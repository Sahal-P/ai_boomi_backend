import hashlib
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.clock import IST, now_ist
from finboy.db.models.ledger import (
    Commitment,
    EmailSource,
    SourceEvent,
    Transaction,
    TransactionRevision,
)
from finboy.services.ingestion.classifier import trusted_domain
from finboy.services.ingestion.types import Event
from finboy.services.ledger.categories import category_for, normalize_merchant
from finboy.services.ledger.confidence import Confidence, confidence_for
from finboy.services.ledger.matching import (
    choose_match,
    claims_agree,
    direction,
    kind,
    original_for,
)
from finboy.services.ledger.reconcile import revision


def as_event(row: SourceEvent) -> Event:
    return Event(
        event_type=row.event_type,
        amount_minor=row.amount_minor,
        merchant=row.merchant_normalized,
        occurred_at=row.occurred_at,
        due_date=row.due_date,
        reference_id=row.reference_id,
        payment_instrument=row.payment_instrument,
        account_last4=row.account_last4,
        extraction_method=row.extraction_method,
        extractor_id=row.extractor_id,
        evidence=row.evidence,
        field_confidence=row.field_confidence,
        payment_proof="payment_proof" in row.evidence,
        rule_fields=row.extractor_id.partition(";fields=")[2].split(",")
        if ";fields=" in row.extractor_id
        else [],
    )


def user_controls_status(session: Session, transaction: Transaction) -> bool:
    return (
        transaction.status == "rejected"
        or "status" in (transaction.user_locked_fields or [])
        or session.scalar(
            select(TransactionRevision.id)
            .where(
                TransactionRevision.transaction_id == transaction.id,
                TransactionRevision.changed_by == "user",
                TransactionRevision.field == "status",
            )
            .limit(1)
        )
        is not None
    )


def _source_event(
    session: Session, user_id: UUID, source: EmailSource, event: Event
) -> SourceEvent:
    row = SourceEvent(
        user_id=user_id,
        email_source_id=source.id,
        event_type=event.event_type,
        amount_minor=event.amount_minor,
        currency=event.currency,
        merchant_raw=event.merchant,
        merchant_normalized=normalize_merchant(event.merchant),
        occurred_at=event.occurred_at,
        due_date=event.due_date,
        reference_id=event.reference_id,
        payment_instrument=event.payment_instrument,
        account_last4=event.account_last4,
        extraction_method=event.extraction_method,
        extractor_id=event.extractor_id + ";fields=" + ",".join(sorted(event.rule_fields)),
        evidence={k: v[:80] for k, v in event.evidence.items()},
        field_confidence=event.field_confidence,
    )
    session.add(row)
    session.flush()
    return row


def _fingerprint(event: Event) -> str:
    parts = (
        direction(event),
        event.currency,
        str(event.amount_minor),
        str(event.occurred_at),
        event.reference_id or "",
        normalize_merchant(event.merchant) or "",
    )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _set_confidence(
    session: Session,
    transaction: Transaction,
    confidence: Confidence,
    *,
    preserve_status: bool = False,
) -> None:
    locked = set(transaction.user_locked_fields or [])
    updates = {
        "confidence": Decimal(str(confidence.value)),
        "confidence_factors": confidence.factors,
    }
    if (
        not preserve_status
        and not user_controls_status(session, transaction)
        and transaction.status != "failed"
    ):
        updates.update(status=confidence.status, review_reason=confidence.review_reason)
    for field, value in updates.items():
        if field not in locked:
            old = getattr(transaction, field)
            revision(
                session,
                transaction,
                field,
                str(old) if isinstance(old, Decimal) else old,
                str(value) if isinstance(value, Decimal) else value,
                reason="evidence_reconciled",
            )
            setattr(transaction, field, value)
    transaction.updated_at = now_ist()


def refresh_review_confidence(
    session: Session, *, user_id: UUID, transaction_id: UUID, preserve_status: bool = True
) -> None:
    """Moved merge evidence changes confidence, while the user's chosen status stays locked."""
    transaction = session.scalar(
        select(Transaction).where(Transaction.user_id == user_id, Transaction.id == transaction_id)
    )
    if transaction is None:
        raise ValueError("transaction_not_found")
    sources = list(
        session.scalars(
            select(SourceEvent)
            .where(SourceEvent.user_id == user_id, SourceEvent.transaction_id == transaction_id)
            .order_by(SourceEvent.created_at, SourceEvent.id)
        )
    )
    if not sources:
        return
    chosen = next((row for row in sources if "payment_proof" in row.evidence), sources[0])
    best = as_event(chosen)
    sender = session.scalar(
        select(EmailSource).where(
            EmailSource.user_id == user_id, EmailSource.id == chosen.email_source_id
        )
    )
    confidence = confidence_for(
        best,
        trusted=trusted_domain(sender.sender_domain) if sender else False,
        source_count=len({row.email_source_id for row in sources}),
        agreement=all(claims_agree(best, as_event(row)) for row in sources),
    )
    _set_confidence(session, transaction, confidence, preserve_status=preserve_status)


def _commitment(
    session: Session, user_id: UUID, event: Event, source_event: SourceEvent, trusted: bool
) -> None:
    if event.due_date is None:
        return
    dataset = (
        "demo"
        if session.get(EmailSource, source_event.email_source_id).source == "demo_mailbox"
        else "household"
    )
    label = normalize_merchant(event.merchant) or "Unidentified obligation"
    existing = session.scalar(
        select(Commitment).where(
            Commitment.user_id == user_id,
            Commitment.dataset == dataset,
            Commitment.label == label,
            Commitment.amount_minor == event.amount_minor,
            Commitment.due_date == event.due_date,
        )
    )
    if existing is None:
        confidence = confidence_for(event, trusted=trusted)
        session.add(
            Commitment(
                user_id=user_id,
                dataset=dataset,
                kind="emi" if event.event_type == "emi_due" else "bill",
                label=label,
                amount_minor=event.amount_minor,
                currency="INR",
                due_date=event.due_date,
                status="upcoming",
                source_event_id=source_event.id,
                confidence=Decimal(str(confidence.value)),
            )
        )


def refresh_links(session: Session, user_id: UUID, dataset: str = "household") -> None:
    transactions = list(
        session.scalars(
            select(Transaction).where(
                Transaction.user_id == user_id,
                Transaction.dataset == dataset,
                Transaction.status != "merged",
            )
        )
    )
    events = []
    for transaction in transactions:
        source = session.scalar(
            select(SourceEvent)
            .where(SourceEvent.transaction_id == transaction.id)
            .order_by(SourceEvent.created_at)
            .limit(1)
        )
        events.append(
            as_event(source)
            if source
            else Event(
                event_type="debit",
                amount_minor=transaction.amount_minor,
                merchant=transaction.merchant,
                occurred_at=transaction.occurred_at,
            )
        )
    # Reconciliation follows corrected canonical facts; source claims remain evidence.
    event_types = {
        "purchase": "debit",
        "salary": "salary",
        "income_other": "credit",
        "refund": "refund",
        "reversal": "reversal",
        "fee": "fee",
        "bill_payment": "debit",
        "emi": "debit",
        "investment": "investment",
        "transfer": "transfer",
    }
    events = [
        event.model_copy(
            update={
                "event_type": event_types[tx.kind],
                "amount_minor": tx.amount_minor,
                "merchant": tx.merchant,
                "occurred_at": tx.occurred_at,
                "reference_id": tx.reference_id,
            }
        )
        for tx, event in zip(transactions, events, strict=True)
    ]
    for transaction, event in zip(transactions, events, strict=True):
        index = original_for(event, events)
        if index is not None and "linked_transaction_id" not in (
            transaction.user_locked_fields or []
        ):
            target = transactions[index].id
            revision(
                session,
                transaction,
                "linked_transaction_id",
                str(transaction.linked_transaction_id)
                if transaction.linked_transaction_id
                else None,
                str(target),
                reason="refund_link",
            )
            transaction.linked_transaction_id = target
        elif (
            index is None
            and transaction.linked_transaction_id
            and "linked_transaction_id" not in (transaction.user_locked_fields or [])
        ):
            revision(
                session,
                transaction,
                "linked_transaction_id",
                str(transaction.linked_transaction_id),
                None,
                reason="refund_link_removed",
            )
            transaction.linked_transaction_id = None
    commitments = session.scalars(
        select(Commitment).where(
            Commitment.user_id == user_id,
            Commitment.dataset == dataset,
            Commitment.status.in_(["upcoming", "paid"]),
        )
    )
    for commitment in commitments:
        if commitment.user_resolved:
            continue
        if commitment.status == "paid":
            paid = next(
                (tx for tx in transactions if tx.id == commitment.paid_transaction_id), None
            )
            # A user rejecting/correcting the recorded payment reopens the obligation.
            # Merchant/category edits alone retain an explicit paid link.
            if paid is not None and (
                paid.status == "confirmed"
                and paid.direction == "out"
                and paid.kind != "transfer"
                and paid.amount_minor == commitment.amount_minor
            ):
                continue
            commitment.status = "upcoming"
            commitment.paid_transaction_id = None
        candidates = [
            tx
            for tx in transactions
            if tx.status == "confirmed"
            and tx.direction == "out"
            and tx.kind != "transfer"
            and tx.amount_minor == commitment.amount_minor
            and tx.merchant == commitment.label
            and abs((tx.occurred_at.astimezone(IST).date() - commitment.due_date).days) <= 7
        ]
        if len(candidates) == 1:
            commitment.status = "paid"
            commitment.paid_transaction_id = candidates[0].id


def persist_event(
    session: Session, *, user_id: UUID, source: EmailSource, event: Event, fallback_time: datetime
) -> tuple[bool, bool]:
    """Return (transaction created, duplicate merged); caller commits one message."""
    source_event = _source_event(session, user_id, source, event)
    trusted = trusted_domain(source.sender_domain)
    dataset = "demo" if source.source == "demo_mailbox" else "household"
    if event.event_type in {"bill_due", "emi_due"}:
        _commitment(session, user_id, event, source_event, trusted)
        session.flush()
        refresh_links(session, user_id, dataset)
        return False, False
    transactions = list(
        session.scalars(
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.dataset == dataset,
                Transaction.status != "merged",
            )
            .order_by(Transaction.created_at)
        )
    )
    existing_events = []
    for transaction in transactions:
        rows = list(
            session.scalars(select(SourceEvent).where(SourceEvent.transaction_id == transaction.id))
        )
        # Matching uses provider evidence even if the user corrected the ledger's amount.
        chosen = next(
            (row for row in rows if "payment_proof" in row.evidence), rows[0] if rows else None
        )
        existing_events.append(
            as_event(chosen)
            if chosen
            else Event(
                event_type="debit",
                amount_minor=transaction.amount_minor,
                merchant=transaction.merchant,
                occurred_at=transaction.occurred_at,
            )
        )
    excluded = {
        i for i, item in enumerate(transactions) if "dedupe" in (item.user_locked_fields or [])
    }
    match = choose_match(event, existing_events, excluded=excluded)
    if match.index is not None:
        transaction = transactions[match.index]
        source_event.transaction_id = transaction.id
        source_event.origin_transaction_id = transaction.id
        session.flush()
        sources = list(
            session.scalars(select(SourceEvent).where(SourceEvent.transaction_id == transaction.id))
        )
        chosen = next((item for item in sources if "payment_proof" in item.evidence), source_event)
        best = as_event(chosen)
        sender = session.get(EmailSource, chosen.email_source_id)
        confidence = confidence_for(
            best,
            trusted=trusted_domain(sender.sender_domain) if sender else False,
            source_count=len({item.email_source_id for item in sources}),
            agreement=all(claims_agree(best, as_event(item)) for item in sources),
        )
        if event.payment_proof and not existing_events[match.index].payment_proof:
            locked = set(transaction.user_locked_fields or [])
            for field, value in {
                "kind": kind(event),
                "merchant": normalize_merchant(event.merchant) or "Unknown",
                "category": category_for(event),
                "occurred_at": event.occurred_at or fallback_time,
                "reference_id": event.reference_id,
                "payment_instrument": event.payment_instrument,
                "account_last4": event.account_last4,
            }.items():
                if field not in locked:
                    old = getattr(transaction, field)
                    revision(
                        session,
                        transaction,
                        field,
                        old.isoformat() if isinstance(old, datetime) else old,
                        value.isoformat() if isinstance(value, datetime) else value,
                        reason="payment_evidence",
                    )
                    setattr(transaction, field, value)
        _set_confidence(session, transaction, confidence)
        session.flush()
        refresh_links(session, user_id, dataset)
        return False, True
    confidence = confidence_for(event, trusted=trusted)
    if match.possible_index is not None:
        confidence = Confidence(
            confidence.value, confidence.factors, "needs_review", "possible_duplicate"
        )
    transaction = Transaction(
        user_id=user_id,
        dataset=dataset,
        direction=direction(event),
        kind=kind(event),
        amount_minor=event.amount_minor,
        currency=event.currency,
        merchant=normalize_merchant(event.merchant) or "Unknown",
        category=category_for(event),
        occurred_at=event.occurred_at or fallback_time,
        reference_id=event.reference_id,
        payment_instrument=event.payment_instrument,
        account_last4=event.account_last4,
        confidence=Decimal(str(confidence.value)),
        confidence_factors=confidence.factors,
        status="failed" if event.event_type == "failed" else confidence.status,
        review_reason=None if event.event_type == "failed" else confidence.review_reason,
        possible_duplicate_of_id=transactions[match.possible_index].id
        if match.possible_index is not None
        else None,
        fingerprint=_fingerprint(event),
        user_locked_fields=[],
    )
    session.add(transaction)
    session.flush()
    source_event.transaction_id = transaction.id
    source_event.origin_transaction_id = transaction.id
    session.flush()
    refresh_links(session, user_id, dataset)
    return True, False
