"""Review actions run inside the caller's transaction and never commit implicitly."""

from typing import Literal, get_args
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from finboy.core.clock import now_ist
from finboy.db.models.ledger import (
    Category,
    Commitment,
    SourceEvent,
    Transaction,
    TransactionRevision,
)


def _get(session: Session, user_id: UUID, transaction_id: UUID) -> Transaction:
    item = session.scalar(
        select(Transaction)
        .where(Transaction.id == transaction_id, Transaction.user_id == user_id)
        .with_for_update()
    )
    if item is None:
        raise ValueError("transaction_not_found")
    return item


def revision(
    session: Session,
    transaction: Transaction,
    field: str,
    old: object,
    new: object,
    *,
    reason: str,
    changed_by: str = "system",
) -> None:
    if old != new:
        session.add(
            TransactionRevision(
                transaction_id=transaction.id,
                field=field,
                old_value=old,
                new_value=new,
                changed_by=changed_by,
                reason=reason,
            )
        )


def merge_transactions(session: Session, *, user_id: UUID, keep_id: UUID, merge_id: UUID) -> None:
    if keep_id == merge_id:
        raise ValueError("invalid_merge")
    # Lock in UUID order so concurrent review actions cannot deadlock each other.
    items = {
        item.id: item
        for item in session.scalars(
            select(Transaction)
            .where(Transaction.user_id == user_id, Transaction.id.in_([keep_id, merge_id]))
            .order_by(Transaction.id)
            .with_for_update()
        )
    }
    if len(items) != 2:
        raise ValueError("transaction_not_found")
    keep, merge = items[keep_id], items[merge_id]
    if merge.status == "merged" and merge.merged_into_id == keep_id:
        return
    if (
        keep.status in {"merged", "rejected", "failed"}
        or merge.status in {"merged", "rejected", "failed"}
        or keep.direction != merge.direction
        or keep.currency != merge.currency
        or ({keep.kind, merge.kind} & {"refund", "reversal"} and keep.kind != merge.kind)
    ):
        raise ValueError("invalid_merge")
    revision(
        session, merge, "status", merge.status, "merged", reason="manual_merge", changed_by="user"
    )
    revision(
        session,
        merge,
        "merged_into_id",
        str(merge.merged_into_id) if merge.merged_into_id else None,
        str(keep_id),
        reason="manual_merge",
        changed_by="user",
    )
    kept_sources = [
        str(value)
        for value in session.scalars(
            select(SourceEvent.id).where(
                SourceEvent.user_id == user_id, SourceEvent.transaction_id == keep_id
            )
        )
    ]
    merged_sources = [
        str(value)
        for value in session.scalars(
            select(SourceEvent.id).where(
                SourceEvent.user_id == user_id, SourceEvent.transaction_id == merge_id
            )
        )
    ]
    revision(
        session,
        keep,
        "source_event_ids",
        kept_sources,
        kept_sources + merged_sources,
        reason="manual_merge",
        changed_by="user",
    )
    session.execute(
        update(SourceEvent)
        .where(SourceEvent.user_id == user_id, SourceEvent.transaction_id == merge_id)
        .values(transaction_id=keep_id)
    )
    session.execute(
        update(Commitment)
        .where(Commitment.user_id == user_id, Commitment.paid_transaction_id == merge_id)
        .values(paid_transaction_id=keep_id)
    )
    session.execute(
        update(Transaction)
        .where(Transaction.user_id == user_id, Transaction.linked_transaction_id == merge_id)
        .values(linked_transaction_id=keep_id)
    )
    session.execute(
        update(Transaction)
        .where(Transaction.user_id == user_id, Transaction.possible_duplicate_of_id == merge_id)
        .values(possible_duplicate_of_id=keep_id)
    )
    merge.status = "merged"
    merge.merged_into_id = keep_id
    merge.possible_duplicate_of_id = None
    merge.updated_at = now_ist()
    if keep.possible_duplicate_of_id == merge_id:
        keep.possible_duplicate_of_id = None
    _lock_fields(session, keep, {"status", "dedupe"}, "manual_merge")
    keep.updated_at = now_ist()
    session.flush()


def keep_separate(session: Session, *, user_id: UUID, transaction_id: UUID) -> None:
    item = _get(session, user_id, transaction_id)
    if item.status in {"merged", "rejected", "failed"}:
        raise ValueError("invalid_review_action")
    partner = item.possible_duplicate_of_id
    if partner is None and "dedupe" in (item.user_locked_fields or []):
        return
    revision(
        session,
        item,
        "possible_duplicate_of_id",
        str(partner) if partner else None,
        None,
        reason="keep_separate",
        changed_by="user",
    )
    revision(
        session,
        item,
        "dedupe",
        None,
        str(partner) if partner else "separate",
        reason="keep_separate",
        changed_by="user",
    )
    item.possible_duplicate_of_id = None
    revision(
        session,
        item,
        "user_locked_fields",
        item.user_locked_fields,
        sorted(set(item.user_locked_fields or []) | {"dedupe"}),
        reason="keep_separate",
        changed_by="user",
    )
    item.user_locked_fields = sorted(set(item.user_locked_fields or []) | {"dedupe"})
    if item.review_reason == "possible_duplicate":
        # Separation resolves identity only. Explicit confirmation still belongs to the user.
        revision(
            session,
            item,
            "review_reason",
            item.review_reason,
            "low_confidence",
            reason="keep_separate",
            changed_by="user",
        )
        item.review_reason = "low_confidence"
    item.updated_at = now_ist()
    session.flush()


def _lock_fields(session: Session, item: Transaction, fields: set[str], reason: str) -> None:
    locked = sorted(set(item.user_locked_fields or []) | fields)
    revision(
        session,
        item,
        "user_locked_fields",
        item.user_locked_fields,
        locked,
        reason=reason,
        changed_by="user",
    )
    item.user_locked_fields = locked


def correct_transaction(
    session: Session,
    *,
    user_id: UUID,
    transaction_id: UUID,
    category: Category | None = None,
    merchant: str | None = None,
    amount_minor: int | None = None,
) -> None:
    if category is not None and category not in get_args(Category):
        raise ValueError("invalid_correction")
    if merchant is not None and (
        not merchant.strip() or len(merchant) > 160 or any(ord(char) < 32 for char in merchant)
    ):
        raise ValueError("invalid_correction")
    if amount_minor is not None and (
        type(amount_minor) is not int or not 0 < amount_minor <= 10**14
    ):
        raise ValueError("invalid_correction")
    changes = {
        key: value
        for key, value in {
            "category": category,
            "merchant": merchant.strip() if merchant is not None else None,
            "amount_minor": amount_minor,
        }.items()
        if value is not None
    }
    if not changes:
        raise ValueError("invalid_correction")
    item = _get(session, user_id, transaction_id)
    if item.status in {"merged", "rejected", "failed"}:
        raise ValueError("invalid_review_action")
    for field, value in changes.items():
        revision(
            session,
            item,
            field,
            getattr(item, field),
            value,
            reason="user_correction",
            changed_by="user",
        )
        setattr(item, field, value)
    _lock_fields(session, item, set(changes), "user_correction")
    item.updated_at = now_ist()
    session.flush()


def set_review_status(
    session: Session,
    *,
    user_id: UUID,
    transaction_id: UUID,
    status: Literal["confirmed", "rejected"],
) -> None:
    if status not in {"confirmed", "rejected"}:
        raise ValueError("invalid_review_action")
    item = _get(session, user_id, transaction_id)
    if item.status in {"merged", "failed"} or item.status == "rejected" and status == "confirmed":
        raise ValueError("invalid_review_action")
    reason = "user_confirmation" if status == "confirmed" else "user_rejection"
    revision(session, item, "status", item.status, status, reason=reason, changed_by="user")
    revision(
        session, item, "review_reason", item.review_reason, None, reason=reason, changed_by="user"
    )
    item.status = status
    item.review_reason = None
    _lock_fields(session, item, {"status", "review_reason"}, reason)
    item.updated_at = now_ist()
    session.flush()
