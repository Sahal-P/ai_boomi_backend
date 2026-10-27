"""Self-serve sign-up (docs/signup-round/contract.md). Digests and masked labels, never secrets.

No login code, ID token, name, photo, phone number in clear, or message text is stored here.
"""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base


class UserIdentity(Base):
    """A Google account that signs in to one household: sha256 of `google:<sub>` only."""

    __tablename__ = "user_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject_sha256"),
        CheckConstraint("provider IN ('google')", name="provider"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(Text)
    subject_sha256: Mapped[str] = mapped_column(Text)
    email_masked: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoginRequest(Base):
    """One "Continue with WhatsApp" attempt, bound to the browser that started it."""

    __tablename__ = "login_requests"
    __table_args__ = (
        CheckConstraint("purpose IN ('sign_in','link')", name="purpose"),
        CheckConstraint("state IN ('pending','confirmed','declined','used')", name="state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code_digest: Mapped[str] = mapped_column(Text, unique=True)
    nonce_digest: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, server_default="pending")
    # Linking: the signed-in household. Signing in: the household that confirmed.
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    binding_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("whatsapp_bindings.id", ondelete="CASCADE"), index=True
    )
    device: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SignupWaitlist(Base):
    """A number that sent JOIN while FinBoy was full: an HMAC to find it, Fernet to reach it."""

    __tablename__ = "signup_waitlist"
    __table_args__ = (CheckConstraint("language IN ('en','hi','ml')", name="language"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    sender_hash: Mapped[str] = mapped_column(Text, unique=True)
    encrypted_sender: Mapped[bytes] = mapped_column(LargeBinary)
    language: Mapped[str | None] = mapped_column(Text)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UsageCounter(Base):
    """AI and voice requests per household per IST day; counts only."""

    __tablename__ = "usage_counters"
    __table_args__ = (CheckConstraint("kind IN ('ai','voice')", name="kind"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
