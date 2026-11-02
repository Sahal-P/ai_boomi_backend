"""FinBoy Premium: paid-through time, payment attempts and the payer's contact.

docs/subscription-round/contract.md. No card number, card token, UPI ID, bank reference, PayU
message, hash or request body is stored. The payer's email and phone are Fernet-encrypted and
erased with the account; payment rows stay as FinBoy's own sales records without them.
"""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    func,
)
from sqlalchemy import text as sql
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base


class BillingProfile(Base):
    """The contact PayU requires with every payment, and which trial nudge was last sent."""

    __tablename__ = "billing_profiles"
    __table_args__ = (
        CheckConstraint(
            "last_nudge IN ('trial_3d','trial_last','trial_over','renewal_failed')",
            name="last_nudge",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    encrypted_email: Mapped[bytes | None] = mapped_column(LargeBinary)
    encrypted_phone: Mapped[bytes | None] = mapped_column(LargeBinary)
    last_nudge: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Subscription(Base):
    """How long a household has paid for, and how it renews."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("renewal IN ('manual','autopay','off')", name="renewal"),
        CheckConstraint("mandate_kind IN ('upi','card')", name="mandate_kind"),
        CheckConstraint(
            "renewal <> 'autopay' OR (mandate_payuid IS NOT NULL AND mandate_kind IS NOT NULL)",
            name="mandate",
        ),
        CheckConstraint("mandate_seq >= 0", name="mandate_seq"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    paid_through: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    renewal: Mapped[str] = mapped_column(Text, server_default="manual")
    # PayU's ID for an AutoPay mandate: the mihpayid of the payment that registered it.
    mandate_payuid: Mapped[str | None] = mapped_column(Text, unique=True)
    mandate_kind: Mapped[str | None] = mapped_column(Text)
    # UPI AutoPay numbers each execution; the registering payment is 1.
    mandate_seq: Mapped[int] = mapped_column(Integer, server_default=sql("0"))
    next_charge_on: Mapped[date | None] = mapped_column(Date)
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BillingPayment(Base):
    """One payment attempt: a checkout through PayU's page, or an AutoPay renewal."""

    __tablename__ = "billing_payments"
    __table_args__ = (
        CheckConstraint("kind IN ('checkout','renewal')", name="kind"),
        CheckConstraint("started_via IN ('web','link','worker')", name="started_via"),
        CheckConstraint(
            "status IN ('started','scheduled','pending','paid','failed','abandoned')",
            name="status",
        ),
        CheckConstraint("amount_minor > 0", name="amount"),
        CheckConstraint("attempts >= 0", name="attempts"),
        Index("ix_billing_payments_user_id_created_at", "user_id", "created_at"),
        Index(
            "ix_billing_payments_open",
            "status",
            "updated_at",
            postgresql_where=sql("status IN ('started','scheduled','pending')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    txnid: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text)
    started_via: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    amount_minor: Mapped[int] = mapped_column(Integer)
    autopay_offered: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))
    mandate_registered: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))
    # PayU's payment ID, the mode's category code (UPI, CC, DC, NB…) and its error code only.
    payu_id: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    covers_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    covers_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Renewals: the debit date announced to the payer, when, its UPI sequence and tries.
    debit_on: Mapped[date | None] = mapped_column(Date)
    predebit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sequence: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, server_default=sql("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
