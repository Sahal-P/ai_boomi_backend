"""Background import orchestration; all progress writes use independent sessions."""

import logging
from collections.abc import Iterable, Iterator
from datetime import date, timedelta
from uuid import UUID, uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from finboy.core.clock import now_ist
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.db.models.mail import ImportRun, MailConnection
from finboy.services.imports.locking import import_lock
from finboy.services.ingestion.pipeline import InboundMessage, IngestionStats, ingest_messages
from finboy.services.mail.fetch import fetch_messages
from finboy.services.mail.oauth import OAuthConfig
from finboy.services.mail.security import MailError, decrypt, encrypt
from finboy.services.privacy.audit import audit

COUNTERS = tuple(IngestionStats.__dataclass_fields__)
logger = logging.getLogger(__name__)


def stored_error(code: str) -> str:
    if code == "gmail_not_configured":
        return "configuration_missing"
    if code in {"reconnect_required", "connection_inactive", "scope_missing"}:
        return "authorization_failed"
    if code == "gmail_unavailable":
        return "provider_unavailable"
    return "import_failed"


def create_run(
    session: Session,
    *,
    mode: str,
    connection_id: UUID | None = None,
    user_id: UUID = LOCAL_USER_ID,
) -> ImportRun:
    # Serializes admission for this household's runs (including simultaneous HTTP requests).
    # Existing active jobs are not duplicated by repeated clicks.
    from finboy.db.models.core import User

    session.scalar(select(User).where(User.id == user_id).with_for_update())
    existing = session.scalar(
        select(ImportRun).where(
            ImportRun.user_id == user_id, ImportRun.status.in_(["queued", "running"])
        )
    )
    if existing:
        stale = session.scalar(
            select(ImportRun.id).where(
                ImportRun.id == existing.id,
                ImportRun.started_at <= now_ist() - timedelta(seconds=30),
            )
        )
        if existing.status == "queued" and not stale:
            raise MailError("import_busy")
        # The worker holds this lock throughout ingestion. If it is absent, this is
        # interrupted work from a stopped process, not an active extractor.
        with import_lock(session.get_bind().engine, user_id):
            existing.status = "failed"
            existing.outcome_detail = "interrupted"
            existing.error_code = "import_failed"
            existing.finished_at = now_ist()
            audit(
                session, "import.failed", "import", existing.id, user_id=user_id, mode=existing.mode
            )
    run = ImportRun(
        id=uuid4(),
        user_id=user_id,
        mode=mode,
        mail_connection_id=connection_id,
        status="queued",
        started_at=now_ist(),
    )
    session.add(run)
    session.flush()
    audit(session, "import.started", "import", run.id, user_id=user_id, mode=mode)
    session.commit()
    return run


def run_import(
    engine: Engine,
    settings: Settings,
    run_id: UUID,
    messages: Iterable[InboundMessage] | None = None,
) -> None:
    factory = sessionmaker(engine, expire_on_commit=False)
    scanned = [0, 0]

    def progress(stats: IngestionStats) -> None:
        with factory.begin() as session:
            run = session.get(ImportRun, run_id)
            if run is None or run.status != "running":
                raise MailError("import_cancelled")
            for counter in COUNTERS:
                value = max(0, getattr(stats, counter))
                if counter == "headers_checked":
                    value = max(value, scanned[0])
                elif counter == "candidates_found":
                    value = max(value, scanned[1])
                setattr(run, counter, max(getattr(run, counter), value))

    def scan(headers: int, candidates: int) -> None:
        scanned[:] = [headers, candidates]
        progress(IngestionStats())

    def scan_coverage(
        start: date, end: date, truncated: bool, next_page: str | None = None
    ) -> None:
        with factory.begin() as session:
            run = session.get(ImportRun, run_id)
            if run is not None:
                run.window_start, run.window_end, run.truncated = start, end, truncated
                run.next_page_token_encrypted = (
                    encrypt(settings.token_encryption_key.get_secret_value(), next_page)
                    if next_page
                    else None
                )

    def active() -> None:
        with factory() as session:
            run = session.get(ImportRun, run_id)
            if run is None or run.status != "running" or run.cancel_requested:
                raise MailError("import_cancelled")
            if run.mail_connection_id:
                connection = session.get(MailConnection, run.mail_connection_id)
                if connection is None or connection.status != "active":
                    raise MailError("import_cancelled")

    def guarded(inbound: Iterable[InboundMessage]) -> Iterator[InboundMessage]:
        for message in inbound:
            active()
            yield message

    google = None
    try:
        with factory() as session:
            # The run names its household; pilot captures never touch the owner's records.
            owner = session.scalar(select(ImportRun.user_id).where(ImportRun.id == run_id))
        if owner is None:
            return
        with import_lock(engine, owner):
            with factory.begin() as session:
                run = session.get(ImportRun, run_id)
                if run is None or run.status != "queued":
                    return
                run.status = "running"
                run.started_at = now_ist()
                connection_id = run.mail_connection_id
                if connection_id:
                    config = OAuthConfig.from_settings(settings)
                    connection = session.get(MailConnection, connection_id)
                    if (
                        connection is None
                        or connection.status != "active"
                        or connection.encrypted_refresh_token is None
                    ):
                        raise MailError("connection_inactive")
                    refresh_token = decrypt(
                        config.encryption_key, connection.encrypted_refresh_token
                    )
                    google = config.google()
                    retry_ids = list(run.retry_source_ids)
                    resume_token = (
                        decrypt(config.encryption_key, run.resume_page_token_encrypted)
                        if run.resume_page_token_encrypted
                        else ""
                    )
                    messages = fetch_messages(
                        google,
                        refresh_token=refresh_token,
                        connection_id=connection_id,
                        on_scan=scan,
                        ensure_active=active,
                        source_ids=retry_ids,
                        factory=factory,
                        on_coverage=scan_coverage,
                        page_token=resume_token,
                        window_start=run.window_start,
                        window_end=run.window_end,
                    )
            if messages is None:
                raise MailError("import_failed")
            stats = ingest_messages(
                factory,
                user_id=owner,
                import_run_id=run_id,
                messages=guarded(messages),
                on_progress=progress,
                ensure_active=active,
            )
            progress(stats)
            active()
            with factory.begin() as session:
                run = session.get(ImportRun, run_id)
                if run is None:
                    return
                run.status = "completed"
                run.outcome_detail = "partial" if run.failed or run.truncated else "complete"
                run.finished_at = now_ist()
                if run.mail_connection_id and not run.retry_source_ids:
                    connection = session.get(MailConnection, run.mail_connection_id)
                    if connection is not None:
                        connection.last_synced_at = now_ist()
                audit(session, "import.completed", "import", run.id, user_id=owner, mode=run.mode)
    except Exception as exc:
        code = exc.code if isinstance(exc, MailError) else "import_failed"
        try:
            with factory.begin() as session:
                run = session.get(ImportRun, run_id)
                if run is not None:
                    run.outcome_detail = "cancelled" if code == "import_cancelled" else "failed"
                    run.status, run.error_code, run.finished_at = (
                        "failed",
                        stored_error(code),
                        now_ist(),
                    )
                    audit(
                        session,
                        "import.failed",
                        "import",
                        run.id,
                        user_id=run.user_id,
                        mode=run.mode,
                    )
                    if code == "reconnect_required" and run.mail_connection_id:
                        connection = session.get(MailConnection, run.mail_connection_id)
                        if connection and connection.status not in {"revoked", "paused"}:
                            connection.status = "error"
                            audit(session, "gmail.reconnect_required", "connection", connection.id)
        except Exception as persistence_error:
            # BackgroundTasks exceptions run after the HTTP response. Contain them
            # here so Uvicorn cannot print chained provider/database exception text.
            logger.error(
                "import.failure_record_unavailable",
                extra={
                    "import_run_id": str(run_id),
                    "error_type": type(persistence_error).__name__,
                },
            )
    finally:
        if google:
            try:
                google.close()
            except Exception:
                logger.error("import.client_close_failed", extra={"import_run_id": str(run_id)})
