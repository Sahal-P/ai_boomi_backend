"""Admin panel accounts, sessions and audit (docs/admin-round/contract.md).

Passwords are scrypt hashes and session tokens are kept only as SHA-256 digests. The audit log
holds fixed action names and allowlisted details, never household content or contact details.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base

ACTIONS = (
    "login",
    "login_failed",
    "logout",
    "password_changed",
    "sessions_revoked",
    "admin_created",
    "admin_disabled",
    "admin_password_reset",
    "admin_enabled",
    "household_signed_out",
    "household_suspended",
    "household_restored",
    "household_erased",
    "premium_granted",
    "autopay_cancelled",
    "pay_link_created",
    "payment_reconciled",
    "signups_tidied",
)


class AdminUser(Base):
    __tablename__ = "admin_users"
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lower"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    # Set for a temporary password; until it is changed only the password route answers.
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sql("false")
    )
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default=sql("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("admin_users.id"))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AdminSession(Base):
    """One signed-in browser. The cookie holds a random token; only its digest is stored."""

    __tablename__ = "admin_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    admin_id: Mapped[UUID] = mapped_column(
        ForeignKey("admin_users.id", ondelete="CASCADE"), index=True
    )
    token_sha256: Mapped[str] = mapped_column(Text, unique=True)
    # A coarse label such as "Chrome · macOS", as household sign-in requests use.
    device: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminEvent(Base):
    """Who did what, and to which household. Survives the household's erasure."""

    __tablename__ = "admin_events"
    __table_args__ = (
        CheckConstraint(
            "action IN (" + ",".join(f"'{action}'" for action in ACTIONS) + ")", name="action"
        ),
        Index("ix_admin_events_created_at", "created_at"),
        Index("ix_admin_events_household_id", "household_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # Empty for a failed sign-in with an unknown email (which is not stored) and server commands.
    admin_id: Mapped[UUID | None] = mapped_column(ForeignKey("admin_users.id"))
    action: Mapped[str] = mapped_column(Text)
    # A plain UUID, not a foreign key, so the entry outlives an erased household's data.
    household_id: Mapped[UUID | None] = mapped_column()
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sql("'{}'::jsonb"))
    request_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
