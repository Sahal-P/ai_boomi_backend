"""Sort payees: one category for every payment to a payee, remembered for the next ones.

docs/statement-round/contract.md. Lists spending payees whose confirmed records are still "Other",
largest first. Choosing a category sets it on all of that payee's spending records the household
hasn't set itself, locks it there as the household's choice, and teaches merchant memory.
"""

from collections import defaultdict
from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finboy.core.clock import IST, today_ist
from finboy.db.models.ledger import Transaction
from finboy.services.ledger.persist import refresh_links
from finboy.services.ledger.reconcile import correct_transaction
from finboy.services.money import merchants
from finboy.services.money.engine import PeriodSpec, period_dates
from finboy.services.privacy.audit import audit
from finboy.services.ux.decisions import VersionRequest
from finboy.services.ux.state import TaskError, data_version, lock_snapshot, require_version

LIMIT = 50
# What a payment can be sorted into; income categories belong to money received.
SpendingCategory = Literal[
    "rent",
    "food_dining",
    "groceries",
    "transport",
    "shopping",
    "utilities",
    "subscriptions",
    "travel",
    "health",
    "education",
    "investments",
    "loan_emi",
    "fees",
    "transfer",
    "farming",
    "livestock",
    "phone_recharge",
    "family_events",
    "work",
    "friends",
    "remittance",
    "other",
]


class Payee(BaseModel):
    name: str
    count: int
    amount_minor: int


class PayeeList(BaseModel):
    items: list[Payee]
    spent_minor: int
    unsorted_minor: int
    data_version: str


class PayeeChoice(VersionRequest):
    name: str = Field(min_length=1, max_length=160)
    category: SpendingCategory

    @field_validator("name")
    @classmethod
    def printable(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("A payee must be a printable name")
        return value.strip()


class PayeeResult(BaseModel):
    updated: int
    data_version: str


def unsorted_payees(session: Session, *, user_id: UUID, period: PeriodSpec) -> PayeeList:
    version = lock_snapshot(session, user_id)
    start, end = period_dates(period, today_ist())
    rows = session.execute(
        select(Transaction.merchant, Transaction.category, Transaction.amount_minor).where(
            Transaction.user_id == user_id,
            Transaction.dataset == "household",
            Transaction.status == "confirmed",
            Transaction.direction == "out",
            Transaction.kind != "transfer",
            Transaction.occurred_at >= datetime.combine(start, time.min, IST),
            Transaction.occurred_at <= datetime.combine(end, time.max, IST),
        )
    )
    spent = unsorted = 0
    groups: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for name, category, amount in rows:
        spent += amount
        key = merchants.merchant_key(name)
        if category == "other" and key is not None:
            unsorted += amount
            groups[key].append((name, amount))
    items = sorted(
        (
            Payee(
                name=max({n for n, _ in group}, key=lambda n: sum(1 for m, _ in group if m == n)),
                count=len(group),
                amount_minor=sum(amount for _, amount in group),
            )
            for group in groups.values()
        ),
        key=lambda payee: (-payee.amount_minor, payee.name),
    )
    return PayeeList(
        items=items[:LIMIT], spent_minor=spent, unsorted_minor=unsorted, data_version=version
    )


class OtherPayee(BaseModel):
    name: str
    count: int
    amount_minor: int
    latest: date
    remembered: str | None = None  # the category remembered for the payee, if any


class OtherPayees(BaseModel):
    """What Ask reads to sort "Other" (docs/advisor-edits-round/contract.md)."""

    items: list[OtherPayee]  # largest first, at most LIMIT
    payees: int  # named payees with payments in "Other", listed or not
    spent_minor: int
    other_minor: int
    other_count: int
    # Unknown or hidden names, which may be several people: sorted one payment at a time.
    unnamed_count: int
    unnamed_minor: int
    # Categorised "transfer" but not marked as an own-account move, so still counted as spending.
    transfer_count: int
    transfer_minor: int


def other_payees(session: Session, *, user_id: UUID, period: PeriodSpec) -> OtherPayees:
    """Spending payees still in "Other", grouped as `unsorted_payees` groups them."""
    lock_snapshot(session, user_id)
    start, end = period_dates(period, today_ist())
    rows = session.execute(
        select(
            Transaction.merchant,
            Transaction.category,
            Transaction.amount_minor,
            Transaction.occurred_at,
        ).where(
            Transaction.user_id == user_id,
            Transaction.dataset == "household",
            Transaction.status == "confirmed",
            Transaction.direction == "out",
            Transaction.kind != "transfer",
            Transaction.occurred_at >= datetime.combine(start, time.min, IST),
            Transaction.occurred_at <= datetime.combine(end, time.max, IST),
        )
    )
    spent = other = count = unnamed = unnamed_count = moved = moved_count = 0
    groups: dict[str, list[tuple[str, int, datetime]]] = defaultdict(list)
    for name, category, amount, occurred_at in rows:
        spent += amount
        if category == "transfer":
            moved, moved_count = moved + amount, moved_count + 1
        if category != "other":
            continue
        other, count = other + amount, count + 1
        key = merchants.merchant_key(name)
        if key is None:
            unnamed, unnamed_count = unnamed + amount, unnamed_count + 1
        else:
            groups[key].append((name, amount, occurred_at))
    memory = merchants.memory(session, user_id)
    items = sorted(
        (
            OtherPayee(
                name=max(
                    {n for n, _, _ in group}, key=lambda n: (sum(m == n for m, _, _ in group), n)
                ),
                count=len(group),
                amount_minor=sum(amount for _, amount, _ in group),
                latest=max(at for _, _, at in group).astimezone(IST).date(),
                remembered=memory.category(group[0][0]),
            )
            for group in groups.values()
        ),
        key=lambda payee: (-payee.amount_minor, payee.name),
    )
    return OtherPayees(
        items=items[:LIMIT],
        payees=len(items),
        spent_minor=spent,
        other_minor=other,
        other_count=count,
        unnamed_count=unnamed_count,
        unnamed_minor=unnamed,
        transfer_count=moved_count,
        transfer_minor=moved,
    )


def sort_payee(session: Session, *, user_id: UUID, choice: PayeeChoice) -> PayeeResult:
    """Set the category on every spending record of the payee; the caller commits."""
    require_version(session, user_id, choice.expected_version)
    key = merchants.merchant_key(choice.name)
    if key is None:
        raise TaskError("invalid_decision")
    rows = session.scalars(
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.dataset == "household",
            Transaction.direction == "out",
            Transaction.status.in_(["confirmed", "needs_review"]),
            func.lower(Transaction.merchant) == key,
        )
        .order_by(Transaction.occurred_at, Transaction.id)
    )
    updated = 0
    for row in rows:
        locked = "category" in (row.user_locked_fields or [])
        if locked or merchants.merchant_key(row.merchant) != key or row.category == choice.category:
            continue
        correct_transaction(
            session,
            user_id=user_id,
            transaction_id=row.id,
            category=choice.category,
            reason="payee_category",
        )
        updated += 1
    merchants.learn(session, user_id, choice.name, choice.category)
    refresh_links(session, user_id)
    audit(session, "review.completed", "user", user_id, user_id=user_id)
    session.flush()
    return PayeeResult(updated=updated, data_version=data_version(session, user_id))
