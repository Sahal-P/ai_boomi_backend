"""Remove source-backed data without erasing operational audit history."""

from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

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
    # A canonical obligation may also be evidenced by a remaining import mode/account.
    # Re-anchor it before removing its first source; otherwise scoped disconnect could
    # erase a bill still supported by another imported notification.
    for commitment in session.scalars(
        select(Commitment).where(
            Commitment.user_id == LOCAL_USER_ID, Commitment.source_event_id.in_(events)
        )
    ):
        replacement = session.scalar(
            select(SourceEvent.id)
            .where(
                SourceEvent.user_id == LOCAL_USER_ID,
                SourceEvent.email_source_id.not_in(sources),
                SourceEvent.event_type == ("emi_due" if commitment.kind == "emi" else "bill_due"),
                SourceEvent.amount_minor == commitment.amount_minor,
                SourceEvent.currency == commitment.currency,
                SourceEvent.due_date == commitment.due_date,
                func.coalesce(SourceEvent.merchant_normalized, "Unidentified obligation")
                == commitment.label,
            )
            .order_by(SourceEvent.created_at, SourceEvent.id)
            .limit(1)
        )
        if replacement is None:
            session.delete(commitment)
        else:
            commitment.source_event_id = replacement
            remaining_source = session.scalar(
                select(EmailSource.source)
                .join(SourceEvent, SourceEvent.email_source_id == EmailSource.id)
                .where(SourceEvent.id == replacement)
            )
            if remaining_source == "demo_mailbox":
                commitment.dataset = "quarantined"
    session.flush()
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
    # Retained shared records may have canonical values chosen from removed evidence.
    # Preserve corrections/history while excluding those claims until source-aware repair.
    shared = affected_transactions - set(orphans)
    if shared:
        from finboy.services.ledger.categories import normalize_merchant
        from finboy.services.ledger.matching import direction, kind
        from finboy.services.ledger.persist import as_event, refresh_review_confidence

        for transaction in session.scalars(
            select(Transaction).where(
                Transaction.user_id == LOCAL_USER_ID, Transaction.id.in_(shared)
            )
        ):
            pairs = list(
                session.execute(
                    select(SourceEvent, EmailSource)
                    .join(EmailSource, EmailSource.id == SourceEvent.email_source_id)
                    .where(
                        SourceEvent.user_id == LOCAL_USER_ID,
                        SourceEvent.transaction_id == transaction.id,
                    )
                )
            )
            locked = set(transaction.user_locked_fields or [])
            supported = False
            for event, source in pairs:
                claim = as_event(event)
                values = {
                    "amount_minor": claim.amount_minor,
                    "direction": direction(claim),
                    "kind": kind(claim),
                    "merchant": normalize_merchant(claim.merchant) or "Unknown",
                    "occurred_at": claim.occurred_at or source.received_at,
                }
                if source.source != "demo_mailbox" and all(
                    field in locked or getattr(transaction, field) == value
                    for field, value in values.items()
                ):
                    supported = True
            if not supported or any(source.source == "demo_mailbox" for _, source in pairs):
                transaction.dataset = "quarantined"
            elif transaction.dataset == "household":
                refresh_review_confidence(
                    session,
                    user_id=LOCAL_USER_ID,
                    transaction_id=transaction.id,
                    preserve_status=False,
                )
    if orphans:
        session.execute(
            update(Commitment)
            .where(Commitment.user_id == LOCAL_USER_ID, Commitment.paid_transaction_id.in_(orphans))
            .values(paid_transaction_id=None, status="upcoming", user_resolved=False)
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
        .values(status="failed", error_code="import_failed", finished_at=now_ist())
    )
    audit(
        session,
        "data.deleted",
        "connection" if connection_id else "user",
        connection_id or LOCAL_USER_ID,
    )
