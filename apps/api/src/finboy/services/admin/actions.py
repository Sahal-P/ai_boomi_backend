"""What an admin can do (docs/admin-round/contract.md).

Every household action first checks it is allowed for that household's kind and status, then
commits together with its audit entry. Services that commit by themselves (Premium grants, the
pilot eraser) get the entry added first, so it lands in their commit.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.db.models.billing import BillingPayment
from finboy.db.models.core import User
from finboy.services.accounts import erasure
from finboy.services.accounts import households as accounts
from finboy.services.admin import audit
from finboy.services.admin.households import (
    PAGE,
    allowed,
    household_rows,
    kind_of,
    payment_row,
    plans_by_household,
    short,
    status_of,
)
from finboy.services.admin.views import Action, Kind, PaymentPage, PaymentRow
from finboy.services.billing import checkout, links, mandates, payu, renewals
from finboy.services.mail.security import MailError
from finboy.services.pilot.households import PilotError


@dataclass(frozen=True)
class Actor:
    """Who is acting, for the audit entry."""

    admin_id: UUID
    request_id: str | None


def _require(
    session: Session, settings: Settings, user_id: UUID, action: Action, now: datetime
) -> tuple[Kind, str | None]:
    rows = household_rows(session, [User.id == user_id])
    if not rows:
        raise AccessError("not_found")
    row = rows[0]
    plan = plans_by_household(session, settings, rows, now)[row.id]
    kind = kind_of(row.id, row.pilot, row.joined_via, row.consented_at)
    if action not in allowed(kind, status_of(row.deleted_at, row.suspended_at), plan, settings):
        session.rollback()
        raise AccessError("action_not_allowed")
    session.rollback()  # end the read snapshot; each action locks what it changes
    return kind, row.language


def _lock(session: Session, user_id: UUID) -> User:
    """The household row, locked; gone since the check means "not found", never a crash."""
    user = session.get(User, user_id, with_for_update=True)
    if user is None:
        session.rollback()
        raise AccessError("not_found")
    return user


def _record(session: Session, actor: Actor, action: str, user_id: UUID, **detail: str | int):
    audit.record(
        session,
        action,
        admin_id=actor.admin_id,
        household_id=user_id,
        request_id=actor.request_id,
        **detail,
    )


def sign_out(session: Session, settings: Settings, actor: Actor, user_id: UUID, now: datetime):
    _require(session, settings, user_id, "sign_out", now)
    user = _lock(session, user_id)
    user.session_epoch += 1
    _record(session, actor, "household_signed_out", user_id)
    session.commit()


def suspend(session: Session, settings: Settings, actor: Actor, user_id: UUID, now: datetime):
    """No sign-in, WhatsApp replies, sends or charges until restored. AutoPay is turned off at
    the bank (best effort, like erasure), so restoring never restarts charges silently."""
    _require(session, settings, user_id, "suspend", now)
    mandates.revoke_before_erasure(session, settings, user_id)
    user = _lock(session, user_id)
    user.suspended_at = now
    user.session_epoch += 1
    _record(session, actor, "household_suspended", user_id)
    session.commit()


def restore(session: Session, settings: Settings, actor: Actor, user_id: UUID, now: datetime):
    """Lifts the suspension. The household signs in again; a STOP on WhatsApp stays as it was."""
    _require(session, settings, user_id, "restore", now)
    user = _lock(session, user_id)
    user.suspended_at = None
    _record(session, actor, "household_restored", user_id)
    session.commit()


def erase(
    session: Session,
    settings: Settings,
    engine: Engine,
    actor: Actor,
    user_id: UUID,
    *,
    confirm: str,
    now: datetime,
) -> None:
    """The same erasure a household runs from its Privacy page, or `pilot.cli erase`; a sign-up
    that never agreed is discarded entirely. Needs the short ID typed back."""
    kind, _language = _require(session, settings, user_id, "erase", now)
    if confirm.strip().lower() != short(user_id):
        raise AccessError("confirmation_mismatch")

    def entry() -> None:
        _record(session, actor, "household_erased", user_id, via=kind)

    try:
        if kind == "pilot":
            erasure.erase_pilot(session, engine, user_id, also=entry)
        elif kind == "pending":
            erasure.discard(session, user_id, also=entry)
        else:
            erasure.erase_self_serve(session, settings, engine, user_id, also=entry)
    except MailError:
        session.rollback()
        raise AccessError("try_later") from None  # an import is running; it finishes first
    except ValueError, PilotError:
        session.rollback()
        raise AccessError("action_not_allowed") from None


def grant(
    session: Session, settings: Settings, actor: Actor, user_id: UUID, days: int, now: datetime
) -> datetime:
    _require(session, settings, user_id, "premium", now)
    _record(session, actor, "premium_granted", user_id, days=days)
    return renewals.grant(session, user_id, days, now)  # commits the grant and its entry


def cancel_autopay(
    session: Session, settings: Settings, actor: Actor, user_id: UUID, now: datetime
) -> None:
    _require(session, settings, user_id, "autopay_cancel", now)
    mandates.turn_off(session, settings, user_id)  # commits, or raises billing_unavailable
    _record(session, actor, "autopay_cancelled", user_id)
    session.commit()


def pay_link(
    session: Session, settings: Settings, actor: Actor, user_id: UUID, now: datetime
) -> str:
    """A 7-day link anyone holding it can pay with; shown once, to send privately."""
    _kind, language = _require(session, settings, user_id, "pay_link", now)
    user = _lock(session, user_id)
    url = links.link(settings, user.id, user.session_epoch, language or "en")
    _record(session, actor, "pay_link_created", user_id)
    session.commit()
    return url


def payments(session: Session, *, status: str | None, offset: int) -> PaymentPage:
    query = select(BillingPayment)
    total = select(func.count()).select_from(BillingPayment)
    if status is not None:
        query = query.where(BillingPayment.status == status)
        total = total.where(BillingPayment.status == status)
    found = session.scalars(
        query.order_by(BillingPayment.created_at.desc()).offset(offset).limit(PAGE)
    ).all()
    count = session.scalar(total) or 0
    following = offset + PAGE
    return PaymentPage(
        items=[payment_row(item) for item in found],
        total=count,
        offset=offset,
        next_offset=following if following < count else None,
    )


def reconcile(session: Session, settings: Settings, actor: Actor, payment_id: UUID) -> PaymentRow:
    """Ask PayU about one payment FinBoy has not heard the outcome of."""
    payment = session.get(BillingPayment, payment_id)
    if payment is None:
        raise AccessError("not_found")
    if not settings.billing_enabled:
        raise AccessError("billing_unavailable")
    _record(session, actor, "payment_reconciled", payment.user_id, payment=str(payment.id))
    try:
        with payu.PayUClient(settings) as client:
            checkout.reconcile(session, settings, client, [payment.txnid])
    except payu.PayUUnavailable:
        session.rollback()
        raise AccessError("billing_unavailable") from None
    session.commit()
    session.refresh(payment)
    return payment_row(payment)


def tidy(session: Session, actor: Actor) -> int:
    removed = accounts.tidy(session)
    audit.record(
        session,
        "signups_tidied",
        admin_id=actor.admin_id,
        request_id=actor.request_id,
        removed=removed,
    )
    session.commit()
    return removed
