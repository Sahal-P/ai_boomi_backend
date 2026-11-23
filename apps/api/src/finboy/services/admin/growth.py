"""How self-serve households join, stay and use FinBoy over time (docs/admin-growth/contract.md).

Only households that signed themselves up and agreed count; the owner and the village pilot are
left out. A household is active on a day it sent FinBoy a WhatsApp message or saved a record,
the two signals the overview uses. Days are IST and weeks start on Monday. Counts and dates
only: nothing here reads an amount, a payee or a message.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from statistics import median
from typing import Literal
from uuid import UUID

from sqlalchemy import Date, cast, func, select, union
from sqlalchemy.orm import Session

from finboy.core.clock import IST
from finboy.db.models.core import User
from finboy.db.models.ledger import Transaction
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppReceipt
from finboy.services.accounts import visits
from finboy.services.admin.views import (
    Growth,
    GrowthCohort,
    GrowthFunnel,
    GrowthPeriod,
    GrowthPoint,
    GrowthSummary,
    GrowthUnit,
)

CohortUnit = Literal["week", "month"]
# Each period: its unit, how many of them are shown, and how its retention grid groups joiners.
PERIODS: dict[GrowthPeriod, tuple[GrowthUnit, int, CohortUnit]] = {
    "30d": ("day", 30, "week"),
    "12w": ("week", 12, "week"),
    "12m": ("month", 12, "month"),
}
SAVED = ("confirmed", "needs_review")
# (household, day) pairs one page reads, newest first: 100 households over a whole year fit.
MAX_PAIRS = 50_000


@dataclass(frozen=True)
class Span:
    """A run of IST days, both ends included."""

    start: date
    end: date

    def __contains__(self, day: object) -> bool:
        return isinstance(day, date) and self.start <= day <= self.end


@dataclass(frozen=True)
class Member:
    """One self-serve household that agreed."""

    id: UUID
    started: datetime  # its first message, or its Google sign-in
    joined: date  # the IST day it agreed
    left: date | None  # the IST day it was deleted
    first_record: datetime | None  # its first still-confirmed record


def floor(day: date, unit: GrowthUnit) -> date:
    if unit == "week":
        return day - timedelta(days=day.weekday())
    if unit == "month":
        return day.replace(day=1)
    return day


def following(start: date, unit: GrowthUnit) -> date:
    """The first day of the next day, week or month."""
    if unit == "day":
        return start + timedelta(days=1)
    if unit == "week":
        return start + timedelta(days=7)
    return (start.replace(day=28) + timedelta(days=4)).replace(day=1)


def walk(start: date, today: date, unit: GrowthUnit) -> list[Span]:
    """Every day, week or month from the one holding `start` to the running one."""
    found: list[Span] = []
    start = floor(start, unit)
    while start <= today:
        after = following(start, unit)
        found.append(Span(start, after - timedelta(days=1)))
        start = after
    return found


def spans(unit: GrowthUnit, count: int, today: date) -> list[Span]:
    """`count` days, weeks or months ending with the running one, oldest first."""
    start = floor(today, unit)
    for _ in range(count - 1):
        start = floor(start - timedelta(days=1), unit)
    return walk(start, today, unit)


def funnel_totals(rows: Iterable[visits.Funnel]) -> GrowthFunnel:
    """The sign-up funnel's rows added up, with sign-ups that came with no visit kept apart."""
    rows = list(rows)
    visited = [row for row in rows if not row.direct]
    direct = [row for row in rows if row.direct]
    return GrowthFunnel(
        opened=sum(row.opened for row in visited),
        tapped=sum(row.tapped for row in visited),
        signed_up=sum(row.signed_up for row in visited),
        agreed=sum(row.agreed for row in visited),
        first_record=sum(row.first_record for row in visited),
        direct_signed_up=sum(row.signed_up for row in direct),
        direct_agreed=sum(row.agreed for row in direct),
        direct_first_record=sum(row.first_record for row in direct),
    )


def assemble(
    period: GrowthPeriod,
    today: date,
    members: Sequence[Member],
    activity: dict[UUID, set[date]],
    saved: Iterable[tuple[UUID, date, int]],
    funnel: GrowthFunnel,
) -> Growth:
    """The page from plain inputs. Activity and records count from the day a household agreed;
    an erased household's activity went with it, so it counts as joined, then left."""
    unit, count, cohort_unit = PERIODS[period]
    shown = spans(unit, count, today)
    window = Span(shown[0].start, today)
    earlier = spans(unit, count, shown[0].start - timedelta(days=1))
    before = Span(earlier[0].start, earlier[-1].end)
    first = min((member.joined for member in members), default=None)
    days = {
        member.id: {day for day in activity.get(member.id, ()) if day >= member.joined}
        for member in members
    }
    joined_on = {member.id: member.joined for member in members}
    records = [
        (user, day, n) for user, day, n in saved if user in joined_on and day >= joined_on[user]
    ]

    def active_in(group: Iterable[Member], span: Span) -> int:
        return sum(1 for member in group if any(day in span for day in days[member.id]))

    def point(span: Span) -> GrowthPoint:
        end = min(span.end, today)
        inside = [(user, n) for user, day, n in records if day in span]
        return GrowthPoint(
            start=span.start,
            end=span.end,
            partial=today in span,
            joined=sum(1 for member in members if member.joined in span),
            left=sum(1 for member in members if member.left in span),
            households=sum(
                1
                for member in members
                if member.joined <= end and (member.left is None or member.left > end)
            ),
            active=active_in(members, span),
            records=sum(n for _user, n in inside),
            recording=len({user for user, _n in inside}),
        )

    cohorts = [
        GrowthCohort(
            start=span.start,
            households=len(group := [member for member in members if member.joined in span]),
            active=[active_in(group, later) for later in walk(span.start, today, cohort_unit)],
        )
        for span in walk(window.start, today, cohort_unit)
        if first is not None and span.end >= first
    ]
    joined = [member for member in members if member.joined in window]
    minutes = [
        (member.first_record - member.started).total_seconds() / 60
        for member in joined
        if member.first_record is not None
    ]
    minutes = [value for value in minutes if value >= 0]
    return Growth(
        period=period,
        unit=unit,
        cohort_unit=cohort_unit,
        today=today,
        summary=GrowthSummary(
            joined=len(joined),
            joined_before=sum(1 for member in members if member.joined in before),
            left=sum(1 for member in members if member.left in window),
            households=sum(1 for member in members if member.left is None),
            active_week=active_in(members, Span(today - timedelta(days=6), today)),
            activated=sum(1 for member in joined if member.first_record is not None),
            minutes_to_record=round(median(minutes), 1) if minutes else None,
        ),
        points=[point(span) for span in shown if first is not None and span.end >= first],
        funnel=funnel,
        cohorts=cohorts,
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _ist(value: datetime) -> date:
    return _aware(value).astimezone(IST).date()


def _day(column):
    """A stored time's IST day, worked out by PostgreSQL."""
    return cast(func.timezone("Asia/Kolkata", column), Date)


def _self_serve():
    return select(User.id).where(User.joined_via.is_not(None), User.consented_at.is_not(None))


def members(session: Session) -> list[Member]:
    self_serve = _self_serve()
    firsts = visits.first_records(self_serve)
    rows = session.execute(
        select(User.id, User.created_at, User.consented_at, User.deleted_at, firsts.c.at)
        .outerjoin(firsts, firsts.c.user_id == User.id)
        .where(User.id.in_(self_serve))
    ).all()
    return [
        Member(
            id=user_id,
            started=_aware(created),
            joined=_ist(agreed),
            left=_ist(deleted) if deleted else None,
            first_record=_aware(first) if first else None,
        )
        for user_id, created, agreed, deleted, first in rows
    ]


def activity(session: Session, since: datetime) -> dict[UUID, set[date]]:
    """The IST days since `since` on which each household sent a WhatsApp message or saved a
    record (any state, as the overview counts them)."""
    self_serve = _self_serve()
    messages = (
        select(
            WhatsAppBinding.user_id.label("user_id"), _day(WhatsAppReceipt.received_at).label("day")
        )
        .join(WhatsAppBinding, WhatsAppBinding.id == WhatsAppReceipt.binding_id)
        .where(WhatsAppReceipt.received_at >= since, WhatsAppBinding.user_id.in_(self_serve))
    )
    records = select(
        Transaction.user_id.label("user_id"), _day(Transaction.created_at).label("day")
    ).where(
        Transaction.dataset == "household",
        Transaction.created_at >= since,
        Transaction.user_id.in_(self_serve),
    )
    both = union(messages, records).subquery()
    found: dict[UUID, set[date]] = defaultdict(set)
    for user_id, day in session.execute(
        select(both.c.user_id, both.c.day).order_by(both.c.day.desc()).limit(MAX_PAIRS)
    ):
        found[user_id].add(day)
    return found


def saved(session: Session, since: datetime) -> list[tuple[UUID, date, int]]:
    """Records saved since `since` that are confirmed or waiting for a check, per household and
    IST day."""
    day = _day(Transaction.created_at)
    return [
        (user_id, on, n)
        for user_id, on, n in session.execute(
            select(Transaction.user_id, day, func.count())
            .where(
                Transaction.dataset == "household",
                Transaction.status.in_(SAVED),
                Transaction.created_at >= since,
                Transaction.user_id.in_(_self_serve()),
            )
            .group_by(Transaction.user_id, day)
            .order_by(day.desc())
            .limit(MAX_PAIRS)
        )
    ]


def growth(session: Session, period: GrowthPeriod, now: datetime) -> Growth:
    today = _ist(now)
    unit, count, cohort_unit = PERIODS[period]
    shown = spans(unit, count, today)
    # Activity from the first cohort's Monday or month start, and always the last 7 days.
    since = datetime.combine(
        min(floor(shown[0].start, cohort_unit), today - timedelta(days=6)), time(), IST
    )
    return assemble(
        period,
        today,
        members(session),
        activity(session, since),
        saved(session, since),
        funnel_totals(visits.funnel(session, datetime.combine(shown[0].start, time(), IST))),
    )
