"""What a household and FinBoy said on WhatsApp (docs/conversation-round/contract.md).

Kept only for a household that agreed (`users.messages_kept_from`), until it clears its chat
history or deletes its account; services/conversations/store.py removes the rows together with
their voice notes and photos in Cloudflare R2. Typed card, account, reference and phone numbers,
UPI IDs and login codes are masked before a row is written.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base

# In: what the household sent. Out: what FinBoy sent (a reply, its spoken words, a template).
KINDS = (
    "text",
    "voice",
    "photo",
    "document",
    "tap",
    "command",
    "buttons",
    "list",
    "voice_reply",
    "template",
)
MEDIA_TYPES = (
    "audio/aac",
    "audio/amr",
    "audio/mpeg",
    "audio/mp4",
    "audio/ogg",
    "image/jpeg",
    "image/png",
)


def _within(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint("direction IN ('in','out')", name="direction"),
        CheckConstraint(f"kind IN ({_within(KINDS)})", name="kind"),
        CheckConstraint("language IN ('en','hi','ml')", name="language"),
        CheckConstraint(f"media_type IN ({_within(MEDIA_TYPES)})", name="media_type"),
        CheckConstraint("length(text) <= 4096 AND length(transcript) <= 4096", name="length"),
        Index("ix_conversation_messages_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # The inbound message this row is, or answers; templates sent first have none.
    receipt_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("whatsapp_receipts.id", ondelete="SET NULL"), index=True
    )
    # FinBoy's send, for its delivered/read status.
    delivery_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("whatsapp_deliveries.id", ondelete="SET NULL")
    )
    direction: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    # Button or list titles FinBoy offered, or the choice a tap made.
    choices: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    # The voice note or photo in R2 (`<prefix><user_id>/<id>.<ext>`), never built from input.
    media_key: Mapped[str | None] = mapped_column(Text)
    media_type: Mapped[str | None] = mapped_column(Text)
    media_bytes: Mapped[int | None] = mapped_column(Integer)
    # A fixed code: the receipt's error (invalid_audio…) or a send's state (sent, failed…).
    outcome: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
