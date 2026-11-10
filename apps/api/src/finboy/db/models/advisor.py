"""The advisor's chats and long-term memory (docs/advisor-round/contract.md).

A household's chats with FinBoy and the facts it chose to remember are kept until the household
deletes them (Memory page, WhatsApp commands) or its account; erasure removes them with its
records (services/accounts/households.py). Audio, photos and diary messages are still never kept.
"""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    REAL,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base

MEMORY_KINDS = ("about", "goal", "plan", "preference", "person", "note")
# Phase 3: what the coach can nudge about (services/advisor/coach.py), most important first.
NUDGE_KINDS = (
    "weekly_recap",
    "due_soon",
    "budget_over",
    "unusual_payment",
    "income_in",
    "budget_near",
    "goal_progress",
    "new_regular",
)


class AdvisorThread(Base):
    """One conversation: a web chat, or a WhatsApp stretch that ends after six idle hours."""

    __tablename__ = "advisor_threads"
    __table_args__ = (
        CheckConstraint("channel IN ('web','whatsapp')", name="channel"),
        Index("ix_advisor_threads_user_last", "user_id", "last_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    # A few sentences written once the chat has gone quiet; earlier chats reach the model this way.
    summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    summarized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Phase 2: the summary's embedding, for "what did we say about…" (unit length, or NULL).
    summary_embedding: Mapped[list[float] | None] = mapped_column(ARRAY(REAL))
    embedding_model: Mapped[str | None] = mapped_column(Text)


class AdvisorMessage(Base):
    """A question or an answer. Tool names are kept to explain answers; their results are not."""

    __tablename__ = "advisor_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="role"),
        CheckConstraint("length(text) BETWEEN 1 AND 4000", name="text"),
        CheckConstraint("language IN ('en','hi','ml')", name="language"),
        Index("ix_advisor_messages_thread_created", "thread_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    thread_id: Mapped[UUID] = mapped_column(ForeignKey("advisor_threads.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    tool_names: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HouseholdMemory(Base):
    """A lasting fact about the household, written in English, like ChatGPT's saved memories."""

    __tablename__ = "household_memories"
    __table_args__ = (
        CheckConstraint(
            "kind IN (" + ",".join(f"'{kind}'" for kind in MEMORY_KINDS) + ")", name="kind"
        ),
        CheckConstraint("source IN ('web','whatsapp','user')", name="source"),
        CheckConstraint("length(text) BETWEEN 1 AND 300", name="text"),
        UniqueConstraint("user_id", "text_key", name="uq_household_memories_user_text"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    # Case-folded, punctuation-free text, so the same fact is never saved twice.
    text_key: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Phase 2: the memory's embedding, to pick the relevant ones when there are many.
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(REAL))
    embedding_model: Mapped[str | None] = mapped_column(Text)


class AdvisorNudge(Base):
    """One coach nudge FinBoy sent first on WhatsApp (phase 3). The row is written before the
    send, so a nudge goes out at most once per number, kind and period, and at most one a day.
    `period_key` is a keyed digest (never a payee name); the words live in the household's chat.
    """

    __tablename__ = "advisor_nudges"
    __table_args__ = (
        CheckConstraint(
            "kind IN (" + ",".join(f"'{kind}'" for kind in NUDGE_KINDS) + ")", name="kind"
        ),
        CheckConstraint("via IN ('message','template')", name="via"),
        CheckConstraint("state IN ('sending','sent','failed','unknown')", name="state"),
        CheckConstraint("provider_status IN ('sent','delivered','read','failed')", name="status"),
        UniqueConstraint("binding_id", "kind", "period_key", name="uq_advisor_nudges_period"),
        UniqueConstraint("binding_id", "day", name="uq_advisor_nudges_day"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    binding_id: Mapped[UUID] = mapped_column(ForeignKey("whatsapp_bindings.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(Text)
    period_key: Mapped[str] = mapped_column(Text)
    # The India date it went out: one nudge a day per number.
    day: Mapped[date] = mapped_column(Date)
    # "message" inside WhatsApp's 24-hour window, else the approved "template".
    via: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    outbound_message_id: Mapped[str | None] = mapped_column(Text, unique=True)
    provider_status: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeEmbedding(Base):
    """A cached embedding of one money guide (apps/api/knowledge), keyed by its text and model.

    The guides themselves live in Git; only their vectors are kept here, regenerable at any time.
    """

    __tablename__ = "knowledge_embeddings"

    content_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    model: Mapped[str] = mapped_column(Text, primary_key=True)
    dimensions: Mapped[int] = mapped_column(Integer, primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(ARRAY(REAL))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
