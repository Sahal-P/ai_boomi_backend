from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True)
class InboundMessage:
    source: Literal["gmail", "eml_upload", "demo_mailbox"]
    provider_message_id: str
    raw_rfc822: bytes
    received_at: datetime | None = None
    mail_connection_id: UUID | None = None


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


def ingest_messages(
    session_factory: sessionmaker[Session],
    *,
    user_id: UUID,
    import_run_id: UUID,
    messages: Iterable[InboundMessage],
    on_progress: Callable[[IngestionStats], None] | None = None,
) -> IngestionStats:
    raise NotImplementedError
