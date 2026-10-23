from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Classification = Literal[
    "bank_alert",
    "card_alert",
    "upi_alert",
    "merchant_receipt",
    "order_confirmation",
    "bill_notice",
    "emi_notice",
    "salary_credit",
    "refund_notice",
    "promotional",
    "non_financial",
    "unknown",
]
EventType = Literal[
    "debit",
    "credit",
    "refund",
    "reversal",
    "fee",
    "salary",
    "bill_due",
    "emi_due",
    "investment",
    "transfer",
    "failed",
]
Category = Literal[
    "salary",
    "other_income",
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
    "other",
]


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    amount_minor: int = Field(gt=0, le=10**14)
    currency: Literal["INR"] = "INR"
    merchant: str | None = None
    occurred_at: datetime | None = None
    due_date: date | None = None
    reference_id: str | None = None
    payment_instrument: str | None = None
    account_last4: str | None = Field(default=None, pattern=r"^\d{4}$")
    category: Category | None = None
    payment_proof: bool = False
    evidence: dict[str, str] = Field(default_factory=dict)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    extraction_method: Literal["rule", "llm"] = "rule"
    extractor_id: str = "rules-v1"
    rule_fields: list[str] = Field(default_factory=list)


class Extraction(BaseModel):
    events: list[Event] = Field(default_factory=list)
    not_transaction: bool = False
