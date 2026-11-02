"""Which plan a household is on (docs/subscription-round/contract.md).

Decided from the clock and two small rows, so every gate can ask cheaply. The owner and pilot
households are always included; everyone else gets 30 days of Premium from sign-up (or from
launch, if they joined earlier), then keeps Premium for as long as they have paid.
"""

import calendar
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.clock import IST
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.core.errors import AccessError
from finboy.db.models.billing import Subscription
from finboy.db.models.core import User

PRICE_MINOR = 29900
TRIAL = timedelta(days=30)
GRACE = timedelta(days=3)
# Paying ahead adds a month on top of what is left; never more than this far ahead.
PAY_AHEAD = timedelta(days=35)

State = Literal["included", "trial", "active", "grace", "free"]
Renewal = Literal["manual", "autopay", "off"]


@dataclass(frozen=True)
class Plan:
    state: State
    trial_ends_at: datetime | None = None
    paid_through: datetime | None = None
    renewal: Renewal | None = None
    next_charge_on: date | None = None
    grace_until: datetime | None = None

    @property
    def premium(self) -> bool:
        return self.state != "free"

    def starts_next(self, now: datetime) -> datetime:
        """When a payment made now starts: never inside trial or paid time already covered."""
        return max(t for t in (now, self.trial_ends_at, self.paid_through) if t is not None)

    def can_pay(self, now: datetime) -> bool:
        if self.state == "included":
            return False
        if self.state == "grace":
            return True  # a renewal is failing; paying now keeps Premium
        if self.renewal == "autopay":
            return False
        return self.starts_next(now) - now <= PAY_AHEAD


INCLUDED = Plan("included")


def add_month(moment: datetime) -> datetime:
    """The same IST date and time a calendar month later; 31 January becomes 28/29 February."""
    local = moment.astimezone(IST)
    year, month = local.year + (local.month == 12), local.month % 12 + 1
    day = min(local.day, calendar.monthrange(year, month)[1])
    return local.replace(year=year, month=month, day=day).astimezone(UTC)


def trial_end(settings: Settings, joined: datetime) -> datetime:
    """30 days from sign-up, or from launch for households that joined before it."""
    if settings.billing_launch_date is not None:
        joined = max(joined, datetime.combine(settings.billing_launch_date, time(), IST))
    return joined + TRIAL


def included(settings: Settings, user_id: UUID, pilot: bool) -> bool:
    if not settings.billing_enabled or pilot:
        return True
    return user_id == LOCAL_USER_ID and settings.billing_owner_included


def plan_for(
    session: Session, settings: Settings, user_id: UUID, now: datetime | None = None
) -> Plan:
    if not settings.billing_enabled:
        return INCLUDED
    row = session.execute(
        select(User.pilot, User.created_at, User.consented_at).where(User.id == user_id)
    ).one_or_none()
    if row is None:
        return Plan("free")
    if included(settings, user_id, row.pilot):
        return INCLUDED
    now = now or datetime.now(UTC)
    subscription = session.get(Subscription, user_id)
    trial = trial_end(settings, row.consented_at or row.created_at)
    paid = subscription.paid_through if subscription else None
    grace = subscription.grace_until if subscription else None
    if now < trial:
        state: State = "trial"
    elif paid is not None and now < paid:
        state = "active"
    elif grace is not None and now < grace:
        state = "grace"
    else:
        state = "free"
    return Plan(
        state=state,
        trial_ends_at=trial,
        paid_through=paid,
        renewal=subscription.renewal if subscription else None,  # type: ignore[arg-type]
        next_charge_on=subscription.next_charge_on if subscription else None,
        grace_until=grace,
    )


def require_premium(session: Session, settings: Settings, user_id: UUID) -> None:
    """Refuse a Premium feature on the Free plan with the fixed `premium_required` code."""
    if not plan_for(session, settings, user_id).premium:
        raise AccessError("premium_required")
