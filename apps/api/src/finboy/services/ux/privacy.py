"""Explicit private portability and source-aware deletion previews."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finboy.core.clock import now_ist
from finboy.db.models.ledger import (
    Commitment,
    EmailSource,
    SourceEvent,
    Transaction,
    TransactionRevision,
)
from finboy.db.models.mail import MailConnection
from finboy.services.money.engine import commitment_view, transaction_views
from finboy.services.money.models import RevisionView
from finboy.services.privacy.audit import audit
from finboy.services.ux.decisions import VersionRequest
from finboy.services.ux.state import TaskError, data_version


class DeletionScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_id: UUID | None = None


class DeleteRequest(VersionRequest):
    connection_id: UUID | None = None


class TaskOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: Literal["evidence_opened", "overview_understood", "review_completed"]
    subject_id: UUID | None = None


def source_scope(user_id: UUID, connection_id: UUID | None):
    conditions = [EmailSource.user_id == user_id]
    if connection_id:
        conditions.append(EmailSource.mail_connection_id == connection_id)
    return conditions


def deletion_preview(session: Session, *, user_id: UUID, connection_id: UUID | None) -> dict:
    if (
        connection_id
        and session.scalar(
            select(MailConnection.id).where(
                MailConnection.id == connection_id, MailConnection.user_id == user_id
            )
        )
        is None
    ):
        raise TaskError("not_found")
    sources = list(
        session.scalars(select(EmailSource).where(*source_scope(user_id, connection_id)))
    )
    ids = {source.id for source in sources}
    events = list(
        session.scalars(
            select(SourceEvent).where(
                SourceEvent.user_id == user_id, SourceEvent.email_source_id.in_(ids)
            )
        )
    )
    txids = {event.transaction_id for event in events if event.transaction_id}
    shared = set(
        session.scalars(
            select(SourceEvent.transaction_id).where(
                SourceEvent.user_id == user_id,
                SourceEvent.transaction_id.in_(txids),
                SourceEvent.email_source_id.not_in(ids),
            )
        )
    )
    obligations = list(
        session.scalars(
            select(Commitment).where(
                Commitment.user_id == user_id,
                Commitment.source_event_id.in_([e.id for e in events]),
            )
        )
    )
    shared_obligations = 0
    for row in obligations:
        replacement = session.scalar(
            select(SourceEvent.id)
            .where(
                SourceEvent.user_id == user_id,
                SourceEvent.email_source_id.not_in(ids),
                SourceEvent.event_type == ("emi_due" if row.kind == "emi" else "bill_due"),
                SourceEvent.amount_minor == row.amount_minor,
                SourceEvent.currency == row.currency,
                SourceEvent.due_date == row.due_date,
                func.coalesce(SourceEvent.merchant_normalized, "Unidentified obligation")
                == row.label,
            )
            .limit(1)
        )
        shared_obligations += int(replacement is not None)
    times = [row.received_at for row in sources]
    return {
        "version": data_version(session, user_id),
        "connection_id": connection_id,
        "source_count": len(sources),
        "event_count": len(events),
        "removed_transaction_count": len(txids - shared),
        "retained_shared_transaction_count": len(shared),
        "removed_obligation_count": len(obligations) - shared_obligations,
        "retained_shared_obligation_count": shared_obligations,
        "first_received_at": min(times) if times else None,
        "last_received_at": max(times) if times else None,
        "backup_retention_days": 7,
    }


def export_records(session: Session, *, user_id: UUID) -> dict:
    rows = list(
        session.scalars(
            select(Transaction)
            .where(Transaction.user_id == user_id, Transaction.dataset == "household")
            .order_by(Transaction.occurred_at, Transaction.id)
        )
    )
    # Source-free structured data; account/reference/payment identifiers are explicitly removed.
    records = [
        view.model_dump(
            mode="json", exclude={"reference_id", "payment_instrument", "account_last4"}
        )
        for view in transaction_views(session, rows, user_id=user_id)
    ]
    revisions = []
    allowed = {
        "merchant",
        "category",
        "amount_minor",
        "occurred_at",
        "direction",
        "kind",
        "status",
        "review_reason",
        "user_locked_fields",
        "dedupe",
        "linked_transaction_id",
        "merged_into_id",
        "possible_duplicate_of_id",
        "source_event_ids",
    }
    for revision in session.scalars(
        select(TransactionRevision)
        .join(Transaction, Transaction.id == TransactionRevision.transaction_id)
        .where(Transaction.user_id == user_id, Transaction.dataset == "household")
        .order_by(TransactionRevision.changed_at, TransactionRevision.id)
    ):
        if revision.field in allowed:
            revisions.append(
                RevisionView.model_validate(revision, from_attributes=True).model_dump(mode="json")
            )
    result = {
        "schema_version": "1.0",
        "dataset": "household",
        "exported_at": now_ist().isoformat(),
        "data_version": data_version(session, user_id),
        "transactions": records,
        "commitments": [
            commitment_view(row).model_dump(mode="json")
            for row in session.scalars(
                select(Commitment)
                .where(Commitment.user_id == user_id, Commitment.dataset == "household")
                .order_by(Commitment.due_date, Commitment.id)
            )
        ],
        "revisions": revisions,
    }
    audit(session, "data.exported", "user", user_id, user_id=user_id)
    session.commit()
    return result


def isolation_inventory(session: Session, *, user_id: UUID) -> dict:
    def count(model, dataset):
        return (
            session.scalar(
                select(func.count())
                .select_from(model)
                .where(model.user_id == user_id, model.dataset == dataset)
            )
            or 0
        )

    return {
        "data_version": data_version(session, user_id),
        "demo_only_transactions": count(Transaction, "demo"),
        "mixed_transactions": count(Transaction, "quarantined"),
        "demo_only_obligations": count(Commitment, "demo"),
        "quarantined_obligations": count(Commitment, "quarantined"),
    }
