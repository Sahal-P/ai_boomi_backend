"""The billing timer: reconciliation and AutoPay renewals (docs/subscription-round/contract.md).

Each run, every 15 minutes:
1. Asks PayU (`verify_payment`) about payments started or pending for 10 minutes, so a payment
   whose tab was closed still counts, and abandons checkouts nobody finished in 2 hours.
2. For AutoPay plans renewing within 3 days: confirms the mandate is active, then sends the
   pre-debit notice PayU requires at least 48 hours before the debit.
3. On the renewal day, outside NPCI's UPI peak hours, charges the mandate (`si_transaction`).
4. A failed renewal keeps Premium in grace while it is retried once; when the retry fails too, the
   mandate is revoked and the household is on the Free plan.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from finboy.core.clock import IST
from finboy.core.config import Settings
from finboy.db.models.billing import BillingPayment, Subscription
from finboy.services.billing import checkout, mandates, payu, plans

logger = logging.getLogger(__name__)

RECHECK = timedelta(minutes=10)
ABANDON = timedelta(hours=2)
GIVE_UP = timedelta(days=3)  # a payment pending this long is treated as failed
NOTIFY_AHEAD = 3  # days before the renewal date
NOTICE = timedelta(hours=48)
ATTEMPTS = 2  # the renewal and one retry
PEAKS = ((time(10), time(13)), (time(17), time(21, 30)))  # NPCI: no UPI AutoPay debits then
RUN_LOCK = 0x46424F5942494C  # one timer run at a time


@dataclass
class Summary:
    reconciled: int = 0
    abandoned: int = 0
    notified: int = 0
    charged: int = 0
    failed: int = 0
    ended: int = 0


def in_peak(now: datetime) -> bool:
    clock = now.astimezone(IST).time()
    return any(start <= clock < end for start, end in PEAKS)


def debit_date(due: date, now: datetime) -> date:
    """The renewal date, or the first day the 48-hour notice allows if that is later."""
    return max(due, (now + NOTICE).astimezone(IST).date() + timedelta(days=1))


def reconcile(
    session: Session, settings: Settings, client: payu.PayUClient, now: datetime
) -> Summary:
    summary = Summary()
    rows = session.execute(
        select(
            BillingPayment.id,
            BillingPayment.txnid,
            BillingPayment.status,
            BillingPayment.created_at,
        )
        .where(
            BillingPayment.status.in_(("started", "pending")),
            BillingPayment.updated_at < now - RECHECK,
        )
        .order_by(BillingPayment.updated_at)
        .limit(100)
    ).all()
    session.rollback()
    for start in range(0, len(rows), 25):
        batch = rows[start : start + 25]
        summary.reconciled += checkout.reconcile(
            session, settings, client, [row.txnid for row in batch], now=now
        )
        session.execute(
            update(BillingPayment)
            .where(
                BillingPayment.id.in_([row.id for row in batch]),
                BillingPayment.status.in_(("started", "pending")),
            )
            .values(updated_at=now)
        )
        session.commit()
    summary.abandoned = (
        session.execute(
            update(BillingPayment)
            .where(BillingPayment.status == "started", BillingPayment.created_at < now - ABANDON)
            .values(status="abandoned")
        ).rowcount
        or 0
    )
    stale = session.execute(
        update(BillingPayment)
        .where(BillingPayment.status == "pending", BillingPayment.created_at < now - GIVE_UP)
        .values(status="failed", error_code="expired", settled_at=now)
    ).rowcount
    summary.failed += stale or 0
    session.commit()
    return summary


def _attempts(session: Session, subscription: Subscription) -> list[BillingPayment]:
    """This cycle's renewal attempts: the ones paying for the month after `paid_through`."""
    return list(
        session.scalars(
            select(BillingPayment).where(
                BillingPayment.user_id == subscription.user_id,
                BillingPayment.kind == "renewal",
                BillingPayment.covers_from == subscription.paid_through,
                BillingPayment.status != "abandoned",
            )
        )
    )


def _end(
    session: Session, settings: Settings, client: payu.PayUClient, subscription: Subscription
) -> None:
    """Retries are used up or the mandate ended at the bank: stop renewing, Premium ends."""
    try:
        client.revoke(subscription.mandate_payuid or "", subscription.mandate_kind or "card")
    except payu.PayUUnavailable:
        logger.warning(
            "billing.mandate", extra={"outcome": "revoke_unavailable", "provider": "payu"}
        )
    mandates.stop_renewing(session, subscription)


def notify(session: Session, settings: Settings, client: payu.PayUClient, now: datetime) -> Summary:
    summary = Summary()
    horizon = now.astimezone(IST).date() + timedelta(days=NOTIFY_AHEAD)
    due = session.scalars(
        select(Subscription.user_id).where(
            Subscription.renewal == "autopay",
            Subscription.next_charge_on.is_not(None),
            Subscription.next_charge_on <= horizon,
        )
    ).all()
    session.rollback()
    for user_id in due:
        subscription = session.get(Subscription, user_id, with_for_update=True)
        if (
            subscription is None
            or subscription.renewal != "autopay"
            or not subscription.paid_through
        ):
            session.rollback()
            continue
        attempts = _attempts(session, subscription)
        if any(row.status in {"scheduled", "pending", "paid"} for row in attempts):
            session.rollback()
            continue
        if len(attempts) >= ATTEMPTS:
            _end(session, settings, client, subscription)
            session.commit()
            summary.ended += 1
            continue
        mandate, kind = subscription.mandate_payuid or "", subscription.mandate_kind or "card"
        try:
            state = client.mandate_state(mandate, kind)
            if state == "ended":
                _end(session, settings, client, subscription)
                session.commit()
                summary.ended += 1
                continue
            if state != "active":  # paused or unclear: ask again next run
                session.rollback()
                continue
            sequence = subscription.mandate_seq + 1 if kind == "upi" else None
            debit_on = debit_date(subscription.next_charge_on or horizon, now)
            renewal = BillingPayment(
                id=uuid4(),
                user_id=user_id,
                txnid=payu.new_txnid(),
                kind="renewal",
                started_via="worker",
                status="scheduled",
                amount_minor=plans.PRICE_MINOR,
                covers_from=subscription.paid_through,
                debit_on=debit_on,
                sequence=sequence,
                attempts=len(attempts) + 1,
            )
            refused = client.pre_debit(
                mandate=mandate,
                amount_minor=renewal.amount_minor,
                debit_on=debit_on,
                invoice=renewal.txnid,
                sequence=sequence,
            )
        except payu.PayUUnavailable:
            session.rollback()
            logger.warning("billing.predebit", extra={"outcome": "unavailable", "provider": "payu"})
            continue
        if refused is not None:
            session.rollback()
            logger.warning("billing.predebit", extra={"outcome": "refused", "code": refused})
            continue
        renewal.predebit_at = now
        if sequence is not None:
            subscription.mandate_seq = sequence
        # Premium continues while this attempt is outstanding, to the end of its debit day.
        end_of_debit_day = datetime.combine(debit_on + timedelta(days=1), time(), IST)
        subscription.grace_until = max(
            subscription.paid_through + plans.GRACE, end_of_debit_day.astimezone(UTC)
        )
        session.add(renewal)
        session.commit()
        summary.notified += 1
        logger.info("billing.predebit", extra={"outcome": "sent", "payment_id": str(renewal.id)})
    return summary


def charge(session: Session, settings: Settings, client: payu.PayUClient, now: datetime) -> Summary:
    summary = Summary()
    if in_peak(now):
        return summary
    today = now.astimezone(IST).date()
    ready = session.scalars(
        select(BillingPayment.id).where(
            BillingPayment.kind == "renewal",
            BillingPayment.status == "scheduled",
            BillingPayment.debit_on <= today,
            BillingPayment.predebit_at <= now - NOTICE,
        )
    ).all()
    session.rollback()
    for payment_id in ready:
        renewal = session.get(BillingPayment, payment_id, with_for_update=True)
        subscription = session.get(Subscription, renewal.user_id) if renewal else None
        if renewal is None or renewal.status != "scheduled":
            session.rollback()
            continue
        if (
            subscription is None
            or subscription.renewal != "autopay"
            or subscription.paid_through != renewal.covers_from
        ):
            # Paid by hand meanwhile, or AutoPay turned off: this debit is no longer owed.
            renewal.status = "abandoned"
            session.commit()
            continue
        try:
            charged = client.charge(
                mandate=subscription.mandate_payuid or "",
                txnid=renewal.txnid,
                amount_minor=renewal.amount_minor,
                invoice=renewal.txnid,
                sequence=renewal.sequence,
            )
        except payu.PayUUnavailable:
            # The request may have reached PayU: ask verify_payment next run instead of retrying.
            renewal.status = "pending"
            session.commit()
            continue
        session.commit()
        result = payu.Result(
            txnid=renewal.txnid,
            outcome=charged.outcome,
            amount_minor=renewal.amount_minor,
            payu_id=charged.payu_id,
            mode=None,
            mandate=False,
            error_code=charged.error_code,
        )
        settled = checkout.settle(session, settings, result, now=now)
        if settled is not None and settled.status == "paid":
            summary.charged += 1
        elif settled is not None and settled.status == "failed":
            summary.failed += 1
    return summary


def run(
    session: Session, settings: Settings, client: payu.PayUClient, now: datetime | None = None
) -> Summary:
    """One timer run; a second run started meanwhile does nothing."""
    now = now or datetime.now(UTC)
    if not session.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": RUN_LOCK}):
        return Summary()
    try:
        total = reconcile(session, settings, client, now)
        for step in (notify, charge):
            part = step(session, settings, client, now)
            for name in vars(total):
                setattr(total, name, getattr(total, name) + getattr(part, name))
        return total
    finally:
        session.rollback()
        session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": RUN_LOCK})
        session.commit()


def grant(session: Session, user_id: UUID, days: int, now: datetime | None = None) -> datetime:
    """Support: add days of Premium without a payment (for example after a refund dispute)."""
    now = now or datetime.now(UTC)
    subscription = session.get(Subscription, user_id, with_for_update=True)
    if subscription is None:
        subscription = Subscription(user_id=user_id, renewal="manual", mandate_seq=0)
        session.add(subscription)
    start = max(now, subscription.paid_through or now)
    subscription.paid_through = start + timedelta(days=days)
    if subscription.renewal == "autopay":
        subscription.next_charge_on = subscription.paid_through.astimezone(IST).date()
    session.commit()
    return subscription.paid_through


def open_payments(session: Session) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(BillingPayment)
            .where(BillingPayment.status.in_(("started", "scheduled", "pending")))
        )
        or 0
    )
