"""Sort payees: one category for every payment to a payee, remembered for the next ones.

docs/statement-round/contract.md. Lists spending payees whose confirmed records are still "Other",
largest first. Choosing a category sets it on all of that payee's spending records the household
hasn't set itself, locks it there as the household's choice, and teaches merchant memory.
"""

from collections import defaultdict
from datetime import datetime, time
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
