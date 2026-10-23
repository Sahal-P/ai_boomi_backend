"""Remove source-backed data without erasing operational audit history."""

from uuid import UUID

from finboy.core.clock import now_ist
from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.ledger import (
    Commitment,
    EmailSource,
    ExtractionCache,
    SourceEvent,
    Transaction,
    TransactionRevision,
)
from finboy.db.models.mail import ImportRun
from finboy.services.privacy.audit import audit
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session


def delete_imported_data(session: Session, *, connection_id: UUID | None = None) -> None:
    source_filter = [EmailSource.user_id == LOCAL_USER_ID]
    if connection_id is not None:
        source_filter.append(EmailSource.mail_connection_id == connection_id)
    sources = select(EmailSource.id).where(*source_filter)
    events = select(SourceEvent.id).where(
        SourceEvent.email_source_id.in_(sources), SourceEvent.user_id == LOCAL_USER_ID
    )
    affected_transactions = set(
        session.scalars(
            select(SourceEvent.transaction_id).where(
                SourceEvent.id.in_(events), SourceEvent.transaction_id.is_not(None)
            )
        )
    )
    # Commitments must precede event/source removal because the FK is not cascading.
    session.execute(
        delete(Commitment).where(
            Commitment.user_id == LOCAL_USER_ID, Commitment.source_event_id.in_(events)
        )
    )
    session.execute(delete(SourceEvent).where(SourceEvent.id.in_(events)))
    session.execute(delete(EmailSource).where(*source_filter))
    remaining = select(SourceEvent.transaction_id).where(SourceEvent.transaction_id.is_not(None))
    orphans = list(
        session.scalars(
            select(Transaction.id).where(
                Transaction.user_id == LOCAL_USER_ID,
                Transaction.id.in_(affected_transactions),
                Transaction.id.not_in(remaining),
            )
        )
    )
    if orphans:
        session.execute(
            update(Commitment)
            .where(Commitment.user_id == LOCAL_USER_ID, Commitment.paid_transaction_id.in_(orphans))
            .values(paid_transaction_id=None)
        )
        for column in (
            Transaction.linked_transaction_id,
            Transaction.merged_into_id,
            Transaction.possible_duplicate_of_id,
        ):
            session.execute(
                update(Transaction)
                .where(Transaction.user_id == LOCAL_USER_ID, column.in_(orphans))
                .values({column: None})
            )
        session.execute(
            delete(TransactionRevision).where(TransactionRevision.transaction_id.in_(orphans))
        )
        session.execute(
            delete(Transaction).where(
                Transaction.id.in_(orphans), Transaction.user_id == LOCAL_USER_ID
            )
        )
    # The cache has no source/user FK; this single-user app must clear it on privacy deletion.
    session.execute(delete(ExtractionCache))
    runs = [ImportRun.user_id == LOCAL_USER_ID, ImportRun.status.in_(["queued", "running"])]
    if connection_id:
        runs.append(ImportRun.mail_connection_id == connection_id)
    session.execute(
        update(ImportRun)
        .where(*runs)
        .values(status="failed", error_code="import_cancelled", finished_at=now_ist())
    )
    audit(
        session,
        "data.deleted",
        "connection" if connection_id else "user",
        connection_id or LOCAL_USER_ID,
    )
