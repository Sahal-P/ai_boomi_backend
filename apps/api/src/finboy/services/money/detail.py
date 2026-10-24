from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.db.models.ledger import (
    EmailSource,
    ReviewDecision,
    SourceEvent,
    Transaction,
    TransactionRevision,
)
from finboy.services.money.engine import transaction_views
from finboy.services.money.models import (
    DecisionView,
    RevisionView,
    TransactionDetail,
    TransactionSource,
)
from finboy.services.ux.state import data_version, lock_snapshot


def transaction_detail(
    session: Session, *, user_id: UUID, transaction_id: UUID
) -> TransactionDetail:
    lock_snapshot(session, user_id)
    transaction = session.scalar(
        select(Transaction).where(Transaction.user_id == user_id, Transaction.id == transaction_id)
    )
    if transaction is None or transaction.dataset == "demo":
        raise ValueError("transaction_not_found")
    sources = [
        TransactionSource(
            id=event.id,
            email_source_id=source.id,
            source=source.source,
            sender_domain=source.sender_domain,
            received_at=source.received_at,
            classification=source.classification,
            event_type=event.event_type,
            amount_minor=event.amount_minor,
            currency=event.currency,
            merchant=event.merchant_normalized,
            occurred_at=event.occurred_at,
            due_date=event.due_date,
            extraction_method=event.extraction_method,
            extractor_id=event.extractor_id,
            evidence={key[:80]: value[:80] for key, value in sorted(event.evidence.items())[:16]},
            field_confidence=event.field_confidence,
        )
        for event, source in session.execute(
            select(SourceEvent, EmailSource)
            .join(EmailSource, EmailSource.id == SourceEvent.email_source_id)
            .where(
                SourceEvent.user_id == user_id,
                EmailSource.user_id == user_id,
                SourceEvent.transaction_id == transaction_id,
                EmailSource.source != "demo_mailbox",
            )
            .order_by(EmailSource.received_at, SourceEvent.id)
        )
    ]
    revisions = [
        RevisionView.model_validate(row, from_attributes=True)
        for row in session.scalars(
            select(TransactionRevision)
            .join(Transaction, Transaction.id == TransactionRevision.transaction_id)
            .where(Transaction.user_id == user_id, Transaction.id == transaction_id)
            .order_by(TransactionRevision.changed_at, TransactionRevision.id)
        )
    ]
    return TransactionDetail(
        version=data_version(session, user_id),
        decisions=[
            DecisionView(
                id=d.id,
                action=d.action,
                created_at=d.created_at,
                undone_at=d.undone_at,
                can_undo=d.undone_at is None and d.result_version == data_version(session, user_id),
            )
            for d in session.scalars(
                select(ReviewDecision)
                .where(
                    ReviewDecision.user_id == user_id,
                    ReviewDecision.transaction_id == transaction_id,
                )
                .order_by(ReviewDecision.created_at.desc())
            )
        ],
        transaction=transaction_views(session, [transaction], user_id=user_id)[0],
        sources=sources,
        confidence_factors=transaction.confidence_factors,
        revisions=revisions,
    )
