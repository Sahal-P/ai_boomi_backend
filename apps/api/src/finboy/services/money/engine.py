"""Shared Phase 1 interfaces. A4 implements all calculations and SQL loading."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from finboy.db.models.ledger import Category, TransactionStatus


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
    raise NotImplementedError


def category_breakdown(
    session: Session,
    *,
    user_id: UUID,
    period: PeriodSpec,
    category: Category | None = None,
) -> list[CategoryTotal]:
    raise NotImplementedError


def upcoming_commitments(
    session: Session,
    *,
    user_id: UUID,
    period: PeriodSpec,
) -> list[CommitmentView]:
    raise NotImplementedError


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
    raise NotImplementedError


def simulate_monthly_commitment(
    session: Session,
    *,
    user_id: UUID,
    monthly_amount_minor: int,
    label: str,
) -> CashFlowSimulation:
    raise NotImplementedError
