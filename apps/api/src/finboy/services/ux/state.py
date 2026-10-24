"""Snapshot tokens and honest manual-scan coverage, with no provider content."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finboy.core.clock import today_ist
from finboy.db.models.core import User
from finboy.db.models.ledger import Commitment, EmailSource, Transaction
from finboy.db.models.mail import ImportRun


class TaskError(Exception):
    MESSAGES = {
        "source_lineage_unavailable": (
            409,
            "An older merge needs a source review before deletion. Your records were kept.",
        ),
        "not_found": (404, "This record is no longer available."),
        "version_conflict": (409, "Your records changed. Refresh and review the latest version."),
        "decision_conflict": (
            409,
            "Later changes prevent this undo. Reopen the current record instead.",
        ),
        "demo_read_only": (
            409,
            "View the isolated sample at /demo. Samples cannot be imported here.",
        ),
        "original_files_required": (
            409,
            "Select the original .eml files again to retry failed messages.",
        ),
        "source_unavailable": (
            503,
            "This source could not be refreshed. Try again or reconnect it.",
        ),
        "invalid_decision": (422, "These changes are incompatible. Review the selected fields."),
        "quarantined_record": (
            409,
            "Mixed sample evidence is isolated. Use source-aware recovery before reviewing.",
        ),
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self.MESSAGES else "invalid_decision"
        self.status, self.message = self.MESSAGES[self.code]
        super().__init__(self.code)


class Coverage(BaseModel):
    sync_mode: Literal["manual"] = "manual"
    last_successful_scan_at: datetime | None = None
    window_start: date | None = None
    window_end: date | None = None
    state: Literal["unknown", "partial", "scanned"] = "unknown"
    truncated: bool = False
    pending_review_count: int = 0
    failed_source_count: int = 0
    active_import_id: UUID | None = None
    quarantined_count: int = 0


def data_version(session: Session, user_id: UUID) -> str:
    value = session.scalar(select(User.data_version).where(User.id == user_id))
    return f"{value if isinstance(value, int) else 0}:{today_ist().isoformat()}"


def lock_snapshot(session: Session, user_id: UUID) -> str:
    value = session.scalar(
        select(User.data_version).where(User.id == user_id).with_for_update(read=True)
    )
    return f"{value if isinstance(value, int) else 0}:{today_ist().isoformat()}"


def require_version(session: Session, user_id: UUID, expected: str) -> str:
    # Same user lock/order as ingestion and legacy review, then lock the version row.
    from finboy.services.ingestion.pipeline import _user_lock

    _user_lock(session, user_id)
    value = session.scalar(select(User.data_version).where(User.id == user_id).with_for_update())
    if value is None:
        raise TaskError("not_found")
    if f"{value}:{today_ist().isoformat()}" != expected:
        raise TaskError("version_conflict")
    return expected


def coverage(session: Session, user_id: UUID) -> Coverage:
    base = (
        select(ImportRun)
        .where(ImportRun.user_id == user_id, ImportRun.mode != "demo_mailbox")
        .order_by(ImportRun.started_at.desc().nullslast(), ImportRun.id.desc())
    )
    normal = base.where(ImportRun.mode == "gmail", ImportRun.retry_source_ids == [])
    latest = session.scalar(normal.limit(1))
    successful = session.scalar(normal.where(ImportRun.status == "completed").limit(1))
    active = session.scalar(base.where(ImportRun.status.in_(["queued", "running"])).limit(1))
    pending = (
        session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.dataset == "household",
                Transaction.status == "needs_review",
            )
        )
        or 0
    )
    failed = (
        session.scalar(
            select(func.count())
            .select_from(EmailSource)
            .where(
                EmailSource.user_id == user_id,
                EmailSource.source != "demo_mailbox",
                EmailSource.processing_status == "failed",
            )
        )
        or 0
    )
    quarantined = (
        session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.user_id == user_id, Transaction.dataset == "quarantined")
        )
        or 0
    ) + (
        session.scalar(
            select(func.count())
            .select_from(Commitment)
            .where(Commitment.user_id == user_id, Commitment.dataset == "quarantined")
        )
        or 0
    )
    return Coverage(
        last_successful_scan_at=successful.finished_at if successful else None,
        window_start=latest.window_start if latest else None,
        window_end=latest.window_end if latest else None,
        state="unknown"
        if latest is None or latest.window_start is None or latest.window_end is None
        else "partial"
        if latest.status != "completed" or latest.failed or latest.truncated
        else "scanned",
        truncated=bool(latest.truncated) if latest else False,
        pending_review_count=pending,
        failed_source_count=failed,
        active_import_id=active.id if active else None,
        quarantined_count=quarantined,
    )
