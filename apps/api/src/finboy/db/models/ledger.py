from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base

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
TransactionStatus = Literal["confirmed", "needs_review", "rejected", "merged", "failed"]


class EmailSource(Base):
    __tablename__ = "email_sources"
    __table_args__ = (
        UniqueConstraint("user_id", "source", "provider_message_id"),
        CheckConstraint("source IN ('gmail','eml_upload','demo_mailbox')", name="source"),
        CheckConstraint(
            "classification IN ('bank_alert','card_alert','upi_alert','merchant_receipt',"
            "'order_confirmation','bill_notice','emi_notice','salary_credit','refund_notice',"
            "'promotional','non_financial','unknown')",
            name="classification",
        ),
        CheckConstraint(
            "processing_status IN ('pending','extracted','skipped','failed')",
            name="processing_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    import_run_id: Mapped[UUID] = mapped_column(ForeignKey("import_runs.id"), index=True)
    mail_connection_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mail_connections.id"), index=True
    )
    source: Mapped[str] = mapped_column(Text)
    provider_message_id: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(Text)
    sender_domain: Mapped[str] = mapped_column(Text)
    subject_sha256: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    classification: Mapped[str] = mapped_column(Text)
    processing_status: Mapped[str] = mapped_column(Text)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("direction IN ('in','out')", name="direction"),
        CheckConstraint(
            "kind IN ('purchase','salary','income_other','refund','reversal','fee',"
            "'bill_payment','emi','investment','transfer')",
            name="kind",
        ),
        CheckConstraint("amount_minor > 0", name="positive_amount"),
        CheckConstraint("currency = 'INR'", name="currency"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
        CheckConstraint(
            "status IN ('confirmed','needs_review','rejected','merged','failed')", name="status"
        ),
        CheckConstraint(
            "review_reason IN ('low_confidence','merchant_uncertain','possible_duplicate',"
            "'category_uncertain','unverified_payment')",
            name="review_reason",
        ),
        CheckConstraint(
            "category IN ('salary','other_income','rent','food_dining','groceries','transport',"
            "'shopping','utilities','subscriptions','travel','health','education','investments',"
            "'loan_emi','fees','transfer','other')",
            name="category",
        ),
        Index("ix_transactions_user_id_occurred_at", "user_id", "occurred_at"),
        Index("ix_transactions_user_id_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    direction: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="INR")
    merchant: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reference_id: Mapped[str | None] = mapped_column(Text, index=True)
    payment_instrument: Mapped[str | None] = mapped_column(Text)
    account_last4: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    confidence_factors: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text)
    review_reason: Mapped[str | None] = mapped_column(Text)
    possible_duplicate_of_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id"), index=True
    )
    linked_transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id"), index=True
    )
    merged_into_id: Mapped[UUID | None] = mapped_column(ForeignKey("transactions.id"), index=True)
    fingerprint: Mapped[str] = mapped_column(Text, index=True)
    user_locked_fields: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceEvent(Base):
    __tablename__ = "source_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('debit','credit','refund','reversal','fee','salary','bill_due',"
            "'emi_due','investment','transfer','failed')",
            name="event_type",
        ),
        CheckConstraint("currency = 'INR'", name="currency"),
        CheckConstraint("extraction_method IN ('rule','llm')", name="extraction_method"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    email_source_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_sources.id", ondelete="CASCADE"), index=True
    )
    transaction_id: Mapped[UUID | None] = mapped_column(ForeignKey("transactions.id"), index=True)
    event_type: Mapped[str] = mapped_column(Text)
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="INR")
    merchant_raw: Mapped[str | None] = mapped_column(Text)
    merchant_normalized: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[date | None] = mapped_column()
    reference_id: Mapped[str | None] = mapped_column(Text, index=True)
    payment_instrument: Mapped[str | None] = mapped_column(Text)
    account_last4: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[str] = mapped_column(Text)
    extractor_id: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict[str, str]] = mapped_column(JSONB)
    field_confidence: Mapped[dict[str, float]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TransactionRevision(Base):
    __tablename__ = "transaction_revisions"
    __table_args__ = (CheckConstraint("changed_by IN ('user','system')", name="changed_by"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    transaction_id: Mapped[UUID] = mapped_column(ForeignKey("transactions.id"), index=True)
    field: Mapped[str] = mapped_column(Text)
    old_value: Mapped[object] = mapped_column(JSONB)
    new_value: Mapped[object] = mapped_column(JSONB)
    changed_by: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Commitment(Base):
    __tablename__ = "commitments"
    __table_args__ = (
        CheckConstraint("kind IN ('bill','emi','subscription','sip')", name="kind"),
        CheckConstraint("currency = 'INR'", name="currency"),
        CheckConstraint("status IN ('upcoming','paid','dismissed')", name="status"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
        Index("ix_commitments_user_id_status", "user_id", "status"),
        Index("ix_commitments_user_id_due_date", "user_id", "due_date"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="INR")
    due_date: Mapped[date] = mapped_column()
    status: Mapped[str] = mapped_column(Text)
    source_event_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_events.id"), index=True)
    paid_transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id"), index=True
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExtractionCache(Base):
    __tablename__ = "extraction_cache"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cache_key: Mapped[str] = mapped_column(Text, unique=True)
    result: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
