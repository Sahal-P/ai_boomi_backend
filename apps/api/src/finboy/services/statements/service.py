"""Statement imports as runs: started by an upload or a WhatsApp document, removable on the web.

docs/statement-round/contract.md. A statement is read and checked before anything is saved; one that
doesn't add up to its own totals becomes a failed run that shows what was found, with no records.
"""

import logging
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from finboy.core.clock import now_ist
from finboy.core.config import Settings
from finboy.db.models.ledger import EmailSource
from finboy.db.models.mail import ImportRun
from finboy.db.models.statements import StatementImport
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.services.imports.locking import import_lock
from finboy.services.imports.runner import _lock_owner, create_run
from finboy.services.mail.security import MailError
from finboy.services.privacy.audit import audit
from finboy.services.privacy.delete import delete_imported_data
from finboy.services.privacy.scope import transaction_impact
from finboy.services.statements.gpay import Statement
from finboy.services.statements.persist import save_statement, statement_record
from finboy.services.statements.views import RemovalPreview
from finboy.services.ux.state import TaskError, data_version
from finboy.services.whatsapp.config import ChannelUnavailable, channel_config

logger = logging.getLogger(__name__)
MODE = "gpay_statement"


def holder_matches(
    session: Session, settings: Settings, user_id: UUID, phone: str | None
) -> bool | None:
    """Whether the statement's number is the household's WhatsApp number.

    Only the answer is kept; the number itself is never stored.
    """
    if phone is None:
        return None
    try:
        config = channel_config(settings)
    except ChannelUnavailable:
        return None
    hashes = set(
        session.scalars(
            select(WhatsAppBinding.sender_hash).where(WhatsAppBinding.user_id == user_id)
        )
    )
    return config.digest("sender", f"91{phone}") in hashes if hashes else None


def already_imported(session: Session, user_id: UUID, file_sha256: str) -> bool:
    return (
        session.scalar(
            select(StatementImport.import_run_id)
            .where(
                StatementImport.user_id == user_id,
                StatementImport.file_sha256 == file_sha256,
                StatementImport.reconciled.is_(True),
                StatementImport.removed_at.is_(None),
            )
            .limit(1)
        )
        is not None
    )


def start_import(
    session: Session,
    *,
    settings: Settings,
    user_id: UUID,
    statement: Statement,
    file_sha256: str,
) -> tuple[ImportRun, bool | None]:
    """Create the run. A statement that doesn't add up fails here and keeps what was found."""
    run = create_run(session, mode=MODE, user_id=user_id)
    run.window_start, run.window_end = statement.period_start, statement.period_end
    holder = holder_matches(session, settings, user_id, statement.phone)
    if not statement.reconciled:
        session.add(
            statement_record(
                user_id=user_id,
                run_id=run.id,
                statement=statement,
                file_sha256=file_sha256,
                holder_matches=holder,
            )
        )
        run.headers_checked = run.candidates_found = len(statement.rows)
        run.status, run.outcome_detail, run.error_code = "failed", "failed", "extraction_failed"
        run.finished_at = now_ist()
        audit(session, "import.failed", "import", run.id, user_id=user_id, mode=MODE)
    session.commit()
    return run, holder


def _finish(run: ImportRun, record: StatementImport) -> None:
    rows = record.rows_total
    run.headers_checked = run.candidates_found = run.emails_processed = rows
    run.events_extracted = rows - record.rows_already_imported
    run.transactions_created = (
        record.rows_new + record.rows_possible_duplicate + record.rows_not_counted
    )
    run.duplicates_merged = record.rows_linked
    run.needs_review = record.rows_possible_duplicate + record.rows_not_counted
    run.status, run.outcome_detail, run.finished_at = "completed", "complete", now_ist()


def run_statement_import(
    engine: Engine,
    run_id: UUID,
    statement: Statement,
    *,
    file_sha256: str,
    holder: bool | None,
) -> None:
    """Save every row in one transaction, under the household's import lock."""
    factory = sessionmaker(engine, expire_on_commit=False)
    try:
        with factory() as session:
            owner = session.scalar(select(ImportRun.user_id).where(ImportRun.id == run_id))
        if owner is None:
            return
        with import_lock(engine, _lock_owner(owner)):
            with factory.begin() as session:
                run = session.get(ImportRun, run_id)
                if run is None or run.status != "queued":
                    return
                run.status, run.started_at = "running", now_ist()
            with factory.begin() as session:
                run = session.get(ImportRun, run_id)
                if run is None or run.status != "running" or run.cancel_requested:
                    raise MailError("import_cancelled")
                record = save_statement(
                    session,
                    user_id=owner,
                    run_id=run_id,
                    record=statement_record(
                        user_id=owner,
                        run_id=run_id,
                        statement=statement,
                        file_sha256=file_sha256,
                        holder_matches=holder,
                    ),
                    statement=statement,
                )
                _finish(run, record)
                audit(session, "import.completed", "import", run.id, user_id=owner, mode=MODE)
    except Exception as exc:
        code = exc.code if isinstance(exc, MailError) else "import_failed"
        try:
            with factory.begin() as session:
                run = session.get(ImportRun, run_id)
                if run is not None and run.status in {"queued", "running"}:
                    run.outcome_detail = "cancelled" if code == "import_cancelled" else "failed"
                    run.status, run.error_code, run.finished_at = (
                        "failed",
                        "import_failed",
                        now_ist(),
                    )
                    audit(
                        session, "import.failed", "import", run.id, user_id=run.user_id, mode=MODE
                    )
        except Exception as persistence_error:
            # Background work runs after the response; exception text may quote private data.
            logger.error(
                "import.failure_record_unavailable",
                extra={
                    "import_run_id": str(run_id),
                    "error_type": type(persistence_error).__name__,
                },
            )


def _removable(session: Session, user_id: UUID, run_id: UUID) -> StatementImport:
    record = session.scalar(
        select(StatementImport).where(
            StatementImport.import_run_id == run_id, StatementImport.user_id == user_id
        )
    )
    run = session.get(ImportRun, run_id)
    if record is None or run is None or run.user_id != user_id or run.mode != MODE:
        raise TaskError("not_found")
    if record.removed_at is not None or run.status != "completed":
        raise TaskError("invalid_decision")
    return record


def _sources(session: Session, user_id: UUID, run_id: UUID) -> set[UUID]:
    return set(
        session.scalars(
            select(EmailSource.id).where(
                EmailSource.user_id == user_id, EmailSource.import_run_id == run_id
            )
        )
    )


def removal_preview(session: Session, *, user_id: UUID, run_id: UUID) -> RemovalPreview:
    _removable(session, user_id, run_id)
    impact = transaction_impact(
        session, user_id=user_id, source_ids=_sources(session, user_id, run_id)
    )
    return RemovalPreview(
        records_removed=len(impact.removed),
        records_kept=len(impact.affected - impact.removed),
        data_version=data_version(session, user_id),
    )


def remove_statement(session: Session, *, user_id: UUID, run_id: UUID) -> None:
    """Undo one statement: what only it supports goes; records with other evidence stay."""
    record = _removable(session, user_id, run_id)
    delete_imported_data(session, user_id=user_id, import_run_id=run_id)
    record.removed_at = now_ist()
    session.flush()
