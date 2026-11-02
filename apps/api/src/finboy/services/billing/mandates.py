"""AutoPay mandates: turning AutoPay off, bank notices and erasure.

docs/subscription-round/contract.md. A mandate is only ever ended through PayU's revoke API, and
FinBoy acts on a bank's notice only after PayU's own mandate-status API confirms it. Premium always
lasts to the end of the month already paid.
"""

import logging
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.db.models.billing import BillingPayment, Subscription
from finboy.services.billing.payu import PayUClient, PayUUnavailable

logger = logging.getLogger(__name__)


def stop_renewing(session: Session, subscription: Subscription) -> None:
    """Stop renewing: no next charge, and any announced renewal is dropped."""
    subscription.renewal = "off"
    subscription.mandate_payuid = None
    subscription.mandate_kind = None
    subscription.next_charge_on = None
    subscription.grace_until = None
    session.execute(
        update(BillingPayment)
        .where(
            BillingPayment.user_id == subscription.user_id,
            BillingPayment.kind == "renewal",
            BillingPayment.status == "scheduled",
        )
        .values(status="abandoned")
    )


def turn_off(
    session: Session, settings: Settings, user_id: UUID, client: PayUClient | None = None
) -> None:
    """Revoke the household's mandate at the bank; Premium continues to `paid_through`."""
    subscription = session.get(Subscription, user_id, with_for_update=True)
    if subscription is None or subscription.renewal != "autopay":
        session.rollback()
        return
    mandate, kind = subscription.mandate_payuid or "", subscription.mandate_kind or "card"
    try:
        with client or PayUClient(settings) as payu:
            revoked = payu.revoke(mandate, kind) or payu.mandate_state(mandate, kind) == "ended"
    except PayUUnavailable:
        session.rollback()
        raise AccessError("billing_unavailable") from None
    if not revoked:
        session.rollback()
        raise AccessError("billing_unavailable")
    stop_renewing(session, subscription)
    session.commit()
    logger.info("billing.mandate", extra={"outcome": "revoked", "provider": "payu"})


def on_bank_notice(session: Session, settings: Settings, mandate: str) -> None:
    """A cancellation or change reported by the bank, acted on once PayU confirms it ended."""
    subscription = session.scalar(
        select(Subscription).where(Subscription.mandate_payuid == mandate).with_for_update()
    )
    if subscription is None:
        session.rollback()
        return
    try:
        with PayUClient(settings) as payu:
            state = payu.mandate_state(mandate, subscription.mandate_kind or "card")
    except PayUUnavailable:
        session.rollback()
        logger.warning("billing.mandate", extra={"outcome": "unconfirmed", "provider": "payu"})
        return
    if state == "ended":
        stop_renewing(session, subscription)
        session.commit()
    else:
        session.rollback()
    logger.info("billing.mandate", extra={"outcome": f"notice_{state}", "provider": "payu"})


def revoke_before_erasure(session: Session, settings: Settings, user_id: UUID) -> None:
    """Best effort before an account is deleted, like the Gmail revoke; never blocks deletion."""
    try:
        turn_off(session, settings, user_id)
    except AccessError:
        logger.warning("billing.mandate", extra={"outcome": "revoke_failed", "provider": "payu"})
