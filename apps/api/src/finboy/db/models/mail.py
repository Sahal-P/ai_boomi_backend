from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, LargeBinary, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base


class MailConnection(Base):
    __tablename__ = "mail_connections"
    __table_args__ = (
        CheckConstraint("provider = 'gmail'", name="provider"),
        CheckConstraint("status IN ('active','paused','revoked','error')", name="status"),
        Index("ix_mail_connections_user_id_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(Text)
    account_email_masked: Mapped[str] = mapped_column(Text)
    account_email_sha256: Mapped[str] = mapped_column(Text)
    encrypted_refresh_token: Mapped[bytes | None] = mapped_column(LargeBinary)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    status: Mapped[str] = mapped_column(Text)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthState(Base):
    __tablename__ = "oauth_states"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    state_sha256: Mapped[str] = mapped_column(Text, unique=True)
    encrypted_code_verifier: Mapped[bytes] = mapped_column(LargeBinary)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImportRun(Base):
    __tablename__ = "import_runs"
    __table_args__ = (
        CheckConstraint("mode IN ('gmail','eml_upload','demo_mailbox')", name="mode"),
        CheckConstraint("status IN ('queued','running','completed','failed')", name="status"),
        CheckConstraint(
            "headers_checked >= 0 AND candidates_found >= 0 AND emails_processed >= 0 "
            "AND events_extracted >= 0 AND transactions_created >= 0 AND duplicates_merged >= 0 "
            "AND needs_review >= 0 AND non_financial_skipped >= 0 AND failed >= 0",
            name="counters",
        ),
        CheckConstraint(
            "error_code IN ('configuration_missing','authorization_failed','provider_unavailable',"
            "'invalid_upload','extraction_failed','import_failed')",
            name="error_code",
        ),
        Index("ix_import_runs_user_id_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    mode: Mapped[str] = mapped_column(Text)
    mail_connection_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mail_connections.id"), index=True
    )
    status: Mapped[str] = mapped_column(Text)
    headers_checked: Mapped[int] = mapped_column(server_default=text("0"))
    candidates_found: Mapped[int] = mapped_column(server_default=text("0"))
    emails_processed: Mapped[int] = mapped_column(server_default=text("0"))
    events_extracted: Mapped[int] = mapped_column(server_default=text("0"))
    transactions_created: Mapped[int] = mapped_column(server_default=text("0"))
    duplicates_merged: Mapped[int] = mapped_column(server_default=text("0"))
    needs_review: Mapped[int] = mapped_column(server_default=text("0"))
    non_financial_skipped: Mapped[int] = mapped_column(server_default=text("0"))
    failed: Mapped[int] = mapped_column(server_default=text("0"))
    error_code: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(Text)
    subject_type: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[UUID] = mapped_column()
    # DeclarativeBase reserves the Python name `metadata`; the SQL column keeps its contract name.
    event_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
