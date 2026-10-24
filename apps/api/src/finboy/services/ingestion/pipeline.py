"""One durable transaction per email; bounded extraction before serial reconciliation."""

import hashlib
import os
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from itertools import islice
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from finboy.core.clock import now_ist
from finboy.core.config import Settings
from finboy.db.models.ledger import EmailSource, ExtractionCache, SourceEvent, Transaction
from finboy.db.models.mail import ImportRun, MailConnection
from finboy.services.ingestion.classifier import classify, trusted_domain
from finboy.services.ingestion.extract import Prepared
from finboy.services.ingestion.llm import (
    ExtractionUnavailable,
    LLMResult,
    cache_key,
    cassette_extract,
    live_extract,
    merge_evidence,
    supported_events,
)
from finboy.services.ingestion.normalize import normalize
from finboy.services.ingestion.rules import extract_rules
from finboy.services.ingestion.types import Extraction
from finboy.services.ledger.persist import persist_event


@dataclass(frozen=True)
class InboundMessage:
    source: Literal["gmail", "eml_upload", "demo_mailbox"]
    provider_message_id: str
    raw_rfc822: bytes
    received_at: datetime | None = None
    mail_connection_id: UUID | None = None
    failure_reason: Literal["message_unavailable"] | None = None


@dataclass
class IngestionStats:
    headers_checked: int = 0
    candidates_found: int = 0
    emails_processed: int = 0
    events_extracted: int = 0
    transactions_created: int = 0
    duplicates_merged: int = 0
    needs_review: int = 0
    non_financial_skipped: int = 0
    failed: int = 0


def _prepare(
    factory: sessionmaker[Session], inbound: InboundMessage, settings: Settings
) -> Prepared | None:
    try:
        if inbound.failure_reason:
            return None
        message = normalize(inbound.raw_rfc822, inbound.received_at)
        classification = classify(message)
        trusted = trusted_domain(message.sender_domain)
        if classification in {"non_financial", "promotional"}:
            return Prepared(message, classification, Extraction(not_transaction=True), trusted)
        rules = extract_rules(message)
        if rules.not_transaction:
            return Prepared(message, classification, rules, trusted)
        mode = os.environ.get("FINBOY_EXTRACTION_MODE", "live")
        model = settings.openai_extraction_model
        key = settings.openai_api_key
        if (
            mode == "rules"
            or not model
            or mode != "offline"
            and (key is None or not key.get_secret_value())
        ):
            return Prepared(message, classification, rules, trusted)
        cache_id = ("demo:" if inbound.source == "demo_mailbox" else "household:") + cache_key(
            message, model
        )
        with factory() as session:
            cached = session.scalar(
                select(ExtractionCache).where(ExtractionCache.cache_key == cache_id)
            )
            result = LLMResult.model_validate(cached.result) if cached else None
        if result is None:
            try:
                result = (
                    cassette_extract(message, model)
                    if mode == "offline"
                    else live_extract(message, settings)
                )
            except ExtractionUnavailable:
                return Prepared(message, classification, rules, trusted)
            with factory.begin() as session:
                session.execute(
                    insert(ExtractionCache)
                    .values(cache_key=cache_id, result=result.model_dump(mode="json"))
                    .on_conflict_do_nothing(index_elements=[ExtractionCache.cache_key])
                )
        extraction = merge_evidence(rules, supported_events(result, message))
        return Prepared(message, classification, extraction, trusted, result)
    except Exception:
        # The caller persists fixed failure state. Exception strings may contain private text.
        return None


def _user_lock(session: Session, user_id: UUID) -> None:
    value = int.from_bytes(hashlib.sha256(user_id.bytes).digest()[:8], "big", signed=True)
    session.execute(select(func.pg_advisory_xact_lock(value)))


def _persist_message(
    session: Session,
    *,
    user_id: UUID,
    import_run_id: UUID,
    inbound: InboundMessage,
    item: Prepared | None,
) -> tuple[IngestionStats, set[UUID]]:
    delta = IngestionStats(emails_processed=1)
    _user_lock(session, user_id)
    existing = session.scalar(
        select(EmailSource).where(
            EmailSource.user_id == user_id,
            EmailSource.source == inbound.source,
            EmailSource.provider_message_id == inbound.provider_message_id,
        )
    )
    if existing is not None and existing.processing_status != "failed":
        return delta, set()
    if (
        inbound.mail_connection_id is not None
        and session.scalar(
            select(MailConnection.id).where(
                MailConnection.id == inbound.mail_connection_id, MailConnection.user_id == user_id
            )
        )
        is None
    ):
        raise ValueError("mail_connection_not_found")
    source = EmailSource(
        user_id=user_id,
        import_run_id=import_run_id,
        mail_connection_id=inbound.mail_connection_id,
        source=inbound.source,
        provider_message_id=inbound.provider_message_id,
        content_sha256=item.message.content_sha256
        if item
        else hashlib.sha256(inbound.raw_rfc822).hexdigest(),
        sender_domain=item.message.sender_domain if item else "",
        subject_sha256=item.message.subject_sha256 if item else hashlib.sha256(b"").hexdigest(),
        received_at=item.message.received_at if item and item.message.received_at else now_ist(),
        classification=item.classification if item else "unknown",
        processing_status="failed"
        if item is None
        else "skipped"
        if item.extraction.not_transaction
        else "failed"
        if not item.extraction.events
        else "extracted",
    )
    if existing is not None:
        # Failed normalization/extraction has no committed events; keep the stable source ID.
        # A partially persisted event is not safe to retry by replacing evidence.
        if (
            session.scalar(
                select(SourceEvent.id).where(SourceEvent.email_source_id == existing.id).limit(1)
            )
            is not None
        ):
            return delta, set()
        for field in (
            "content_sha256",
            "sender_domain",
            "subject_sha256",
            "received_at",
            "classification",
            "processing_status",
        ):
            setattr(existing, field, getattr(source, field))
        existing.attempts += 1
        source = existing
    else:
        session.add(source)
    source.last_attempt_run_id = import_run_id
    source.issue_reason = (
        inbound.failure_reason or "extraction_failed"
        if item is None
        else "no_supported_events"
        if source.processing_status == "failed"
        else None
    )
    session.flush()
    if item is None:
        delta.failed = 1
    elif item.extraction.not_transaction:
        delta.non_financial_skipped = 1
    elif not item.extraction.events:
        # No positive amount/direction claim exists to put into a ledger review row.
        delta.candidates_found = 1
        delta.failed = 1
    else:
        delta.candidates_found = 1
        for event in item.extraction.events:
            created, duplicate = persist_event(
                session,
                user_id=user_id,
                source=source,
                event=event,
                fallback_time=source.received_at,
            )
            delta.events_extracted += 1
            delta.transactions_created += int(created)
            delta.duplicates_merged += int(duplicate)
    session.flush()
    touched = set(
        session.scalars(
            select(SourceEvent.transaction_id).where(
                SourceEvent.email_source_id == source.id, SourceEvent.transaction_id.is_not(None)
            )
        )
    )
    return delta, touched


def ingest_messages(
    session_factory: sessionmaker[Session],
    *,
    user_id: UUID,
    import_run_id: UUID,
    messages: Iterable[InboundMessage],
    on_progress: Callable[[IngestionStats], None] | None = None,
    ensure_active: Callable[[], None] | None = None,
) -> IngestionStats:
    stats = IngestionStats()
    with session_factory() as session:
        run = session.scalar(
            select(ImportRun).where(ImportRun.id == import_run_id, ImportRun.user_id == user_id)
        )
        if run is None:
            raise ValueError("import_run_not_found")
    iterator = iter(messages)
    touched: set[UUID] = set()
    settings = Settings()
    with ThreadPoolExecutor(max_workers=4) as pool:
        while batch := list(islice(iterator, 4)):
            prepared = pool.map(lambda item: _prepare(session_factory, item, settings), batch)
            for inbound, item in zip(batch, prepared, strict=True):
                if ensure_active:
                    ensure_active()
                stats.headers_checked += 1
                try:
                    with session_factory.begin() as session:
                        delta, message_ids = _persist_message(
                            session,
                            user_id=user_id,
                            import_run_id=import_run_id,
                            inbound=inbound,
                            item=item,
                        )
                    # Counters advance only after the database commit succeeds.
                    for name, value in asdict(delta).items():
                        setattr(stats, name, getattr(stats, name) + value)
                    touched.update(message_ids)
                except Exception:
                    # Preserve a retryable source identity after a rolled-back extraction.
                    # An unavailable database may also prevent this fixed metadata write.
                    try:
                        with session_factory.begin() as failure_session:
                            _persist_message(
                                failure_session,
                                user_id=user_id,
                                import_run_id=import_run_id,
                                inbound=inbound,
                                item=None,
                            )
                    except Exception:
                        pass
                    stats.failed += 1
                    stats.emails_processed += 1
                with session_factory() as session:
                    stats.needs_review = (
                        session.scalar(
                            select(func.count())
                            .select_from(Transaction)
                            .where(
                                Transaction.user_id == user_id,
                                Transaction.id.in_(touched),
                                Transaction.status == "needs_review",
                            )
                        )
                        or 0
                    )
                if on_progress:
                    on_progress(replace(stats))
    return stats
