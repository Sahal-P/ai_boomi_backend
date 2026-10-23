"""Review writes own commit/rollback; ingestion and review serialize on the same user lock."""

import hashlib
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finboy.db.models.mail import AuditEvent
from finboy.services.ledger.persist import refresh_links, refresh_review_confidence
from finboy.services.ledger.reconcile import (
    correct_transaction,
    keep_separate,
    merge_transactions,
    set_review_status,
)
from finboy.services.money.detail import transaction_detail
from finboy.services.money.models import Correction, TransactionDetail

ReviewAction = Literal["confirm", "reject", "merge", "keep-separate", "correct"]


def review_transaction(
    session: Session,
    *,
    user_id: UUID,
    transaction_id: UUID,
    action: ReviewAction,
    correction: Correction | None = None,
    keep_id: UUID | None = None,
) -> TransactionDetail:
    try:
        lock = int.from_bytes(hashlib.sha256(user_id.bytes).digest()[:8], "big", signed=True)
        session.execute(select(func.pg_advisory_xact_lock(lock)))
        if action == "correct" and correction is not None:
            correct_transaction(
                session,
                user_id=user_id,
                transaction_id=transaction_id,
                category=correction.category,
                merchant=correction.merchant,
                amount_minor=correction.amount_minor,
            )
        elif action in {"confirm", "reject"}:
            set_review_status(
                session,
                user_id=user_id,
                transaction_id=transaction_id,
                status="confirmed" if action == "confirm" else "rejected",
            )
        elif action == "merge" and keep_id is not None:
            merge_transactions(session, user_id=user_id, keep_id=keep_id, merge_id=transaction_id)
            refresh_review_confidence(session, user_id=user_id, transaction_id=keep_id)
        elif action == "keep-separate":
            keep_separate(session, user_id=user_id, transaction_id=transaction_id)
        else:
            raise ValueError("invalid_review_action")
        refresh_links(session, user_id)
        # Fixed operation codes and field NAMES only; no financial or source content.
        session.add(
            AuditEvent(
                user_id=user_id,
                event_type={
                    "correct": "transaction.corrected",
                    "confirm": "transaction.confirmed",
                    "reject": "transaction.rejected",
                    "merge": "transaction.merged",
                    "keep-separate": "transaction.kept_separate",
                }[action],
                subject_type="transaction",
                subject_id=transaction_id,
                event_metadata={
                    "action": action,
                    "fields": sorted(correction.model_fields_set) if correction else [],
                },
            )
        )
        session.flush()
        result = transaction_detail(session, user_id=user_id, transaction_id=transaction_id)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
