"""Inspectable liabilities, conservative uncertainty and explicit resolution."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.clock import today_ist
from finboy.db.models.ledger import Commitment, EmailSource, SourceEvent, Transaction
from finboy.services.money.engine import commitment_view
from finboy.services.money.models import TransactionSource
from finboy.services.privacy.audit import audit
from finboy.services.ux.decisions import VersionRequest
from finboy.services.ux.state import TaskError, data_version, require_version


class ObligationCorrection(VersionRequest):
    label: str | None = Field(default=None, min_length=1, max_length=160)
    amount_minor: int | None = Field(default=None, gt=0, le=10**14, strict=True)
    due_date: date | None = None
    status: Literal["upcoming", "paid", "dismissed"] | None = None
    paid_transaction_id: UUID | None = None

    @model_validator(mode="after")
    def validate_change(self) -> ObligationCorrection:
        if not self.model_fields_set - {"expected_version"}:
            raise ValueError("Supply an obligation correction")
        if self.label is not None and (
            not self.label.strip() or any(ord(c) < 32 for c in self.label)
        ):
            raise ValueError("Use a printable label")
        if any(
            getattr(self, k) is None
            for k in self.model_fields_set - {"expected_version", "paid_transaction_id"}
        ):
            raise ValueError("A correction cannot be null")
        return self


def obligation_detail(session: Session, *, user_id: UUID, obligation_id: UUID) -> dict:
    row = session.scalar(
        select(Commitment).where(
            Commitment.user_id == user_id,
            Commitment.id == obligation_id,
            Commitment.dataset == "household",
            Commitment.status != "pending",
        )
    )
    if row is None:
        raise TaskError("not_found")
    sources = []
    if row.source_event_id:
        pair = session.execute(
            select(SourceEvent, EmailSource)
            .join(EmailSource, EmailSource.id == SourceEvent.email_source_id)
            .where(
                SourceEvent.id == row.source_event_id,
                SourceEvent.user_id == user_id,
                EmailSource.source != "demo_mailbox",
            )
        ).first()
        if pair:
            event, source = pair
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
                    merchant=event.merchant_normalized,
                    occurred_at=event.occurred_at,
                    due_date=event.due_date,
                    extraction_method=event.extraction_method,
                    extractor_id=event.extractor_id,
                    evidence={k[:80]: v[:80] for k, v in sorted(event.evidence.items())[:16]},
                    field_confidence=event.field_confidence,
                )
            ]
    version = data_version(session, user_id)
    return {
        "commitment": commitment_view(row, today=today_ist(), version=version),
        "sources": sources,
        "version": version,
    }


def correct_obligation(
    session: Session, *, user_id: UUID, obligation_id: UUID, request: ObligationCorrection
) -> dict:
    try:
        require_version(session, user_id, request.expected_version)
        obligation_detail(session, user_id=user_id, obligation_id=obligation_id)
        row = session.get(Commitment, obligation_id)
        changes = request.model_dump(exclude_unset=True, exclude={"expected_version"})
        if request.paid_transaction_id:
            payment = session.scalar(
                select(Transaction).where(
                    Transaction.user_id == user_id,
                    Transaction.id == request.paid_transaction_id,
                    Transaction.dataset == "household",
                    Transaction.status == "confirmed",
                    Transaction.direction == "out",
                    Transaction.kind != "transfer",
                    Transaction.amount_minor == changes.get("amount_minor", row.amount_minor),
                )
            )
            if payment is None or changes.get("status", row.status) != "paid":
                raise TaskError("invalid_decision")
        for key, value in changes.items():
            setattr(row, key, value.strip() if key == "label" else value)
        if row.status != "paid":
            row.paid_transaction_id = None
        if "status" in changes:
            row.user_resolved = not (row.status == "paid" and row.paid_transaction_id is not None)
        audit(session, "obligation.corrected", "commitment", row.id, user_id=user_id)
        session.flush()
        result = obligation_detail(session, user_id=user_id, obligation_id=obligation_id)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
