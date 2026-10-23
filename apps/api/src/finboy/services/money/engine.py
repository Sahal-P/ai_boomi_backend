"""Deterministic INR calculations over confirmed, user-scoped ledger records."""

import calendar
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from typing import Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from finboy.core.clock import IST, today_ist
from finboy.db.models.ledger import Category, Commitment, Transaction, TransactionStatus


class PeriodSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["current_month", "month"] = "current_month"
    year: int | None = Field(default=None, ge=1, le=9999)
    month: int | None = Field(default=None, ge=1, le=12)

    @model_validator(mode="after")
    def require_month_pair(self) -> PeriodSpec:
        if self.kind == "month" and (self.year is None or self.month is None):
            raise ValueError("An explicit month requires year and month")
        if self.kind == "current_month" and (self.year is not None or self.month is not None):
            raise ValueError("current_month does not accept year or month")
        return self


class CategoryTotal(BaseModel):
    category: Category
    amount_minor: int
    currency: Literal["INR"] = "INR"
    transaction_count: int = Field(ge=0)


class CommitmentView(BaseModel):
    id: UUID
    kind: Literal["bill", "emi", "subscription", "sip"]
    label: str
    amount_minor: int
    currency: Literal["INR"] = "INR"
    due_date: date
    status: Literal["upcoming", "paid", "dismissed"]
    confidence: float = Field(ge=0, le=1)
    source_event_id: UUID | None = None
    paid_transaction_id: UUID | None = None


class TransactionView(BaseModel):
    id: UUID
    direction: Literal["in", "out"]
    kind: Literal[
        "purchase",
        "salary",
        "income_other",
        "refund",
        "reversal",
        "fee",
        "bill_payment",
        "emi",
        "investment",
        "transfer",
    ]
    amount_minor: int = Field(gt=0)
    currency: Literal["INR"] = "INR"
    merchant: str
    category: Category
    occurred_at: datetime
    status: TransactionStatus
    confidence: float = Field(ge=0, le=1)
    review_reason: (
        Literal[
            "low_confidence",
            "merchant_uncertain",
            "possible_duplicate",
            "category_uncertain",
            "unverified_payment",
        ]
        | None
    ) = None
    reference_id: str | None = None
    payment_instrument: str | None = None
    account_last4: str | None = None
    possible_duplicate_of_id: UUID | None = None
    linked_transaction_id: UUID | None = None
    merged_into_id: UUID | None = None


class MoneySummary(BaseModel):
    period_start: date
    period_end: date
    as_of: date
    currency: Literal["INR"] = "INR"
    tracked_income_minor: int
    confirmed_outflows_minor: int
    upcoming_commitments_minor: int
    estimated_unallocated_minor: int
    pending_review_count: int = Field(ge=0)
    pending_review_minor: int
    income_transaction_count: int = Field(ge=0)
    outflow_transaction_count: int = Field(ge=0)
    commitment_count: int = Field(ge=0)
    categories: list[CategoryTotal]
    evidence_transaction_ids: list[UUID]


class SimulationLine(BaseModel):
    label_key: Literal[
        "tracked_income",
        "confirmed_outflows",
        "upcoming_commitments",
        "proposed_monthly",
    ]
    amount_minor: int
    sign: Literal["+", "-"]


class CashFlowSimulation(BaseModel):
    summary: MoneySummary
    proposed_monthly_minor: int = Field(gt=0)
    remaining_after_proposal_minor: int
    lines: list[SimulationLine]
    warnings: list[
        Literal[
            "pending_review_items",
            "negative_remaining",
            "low_buffer",
            "incomplete_coverage",
        ]
    ]
    disclaimer_key: Literal["cash_flow_model_not_investment_advice"] = (
        "cash_flow_model_not_investment_advice"
    )


def money_summary(session: Session, *, user_id: UUID, period: PeriodSpec) -> MoneySummary:
    today = today_ist()
    start, end = period_dates(period, today)
    records = [transaction_view(row) for row in session.scalars(_transactions(user_id, start, end))]
    linked_ids = {row.linked_transaction_id for row in records if row.linked_transaction_id}
    # A refund follows the original's corrected category, even across month boundaries.
    linked_categories = (
        {
            row.id: transaction_view(row).category
            for row in session.scalars(
                select(Transaction).where(
                    Transaction.user_id == user_id, Transaction.id.in_(linked_ids)
                )
            )
        }
        if linked_ids
        else {}
    )
    return calculate_summary(
        records,
        _upcoming(session, user_id=user_id, start=start, end=end, today=today),
        period=period,
        today=today,
        linked_categories=linked_categories,
    )


def category_breakdown(
    session: Session,
    *,
    user_id: UUID,
    period: PeriodSpec,
    category: Category | None = None,
) -> list[CategoryTotal]:
    if category is not None and category not in get_args(Category):
        raise ValueError("invalid_category")
    totals = money_summary(session, user_id=user_id, period=period).categories
    return [item for item in totals if category is None or item.category == category]


def upcoming_commitments(
    session: Session,
    *,
    user_id: UUID,
    period: PeriodSpec,
) -> list[CommitmentView]:
    today = today_ist()
    start, end = period_dates(period, today)
    return _upcoming(session, user_id=user_id, start=start, end=end, today=today)


def find_transactions(
    session: Session,
    *,
    user_id: UUID,
    period: PeriodSpec,
    category: Category | None = None,
    merchant: str | None = None,
    status: TransactionStatus | None = None,
    limit: int = 50,
) -> list[TransactionView]:
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("invalid_limit")
    if category is not None and category not in get_args(Category):
        raise ValueError("invalid_category")
    if status is not None and status not in get_args(TransactionStatus):
        raise ValueError("invalid_status")
    if merchant is not None and (not merchant.strip() or len(merchant) > 160):
        raise ValueError("invalid_merchant")
    start, end = period_dates(period, today_ist())
    statement = _transactions(user_id, start, end)
    if category is not None:
        statement = statement.where(Transaction.category == category)
    if status is not None:
        statement = statement.where(Transaction.status == status)
    if merchant is not None:
        statement = statement.where(
            Transaction.merchant.icontains(merchant.strip(), autoescape=True)
        )
    return [
        transaction_view(row)
        for row in session.scalars(
            statement.order_by(Transaction.occurred_at.desc(), Transaction.id).limit(limit)
        )
    ]


def simulate_monthly_commitment(
    session: Session,
    *,
    user_id: UUID,
    monthly_amount_minor: int,
    label: str,
) -> CashFlowSimulation:
    if type(monthly_amount_minor) is not int or not 0 < monthly_amount_minor <= 10**14:
        raise ValueError("invalid_amount")
    if not isinstance(label, str) or not label.strip() or len(label) > 80:
        raise ValueError("invalid_label")
    return calculate_simulation(
        money_summary(session, user_id=user_id, period=PeriodSpec()), monthly_amount_minor
    )


def period_dates(period: PeriodSpec, today: date) -> tuple[date, date]:
    year = period.year if period.kind == "month" else today.year
    month = period.month if period.kind == "month" else today.month
    assert year is not None and month is not None
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def transaction_view(row: Transaction) -> TransactionView:
    return TransactionView.model_validate(row, from_attributes=True)


def _transactions(user_id: UUID, start: date, end: date) -> Select[tuple[Transaction]]:
    return select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.occurred_at >= datetime.combine(start, time.min, IST),
        Transaction.occurred_at <= datetime.combine(end, time.max, IST),
    )


def _upcoming(
    session: Session, *, user_id: UUID, start: date, end: date, today: date
) -> list[CommitmentView]:
    return [
        CommitmentView.model_validate(row, from_attributes=True)
        for row in session.scalars(
            select(Commitment)
            .where(
                Commitment.user_id == user_id,
                Commitment.status == "upcoming",
                Commitment.due_date >= max(today, start),
                Commitment.due_date <= end,
            )
            .order_by(Commitment.due_date, Commitment.id)
        )
    ]


def calculate_summary(
    records: Sequence[TransactionView],
    commitments: Sequence[CommitmentView],
    *,
    period: PeriodSpec,
    today: date,
    linked_categories: Mapping[UUID, Category] | None = None,
) -> MoneySummary:
    """Pure calculation; counts/evidence include each contributing canonical record once."""
    start, end = period_dates(period, today)
    in_period = sorted(
        (row for row in records if start <= row.occurred_at.astimezone(IST).date() <= end),
        key=lambda row: (row.occurred_at, row.id),
    )
    income: list[TransactionView] = []
    outflows: list[TransactionView] = []
    review = [row for row in in_period if row.status == "needs_review"]
    categories: dict[Category, tuple[int, int]] = {}
    parents = {row.id: row.category for row in records} | dict(linked_categories or {})
    for row in in_period:
        if row.status != "confirmed" or row.kind == "transfer":
            continue
        if row.direction == "in" and row.kind in {"salary", "income_other"}:
            income.append(row)
        elif row.direction == "out" or row.direction == "in" and row.kind in {"refund", "reversal"}:
            outflows.append(row)
            category = (
                parents.get(row.linked_transaction_id, row.category)
                if row.kind in {"refund", "reversal"}
                else row.category
            )
            amount, count = categories.get(category, (0, 0))
            categories[category] = (
                amount + row.amount_minor * (1 if row.direction == "out" else -1),
                count + 1,
            )
    upcoming = [
        row
        for row in commitments
        if row.status == "upcoming" and max(today, start) <= row.due_date <= end
    ]
    category_totals = [
        CategoryTotal(category=key, amount_minor=amount, transaction_count=count)
        for key, (amount, count) in sorted(categories.items())
    ]
    income_total = sum(row.amount_minor for row in income)
    outflow_total = sum(row.amount_minor for row in category_totals)
    upcoming_total = sum(row.amount_minor for row in upcoming)
    contributing = {row.id for row in income + outflows}
    return MoneySummary(
        period_start=start,
        period_end=end,
        as_of=today,
        tracked_income_minor=income_total,
        confirmed_outflows_minor=outflow_total,
        upcoming_commitments_minor=upcoming_total,
        estimated_unallocated_minor=income_total - outflow_total - upcoming_total,
        pending_review_count=len(review),
        pending_review_minor=sum(row.amount_minor for row in review),
        income_transaction_count=len(income),
        outflow_transaction_count=len(outflows),
        commitment_count=len(upcoming),
        categories=category_totals,
        evidence_transaction_ids=[row.id for row in in_period if row.id in contributing],
    )


def calculate_simulation(summary: MoneySummary, monthly_amount_minor: int) -> CashFlowSimulation:
    if type(monthly_amount_minor) is not int or not 0 < monthly_amount_minor <= 10**14:
        raise ValueError("invalid_amount")
    remaining = summary.estimated_unallocated_minor - monthly_amount_minor
    warnings: list[
        Literal["pending_review_items", "negative_remaining", "low_buffer", "incomplete_coverage"]
    ] = []
    if summary.pending_review_count:
        warnings.append("pending_review_items")
    if remaining < 0:
        warnings.append("negative_remaining")
    if summary.tracked_income_minor > 0 and remaining * 10 < summary.tracked_income_minor:
        warnings.append("low_buffer")
    # Email-derived records have no independently verified completeness signal.
    warnings.append("incomplete_coverage")
    return CashFlowSimulation(
        summary=summary,
        proposed_monthly_minor=monthly_amount_minor,
        remaining_after_proposal_minor=remaining,
        lines=[
            SimulationLine(
                label_key="tracked_income", amount_minor=summary.tracked_income_minor, sign="+"
            ),
            SimulationLine(
                label_key="confirmed_outflows",
                amount_minor=summary.confirmed_outflows_minor,
                sign="-",
            ),
            SimulationLine(
                label_key="upcoming_commitments",
                amount_minor=summary.upcoming_commitments_minor,
                sign="-",
            ),
            SimulationLine(
                label_key="proposed_monthly", amount_minor=monthly_amount_minor, sign="-"
            ),
        ],
        warnings=warnings,
    )
