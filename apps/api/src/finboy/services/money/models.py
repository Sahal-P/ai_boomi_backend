"""Typed product request and transaction-evidence contracts."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from finboy.db.models.ledger import Category, TransactionStatus
from finboy.services.money.engine import PeriodSpec, TransactionView


class PeriodQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: Literal["current_month", "month"] = "current_month"
    year: int | None = Field(default=None, ge=1, le=9999)
    month: int | None = Field(default=None, ge=1, le=12)

    @model_validator(mode="after")
    def valid_period(self) -> PeriodQuery:
        self.to_period()
        return self

    def to_period(self) -> PeriodSpec:
        return PeriodSpec(kind=self.period, year=self.year, month=self.month)


class TransactionFilters(PeriodQuery):
    category: Category | None = None
    status: TransactionStatus | None = None
    q: str | None = Field(default=None, min_length=1, max_length=160)
    limit: int = Field(default=50, ge=1, le=200)

    @field_validator("q")
    @classmethod
    def valid_query(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("A merchant search cannot be blank")
        return value.strip() if value is not None else None


class Correction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category | None = None
    merchant: str | None = Field(default=None, min_length=1, max_length=160, strict=True)
    amount_minor: int | None = Field(default=None, gt=0, le=10**14, strict=True)

    occurred_at: datetime | None = None
    direction: Literal["in", "out"] | None = None
    kind: (
        Literal[
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
        | None
    ) = None

    @field_validator("occurred_at")
    @classmethod
    def aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("A timezone is required")
        return value

    @field_validator("merchant")
    @classmethod
    def valid_merchant(cls, value: str | None) -> str | None:
        if value is not None and (
            not value.strip() or any(ord(character) < 32 for character in value)
        ):
            raise ValueError("A merchant must be a printable nonempty name")
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def has_correction(self) -> Correction:
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("Supply at least one non-null correction")
        return self


class MergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keep_id: UUID


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_overdue_line: bool = Field(default=False, strict=True)
    monthly_amount_minor: int = Field(gt=0, le=10**14, strict=True)
    label: str = Field(default="Monthly SIP", min_length=1, max_length=80, strict=True)

    @field_validator("label")
    @classmethod
    def valid_label(cls, value: str) -> str:
        if not value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("A label must be a printable nonempty name")
        return value.strip()


class TransactionSource(BaseModel):
    id: UUID
    email_source_id: UUID
    source: Literal["gmail", "eml_upload", "demo_mailbox", "whatsapp_image"]
    sender_domain: str
    received_at: datetime
    classification: str
    event_type: str
    amount_minor: int
    currency: Literal["INR"] = "INR"
    merchant: str | None
    occurred_at: datetime | None
    due_date: date | None
    extraction_method: Literal["rule", "llm"]
    extractor_id: str
    evidence: dict[str, str]
    field_confidence: dict[str, float]


class RevisionView(BaseModel):
    id: UUID
    field: str
    old_value: JsonValue
    new_value: JsonValue
    changed_by: Literal["user", "system"]
    reason: str
    changed_at: datetime


class DecisionView(BaseModel):
    id: UUID
    action: str
    created_at: datetime
    undone_at: datetime | None
    can_undo: bool


class TransactionDetail(BaseModel):
    version: str = "0"
    decisions: list[DecisionView] = Field(default_factory=list)
    transaction: TransactionView
    sources: list[TransactionSource]
    confidence_factors: dict[str, float | int | None]
    revisions: list[RevisionView]
