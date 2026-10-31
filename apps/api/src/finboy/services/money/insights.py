"""Reports beyond categories: who you pay, regular payments, money with people, small payments.

docs/statement-round/contract.md. Pure functions over confirmed household records, so the same
figures come from any source (statements, WhatsApp, email). Payees are grouped by their case-folded
name without spaces, because Google Pay prints one person as "Name K M" when paid and "NameKM" when
received from, and shown in their most common spelling. Transfers are left out, as in the month
summary; regular payments always look back six months from the period's end.
"""

import calendar
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.clock import IST, today_ist
from finboy.db.models.ledger import Transaction
from finboy.services.ingestion.types import Category
from finboy.services.money.engine import PeriodSpec, period_dates
from finboy.services.money.merchants import merchant_key
from finboy.services.ux.state import lock_snapshot

SMALL_MINOR = 20_000  # ₹200
REGULAR_MONTHS = 3  # of the last six, with a steady amount
STEADY = 0.10  # within ±10% of the usual amount
LATE = timedelta(days=10)  # a monthly payment this late, while other records go on, has stopped
TOP_PAYEES, TOP_SENDERS, BIGGEST, REGULAR, PEOPLE, SMALL_PLACES = 8, 5, 5, 8, 8, 3


@dataclass(frozen=True)
class Entry:
    """A confirmed record as reports read it."""

    id: UUID
    direction: str
    kind: str
    name: str
    category: str
    amount_minor: int
    occurred_at: datetime

    @property
    def spending(self) -> bool:
        return self.direction == "out" and self.kind != "transfer"

    @property
    def income(self) -> bool:
        return self.direction == "in" and self.kind in {"salary", "income_other"}

    @property
    def day(self) -> date:
        return self.occurred_at.astimezone(IST).date()


class PayeeTotal(BaseModel):
    name: str
    amount_minor: int = Field(ge=0)
    count: int = Field(ge=0)
    share: float = Field(ge=0, le=1)
    category: Category


class BigPayment(BaseModel):
    id: UUID
    name: str
    amount_minor: int
    occurred_at: datetime
    category: Category


class RegularPayment(BaseModel):
    name: str
    usual_minor: int
    months: int = Field(ge=REGULAR_MONTHS, le=6)
    last_paid: date
    next_expected: date
    category: Category


class Person(BaseModel):
    name: str
    sent_minor: int
    received_minor: int
    # Positive: more came back than went out.
    balance_minor: int
    count: int
    last_on: date


class SmallPayments(BaseModel):
    threshold_minor: int
    count: int
    amount_minor: int
    per_month_minor: int
    count_share: float = Field(ge=0, le=1)
    amount_share: float = Field(ge=0, le=1)
    places: list[PayeeTotal]


class Insights(BaseModel):
    period_start: date
    period_end: date
    months: int = Field(ge=1)
    money_out_minor: int
    money_in_minor: int
    payment_count: int
    top_payees: list[PayeeTotal]
    top_senders: list[PayeeTotal]
    biggest: list[BigPayment]
    regular: list[RegularPayment]
    regular_monthly_minor: int
    people: list[Person]
    small: SmallPayments
    data_version: str = "0"


def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month + 1


def next_month(day: date) -> date:
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _share(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


def payee_group(name: str) -> str:
    return "".join((merchant_key(name) or name.casefold()).split())


def _groups(entries: Iterable[Entry]) -> dict[str, list[Entry]]:
    groups: dict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        groups[payee_group(entry.name)].append(entry)
    return groups


def _name(entries: Sequence[Entry]) -> str:
    return Counter(entry.name for entry in entries).most_common(1)[0][0]


def _category(entries: Sequence[Entry]) -> Category:
    return Counter(entry.category for entry in entries).most_common(1)[0][0]  # type: ignore[return-value]


def _totals(groups: dict[str, list[Entry]], whole: int, limit: int) -> list[PayeeTotal]:
    ranked = sorted(
        groups.values(), key=lambda items: (-sum(e.amount_minor for e in items), _name(items))
    )
    return [
        PayeeTotal(
            name=_name(items),
            amount_minor=sum(e.amount_minor for e in items),
            count=len(items),
            share=_share(sum(e.amount_minor for e in items), whole),
            category=_category(items),
        )
        for items in ranked[:limit]
    ]


def regular_payments(entries: Iterable[Entry], *, end: date) -> list[RegularPayment]:
    """Payees paid a steady amount in at least three of the six months ending with `end`.

    A shop paid many times a month at a similar price is daily spending, not a bill: more than
    two payments a month at the usual amount rules a payee out. So does a payment that stopped:
    its next one is over ten days late by the household's last record in the window. Lateness is
    judged against records, not today, so months not imported yet don't make every bill look
    stopped.
    """
    first = date(end.year, end.month, 1)
    for _ in range(5):
        first = (first - timedelta(days=1)).replace(day=1)
    window = [e for e in entries if e.spending and first <= e.day <= end]
    if not window:
        return []
    latest = max(e.day for e in window)
    found = []
    for items in _groups(window).values():
        best: tuple[tuple[int, int, int], list[Entry]] | None = None
        for usual in sorted({e.amount_minor for e in items}):
            near = [e for e in items if abs(e.amount_minor - usual) <= usual * STEADY]
            months = {(e.day.year, e.day.month) for e in near}
            if len(months) < REGULAR_MONTHS or len(near) > 2 * len(months):
                continue
            score = (len(months), len(near), usual)
            if best is None or score > best[0]:
                best = (score, near)
        if best is None:
            continue
        near = best[1]
        last = max(e.day for e in near)
        if next_month(last) + LATE < latest:
            continue
        found.append(
            RegularPayment(
                name=_name(items),
                usual_minor=int(statistics.median(e.amount_minor for e in near)),
                months=best[0][0],
                last_paid=last,
                next_expected=next_month(last),
                category=_category(near),
            )
        )
    return sorted(found, key=lambda item: (-item.usual_minor, item.name))


def people(entries: Iterable[Entry]) -> list[Person]:
    """Counterparties money went to and came back from in the period."""
    sent = _groups(e for e in entries if e.spending)
    received = _groups(e for e in entries if e.income)
    both = []
    for key in sent.keys() & received.keys():
        items = sent[key] + received[key]
        out = sum(e.amount_minor for e in sent[key])
        back = sum(e.amount_minor for e in received[key])
        both.append(
            Person(
                name=_name(items),
                sent_minor=out,
                received_minor=back,
                balance_minor=back - out,
                count=len(items),
                last_on=max(e.day for e in items),
            )
        )
    return sorted(both, key=lambda p: (-(p.sent_minor + p.received_minor), p.name))[:PEOPLE]


def insights(
    entries: Sequence[Entry], history: Sequence[Entry], *, start: date, end: date
) -> Insights:
    """`entries`: the period's confirmed records; `history`: the six months before its end."""
    spending = [e for e in entries if e.spending]
    income = [e for e in entries if e.income]
    money_out = sum(e.amount_minor for e in spending)
    months = months_between(start, end)
    small = [e for e in spending if e.amount_minor < SMALL_MINOR]
    small_amount = sum(e.amount_minor for e in small)
    regular = regular_payments(history, end=end)
    places = sorted(_groups(small).values(), key=lambda items: (-len(items), _name(items)))[
        :SMALL_PLACES
    ]
    return Insights(
        period_start=start,
        period_end=end,
        months=months,
        money_out_minor=money_out,
        money_in_minor=sum(e.amount_minor for e in income),
        payment_count=len(spending),
        top_payees=_totals(_groups(spending), money_out, TOP_PAYEES),
        top_senders=_totals(_groups(income), sum(e.amount_minor for e in income), TOP_SENDERS),
        biggest=[
            BigPayment(
                id=e.id,
                name=e.name,
                amount_minor=e.amount_minor,
                occurred_at=e.occurred_at,
                category=e.category,  # type: ignore[arg-type]
            )
            for e in sorted(spending, key=lambda e: (-e.amount_minor, e.occurred_at))[:BIGGEST]
        ],
        regular=regular[:REGULAR],
        regular_monthly_minor=sum(item.usual_minor for item in regular),
        people=people(entries),
        small=SmallPayments(
            threshold_minor=SMALL_MINOR,
            count=len(small),
            amount_minor=small_amount,
            per_month_minor=small_amount // months,
            count_share=_share(len(small), len(spending)),
            amount_share=_share(small_amount, money_out),
            places=[
                PayeeTotal(
                    name=_name(items),
                    amount_minor=sum(e.amount_minor for e in items),
                    count=len(items),
                    share=_share(len(items), len(small)),
                    category=_category(items),
                )
                for items in places
            ],
        ),
    )


def _entries(session: Session, user_id: UUID, start: date, end: date) -> list[Entry]:
    rows = session.execute(
        select(
            Transaction.id,
            Transaction.direction,
            Transaction.kind,
            Transaction.merchant,
            Transaction.category,
            Transaction.amount_minor,
            Transaction.occurred_at,
        ).where(
            Transaction.user_id == user_id,
            Transaction.dataset == "household",
            Transaction.status == "confirmed",
            Transaction.occurred_at >= datetime.combine(start, time.min, IST),
            Transaction.occurred_at <= datetime.combine(end, time.max, IST),
        )
    )
    return [Entry(*row) for row in rows]


def money_insights(session: Session, *, user_id: UUID, period: PeriodSpec) -> Insights:
    version = lock_snapshot(session, user_id)
    start, end = period_dates(period, today_ist())
    first = date(end.year, end.month, 1)
    for _ in range(5):
        first = (first - timedelta(days=1)).replace(day=1)
    entries = _entries(session, user_id, min(start, first), end)
    result = insights([e for e in entries if e.day >= start], entries, start=start, end=end)
    result.data_version = version
    return result
