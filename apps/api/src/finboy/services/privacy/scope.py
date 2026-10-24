"""Exact current and original transaction lineage for privacy previews and removal."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.db.models.ledger import ReviewDecision, SourceEvent, Transaction
from finboy.services.ux.state import TaskError


@dataclass(frozen=True)
class TransactionImpact:
    affected: set[UUID]
    removed: set[UUID]
    retained: set[UUID]
    decisions: set[UUID]


def transaction_impact(
    session: Session, *, user_id: UUID, source_ids: set[UUID]
) -> TransactionImpact:
    selected = list(
        session.scalars(
            select(SourceEvent).where(
                SourceEvent.user_id == user_id, SourceEvent.email_source_id.in_(source_ids)
            )
        )
    )
    affected = {
        key
        for event in selected
        for key in (event.transaction_id, event.origin_transaction_id)
        if key is not None
    }
    affected = set(
        session.scalars(
            select(Transaction.id).where(
                Transaction.user_id == user_id, Transaction.id.in_(affected)
            )
        )
    )
    remaining = list(
        session.scalars(
            select(SourceEvent).where(
                SourceEvent.user_id == user_id, SourceEvent.email_source_id.not_in(source_ids)
            )
        )
    )
    retained = {
        key
        for event in remaining
        for key in (event.transaction_id, event.origin_transaction_id)
        if key in affected
    }
    decision_ids = set()
    decisions = list(
        session.scalars(select(ReviewDecision).where(ReviewDecision.user_id == user_id))
    )
    known_origins = set(
        session.scalars(
            select(SourceEvent.origin_transaction_id).where(
                SourceEvent.user_id == user_id, SourceEvent.origin_transaction_id.is_not(None)
            )
        )
    )
    recorded_merges = {
        decision.transaction_id for decision in decisions if decision.action == "merge"
    }
    merged = {
        row.id: row.merged_into_id
        for row in session.scalars(
            select(Transaction).where(
                Transaction.user_id == user_id, Transaction.status == "merged"
            )
        )
    }
    for key in merged:
        if key in known_origins or key in recorded_merges:
            continue
        current, seen = merged[key], set()
        while current is not None and current not in seen:
            if current in affected:
                raise TaskError("source_lineage_unavailable")
            seen.add(current)
            current = merged.get(current)

    event_ids = {str(event.id) for event in selected}
    for decision in decisions:
        touched = {str(decision.transaction_id)}
        touched_events = set()
        commitment_source_ids = set()
        for snapshot in (decision.before_state, decision.after_state):
            touched.update(snapshot.get("transactions", {}))
            touched_events.update(snapshot.get("source_events", {}))
            commitment_source_ids.update(
                value.get("source_event_id") for value in snapshot.get("commitments", {}).values()
            )
        if (
            touched & {str(key) for key in affected}
            or touched_events & event_ids
            or commitment_source_ids & event_ids
        ):
            decision_ids.add(decision.id)
    return TransactionImpact(affected, affected - retained, retained, decision_ids)
