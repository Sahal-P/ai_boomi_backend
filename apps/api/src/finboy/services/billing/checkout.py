"""Starting PayU checkouts and settling their outcomes (docs/subscription-round/contract.md).

A payment counts once, when a result PayU signed (the browser's return, a webhook, or
`verify_payment`) says it succeeded for the amount FinBoy asked. States only move forward, under a
row lock, so a return and a webhook arriving together settle it exactly once.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from finboy.core.clock import IST
from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.db.models.billing import BillingPayment, Subscription
from finboy.services.billing import contact, payu, plans

logger = logging.getLogger(__name__)

OPEN_LIMIT = 5  # unpaid checkouts per household in ten minutes
MANDATE_DAYS = 5 * 365
Via = Literal["web", "link"]


@dataclass(frozen=True)
class Started:
    payment_id: UUID
    action: str
    fields: dict[str, str]


def mandate_kind(mode: str | None) -> str | None:
    """AutoPay runs on UPI and cards only; PayU's mode codes say which."""
    if mode == "UPI":
        return "upi"
    return "card" if mode in {"CC", "DC", "CREDITCARD", "DEBITCARD"} else None


def start(
    session: Session,
    settings: Settings,
    user_id: UUID,
    *,
    email: str | None,
    phone: str | None,
    via: Via,
    hindi: bool = False,
    now: datetime | None = None,
) -> Started:
    """A signed PayU form for one month of Premium; the salt never leaves the server."""
    if not settings.billing_enabled:
        raise AccessError("billing_unavailable")
    now = now or datetime.now(UTC)
    plan = plans.plan_for(session, settings, user_id, now)
    if not plan.can_pay(now):
        raise AccessError("already_paid")
    recent = session.scalar(
        select(func.count())
        .select_from(BillingPayment)
        .where(
            BillingPayment.user_id == user_id,
            BillingPayment.status == "started",
            BillingPayment.created_at > now - timedelta(minutes=10),
        )
    )
    if (recent or 0) >= OPEN_LIMIT:
        raise AccessError("try_later")
    contact.save(session, settings, user_id, email=email, phone=phone)
    known = contact.stored(session, settings, user_id)
    if known.email is None or known.phone is None:
        raise AccessError("contact_required")
    mandate = None
    if settings.payu_autopay_enabled and plan.renewal != "autopay":
        # The mandate's first debit is when the month paid now runs out.
        first = plans.add_month(plan.starts_next(now)).astimezone(IST).date()
        mandate = (first, first + timedelta(days=MANDATE_DAYS))
    payment = BillingPayment(
        id=uuid4(),
        user_id=user_id,
        txnid=payu.new_txnid(),
        kind="checkout",
        started_via=via,
        status="started",
        amount_minor=plans.PRICE_MINOR,
        autopay_offered=mandate is not None,
    )
    form = payu.checkout_form(
        settings,
        txnid=payment.txnid,
        amount_minor=payment.amount_minor,
        email=known.email,
        phone=known.phone,
        mandate=mandate,
        hindi=hindi,
    )
    session.add(payment)
    session.commit()
    logger.info(
        "billing.checkout_started",
        extra={"payment_id": str(payment.id), "stage": via, "provider": "payu"},
    )
    return Started(payment.id, form.action, form.fields)


def _paid(
    session: Session,
    settings: Settings,
    payment: BillingPayment,
    result: payu.Result,
    now: datetime,
) -> None:
    subscription = session.get(Subscription, payment.user_id, with_for_update=True)
    if subscription is None:
        subscription = Subscription(user_id=payment.user_id, renewal="manual", mandate_seq=0)
        session.add(subscription)
        session.flush()
    plan = plans.plan_for(session, settings, payment.user_id, now)
    if payment.kind == "renewal":
        # A renewal continues the paid month it follows, even when it lands in grace.
        start = subscription.paid_through or plan.starts_next(now)
    else:
        start = plan.starts_next(now)
    end = plans.add_month(start)
    payment.covers_from, payment.covers_to = start, end
    subscription.paid_through = end
    subscription.grace_until = None
    kind = mandate_kind(result.mode)
    if payment.kind == "checkout" and result.mandate and result.payu_id and kind:
        subscription.renewal = "autopay"
        subscription.mandate_payuid = result.payu_id
        subscription.mandate_kind = kind
        subscription.mandate_seq = 1
        payment.mandate_registered = True
    elif payment.kind == "checkout" and subscription.renewal != "autopay":
        subscription.renewal = "manual"
    if payment.kind == "renewal" and payment.sequence:
        subscription.mandate_seq = max(subscription.mandate_seq, payment.sequence)
    subscription.next_charge_on = (
        end.astimezone(IST).date() if subscription.renewal == "autopay" else None
    )
    payment.status = "paid"
    payment.error_code = None
    payment.settled_at = now


def settle(
    session: Session, settings: Settings, result: payu.Result, *, now: datetime | None = None
) -> BillingPayment | None:
    """Apply one PayU-signed outcome to the payment it names; None if FinBoy did not start it."""
    now = now or datetime.now(UTC)
    payment = session.scalar(
        select(BillingPayment).where(BillingPayment.txnid == result.txnid).with_for_update()
    )
    if payment is None:
        session.rollback()
        return None
    if payment.status == "paid":
        session.rollback()
        return payment  # a replay or a late webhook changes nothing
    if result.outcome == "paid" and result.amount_minor != payment.amount_minor:
        session.rollback()
        logger.warning(
            "billing.amount_mismatch", extra={"payment_id": str(payment.id), "provider": "payu"}
        )
        return None
    payment.payu_id = result.payu_id or payment.payu_id
    payment.mode = result.mode or payment.mode
    if result.outcome == "paid":
        _paid(session, settings, payment, result, now)
    elif result.outcome == "pending":
        if payment.status in {"started", "scheduled", "abandoned"}:
            payment.status = "pending"
    elif payment.status != "failed":
        payment.status = "failed"
        payment.error_code = result.error_code
        payment.settled_at = now
    session.commit()
    logger.info(
        "billing.payment_settled",
        extra={
            "payment_id": str(payment.id),
            "outcome": payment.status,
            "stage": payment.kind,
            "code": payment.error_code,
            "provider": "payu",
        },
    )
    return payment


def receive(
    session: Session, settings: Settings, fields: Mapping[str, str], *, now: datetime | None = None
) -> tuple[BillingPayment | None, str]:
    """Check a PayU result (the browser's return or a webhook) and settle it.

    Returns the payment and "settled", or None and the reason it was refused.
    """
    if settings.payu_merchant_salt is None or fields.get("key") != settings.payu_merchant_key:
        return None, "wrong_key"
    if not payu.TXNID.fullmatch(fields.get("txnid", "")):
        return None, "unknown_txnid"
    if not payu.authentic(fields, settings.payu_merchant_salt.get_secret_value()):
        return None, "bad_hash"
    payment = settle(session, settings, payu.read_result(fields), now=now)
    return payment, "settled" if payment is not None else "unknown_txnid"


def reconcile(
    session: Session,
    settings: Settings,
    client: payu.PayUClient,
    txnids: Sequence[str],
    *,
    now: datetime | None = None,
) -> int:
    """Ask PayU about payments whose outcome FinBoy has not heard; settles what PayU knows."""
    found = client.verify(txnids)
    for result in found.values():
        settle(session, settings, result, now=now)
    return len(found)


def confirm_soon(engine: Engine, settings: Settings, txnid: str) -> None:
    """After a pending return: one `verify_payment`, outside the request. Never raises."""
    try:
        with Session(engine) as session, payu.PayUClient(settings) as client:
            reconcile(session, settings, client, [txnid])
    except Exception as exc:  # the worker reconciles again within ten minutes
        logger.warning("billing.confirm_unavailable", extra={"error_type": type(exc).__name__})
