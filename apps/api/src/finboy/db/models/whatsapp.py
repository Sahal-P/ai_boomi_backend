"""Consent and transport metadata only. Never add message/answer/audio/image columns."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base


class WhatsAppBinding(Base):
    __tablename__ = "whatsapp_bindings"
    __table_args__ = (CheckConstraint("language IN ('en','hi','ml')", name="language"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    sender_hash: Mapped[str] = mapped_column(Text, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    # NULL means automatic language detection; explicit en/hi/ml commands override it.
    language: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_inbound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WhatsAppReceipt(Base):
    __tablename__ = "whatsapp_receipts"
    __table_args__ = (
        CheckConstraint("kind IN ('text','audio','image','command')", name="kind"),
        CheckConstraint("language IN ('en','hi','ml')", name="language"),
        CheckConstraint(
            "state IN ('admitted','processing','completed','failed','interrupted','ignored')",
            name="state",
        ),
        CheckConstraint(
            "error_code IN ('provider_unavailable','invalid_audio','assistant_unavailable',"
            "'processing_failed','window_expired','interrupted','disabled','stale_message',"
            "'invalid_image','capture_unavailable','capture_busy')",
            name="error_code",
        ),
        Index("ix_whatsapp_receipts_state_received_at", "state", "received_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    binding_id: Mapped[UUID] = mapped_column(ForeignKey("whatsapp_bindings.id", ondelete="CASCADE"))
    inbound_message_id: Mapped[str] = mapped_column(Text, unique=True)
    content_hash: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    provider_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WhatsAppDelivery(Base):
    __tablename__ = "whatsapp_deliveries"
    __table_args__ = (
        UniqueConstraint("receipt_id", "kind"),
        CheckConstraint("kind IN ('text','audio')", name="kind"),
        CheckConstraint("state IN ('pending','sending','sent','failed','unknown')", name="state"),
        CheckConstraint("provider_status IN ('sent','delivered','read','failed')", name="status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    receipt_id: Mapped[UUID] = mapped_column(ForeignKey("whatsapp_receipts.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    outbound_message_id: Mapped[str | None] = mapped_column(Text, unique=True)
    provider_status: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
