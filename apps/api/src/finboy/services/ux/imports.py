"""Recoverable source failures and durable operational import outcomes."""

from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import Engine, func, or_, select
from sqlalchemy.orm import Session

from finboy.core.clock import now_ist
from finboy.db.models.ledger import EmailSource, SourceEvent, Transaction
from finboy.db.models.mail import ImportRun, MailConnection
from finboy.services.imports.locking import import_lock
from finboy.services.mail.security import MailError
from finboy.services.ux.decisions import VersionRequest
from finboy.services.ux.state import TaskError, data_version, require_version


class ImportView(BaseModel):
    id: UUID
    mode: str
    status: str
    headers_checked: int
    candidates_found: int
    emails_processed: int
    events_extracted: int
    transactions_created: int
    duplicates_merged: int
    needs_review: int
    non_financial_skipped: int
    failed: int
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None
    outcome: Literal[
        "queued", "running", "complete", "partial", "failed", "interrupted", "cancelled"
    ]
    retryable: bool
    retry_strategy: Literal["refetch_gmail", "select_original_files", "none"]
    cancel_requested: bool
    window_start: str | None
    window_end: str | None
    truncated: bool
    can_continue: bool
    data_version: str


class RetryRequest(VersionRequest):
    source_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=50)


def run_for(session: Session, run_id: UUID, user_id: UUID) -> ImportRun:
    row = session.scalar(
        select(ImportRun).where(
            ImportRun.id == run_id, ImportRun.user_id == user_id, ImportRun.mode != "demo_mailbox"
        )
    )
    if row is None:
        raise TaskError("not_found")
    return row


def import_view(session: Session, row: ImportRun) -> ImportView:
    outcome = row.outcome_detail or ("complete" if row.status == "completed" else row.status)
    if row.status == "completed" and (row.failed or row.truncated):
        outcome = "partial"
    failures = (
        session.scalar(
            select(func.count())
            .select_from(EmailSource)
            .where(
                EmailSource.user_id == row.user_id,
                or_(EmailSource.import_run_id == row.id, EmailSource.last_attempt_run_id == row.id),
                EmailSource.processing_status == "failed",
            )
        )
        or 0
    )
    connection = (
        session.get(MailConnection, row.mail_connection_id) if row.mail_connection_id else None
    )
    can_retry = outcome in {"partial", "failed", "interrupted", "cancelled"} and (
        row.mode == "eml_upload" or bool(failures and connection and connection.status == "active")
    )
    pending = (
        session.scalar(
            select(func.count(func.distinct(SourceEvent.transaction_id)))
            .join(EmailSource, EmailSource.id == SourceEvent.email_source_id)
            .join(Transaction, Transaction.id == SourceEvent.transaction_id)
            .where(
                SourceEvent.user_id == row.user_id,
                EmailSource.user_id == row.user_id,
                or_(EmailSource.import_run_id == row.id, EmailSource.last_attempt_run_id == row.id),
                EmailSource.source != "demo_mailbox",
                Transaction.dataset == "household",
                Transaction.status == "needs_review",
            )
        )
        or 0
    )
    return ImportView.model_validate(
        {
            **{
                name: getattr(row, name)
                for name in (
                    "id",
                    "mode",
                    "status",
                    "headers_checked",
                    "candidates_found",
                    "emails_processed",
                    "events_extracted",
                    "transactions_created",
                    "duplicates_merged",
                    "needs_review",
                    "non_financial_skipped",
                    "failed",
                    "error_code",
                    "started_at",
                    "finished_at",
                    "cancel_requested",
                    "truncated",
                )
            },
            "needs_review": pending,
            "outcome": outcome,
            "can_continue": bool(
                row.truncated and row.next_page_token_encrypted and row.status == "completed"
            ),
            "retryable": can_retry,
            "retry_strategy": "refetch_gmail"
            if row.mode == "gmail" and can_retry
            else "select_original_files"
            if can_retry
            else "none",
            "window_start": row.window_start.isoformat() if row.window_start else None,
            "window_end": row.window_end.isoformat() if row.window_end else None,
            "data_version": data_version(session, row.user_id),
        }
    )


def recover_interrupted(session: Session, engine: Engine, user_id: UUID) -> None:
    rows = list(
        session.scalars(
            select(ImportRun).where(
                ImportRun.user_id == user_id,
                ImportRun.mode != "demo_mailbox",
                ImportRun.status.in_(["queued", "running"]),
                ImportRun.started_at < now_ist() - timedelta(seconds=30),
            )
        )
    )
    if not rows:
        return
    try:
        with import_lock(engine):
            # A live worker owns the session lock, including slow provider requests.
            for row in rows:
                row.status, row.outcome_detail, row.error_code, row.finished_at = (
                    "failed",
                    "interrupted",
                    "import_failed",
                    now_ist(),
                )
            session.commit()
    except MailError:
        pass


def issues(session: Session, *, user_id: UUID, run_id: UUID, limit: int, offset: int) -> dict:
    run_for(session, run_id, user_id)
    condition = [
        EmailSource.user_id == user_id,
        or_(EmailSource.import_run_id == run_id, EmailSource.last_attempt_run_id == run_id),
        EmailSource.processing_status == "failed",
        EmailSource.source != "demo_mailbox",
    ]
    total = session.scalar(select(func.count()).select_from(EmailSource).where(*condition)) or 0
    rows = list(
        session.scalars(
            select(EmailSource)
            .where(*condition)
            .order_by(EmailSource.id)
            .limit(limit)
            .offset(offset)
        )
    )
    items = [
        {
            "id": row.id,
            "source_id": row.id,
            "source_mode": row.source,
            "reason": row.issue_reason or "extraction_failed",
            # Screenshots are never retained; the sender resends them on WhatsApp instead.
            "retryable": row.source != "whatsapp_image",
            "retry_strategy": "refetch_gmail"
            if row.source == "gmail"
            else "none"
            if row.source == "whatsapp_image"
            else "select_original_files",
            "attempts": row.attempts,
        }
        for row in rows
    ]
    return {
        "items": items,
        "total": total,
        "next_offset": offset + len(items) if offset + len(items) < total else None,
    }


def retry_sources(
    session: Session, *, user_id: UUID, run_id: UUID, request: RetryRequest
) -> tuple[ImportRun, list[UUID]]:
    require_version(session, user_id, request.expected_version)
    row = run_for(session, run_id, user_id)
    if row.mode != "gmail":
        raise TaskError("original_files_required")
    if row.status in {"running", "queued"}:
        raise TaskError("invalid_decision")
    connection = session.scalar(
        select(MailConnection).where(
            MailConnection.id == row.mail_connection_id,
            MailConnection.user_id == user_id,
            MailConnection.status == "active",
        )
    )
    if connection is None:
        raise TaskError("source_unavailable")
    conditions = [
        EmailSource.user_id == user_id,
        or_(EmailSource.import_run_id == run_id, EmailSource.last_attempt_run_id == run_id),
        EmailSource.source == "gmail",
        EmailSource.processing_status == "failed",
        EmailSource.mail_connection_id == connection.id,
    ]
    if request.source_ids:
        conditions.append(EmailSource.id.in_(request.source_ids))
    selected = list(
        session.scalars(
            select(EmailSource.id).where(*conditions).order_by(EmailSource.id).limit(50)
        )
    )
    if not selected or (request.source_ids and set(selected) != set(request.source_ids)):
        raise TaskError("not_found")
    return row, selected
