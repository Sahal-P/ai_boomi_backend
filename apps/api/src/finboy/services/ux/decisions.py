"""Version-checked review previews and reversible decisions; no lost updates."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.clock import now_ist
from finboy.db.models.ledger import Commitment, ReviewDecision, SourceEvent, Transaction
from finboy.services.ledger.persist import refresh_links, refresh_review_confidence
from finboy.services.ledger.reconcile import (
    _get,
    _lock_fields,
    correct_transaction,
    keep_separate,
    merge_transactions,
    revision,
    set_review_status,
)
from finboy.services.money import merchants
from finboy.services.money.detail import transaction_detail
from finboy.services.money.engine import MoneySummary, PeriodSpec, money_summary
from finboy.services.money.models import Correction, TransactionDetail
from finboy.services.privacy.audit import audit
from finboy.services.ux.state import TaskError, data_version, require_version


class VersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: str = Field(min_length=1, max_length=80)


class DecisionRequest(VersionRequest):
    action: Literal["confirm", "reject", "reopen", "correct", "merge", "keep-separate"]
    correction: Correction | None = None
    keep_id: UUID | None = None

    @model_validator(mode="after")
    def required_fields(self) -> DecisionRequest:
        if (self.action == "merge") != (self.keep_id is not None):
            raise ValueError("Only a merge requires a survivor")
        if self.action == "correct" and self.correction is None:
            raise ValueError("Supply a correction")
        if self.correction is not None and self.action not in {"correct", "confirm"}:
            raise ValueError("Unsupported correction action")
        return self


class DecisionPreview(BaseModel):
    version: str
    action: str
    transaction_id: UUID
    keep_id: UUID | None
    source_count: int
    affected_transaction_ids: list[UUID]
    before_summary: MoneySummary
    after_summary: MoneySummary


class DecisionResult(BaseModel):
    detail: TransactionDetail
    decision_id: UUID
    data_version: str


def _json(value: object) -> object:
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _snapshot(session: Session, user_id: UUID) -> dict:
    state = {}
    for model, fields in [
        (Transaction, None),
        (Commitment, None),
        (SourceEvent, ["transaction_id"]),
    ]:
        names = fields or [
            c.name
            for c in model.__table__.columns
            if c.name not in {"id", "user_id", "created_at", "updated_at"}
        ]
        state[model.__tablename__] = {
            str(row.id): {name: _json(getattr(row, name)) for name in names}
            for row in session.scalars(select(model).where(model.user_id == user_id))
        }
    return state


def _apply(session: Session, user_id: UUID, transaction_id: UUID, request: DecisionRequest) -> None:
    try:
        item = _get(session, user_id, transaction_id)
        if request.correction:
            values = request.correction.model_dump(exclude_unset=True)
            direction = values.get("direction", item.direction)
            kind = values.get("kind", item.kind)
            if (kind in {"salary", "income_other", "refund", "reversal"} and direction != "in") or (
                kind in {"purchase", "fee", "bill_payment", "emi", "investment"}
                and direction != "out"
            ):
                raise TaskError("invalid_decision")
            correct_transaction(session, user_id=user_id, transaction_id=transaction_id, **values)
        if request.action in {"confirm", "reject"}:
            set_review_status(
                session,
                user_id=user_id,
                transaction_id=transaction_id,
                status="confirmed" if request.action == "confirm" else "rejected",
            )
        elif request.action == "reopen":
            if item.status == "merged":
                raise TaskError("invalid_decision")
            revision(
                session,
                item,
                "status",
                item.status,
                "needs_review",
                reason="user_reopened",
                changed_by="user",
            )
            item.status, item.review_reason = "needs_review", "low_confidence"
            _lock_fields(session, item, {"status", "review_reason"}, "user_reopened")
            item.updated_at = now_ist()
        elif request.action == "merge":
            merge_transactions(
                session, user_id=user_id, keep_id=request.keep_id, merge_id=transaction_id
            )
            refresh_review_confidence(session, user_id=user_id, transaction_id=request.keep_id)
        elif request.action == "keep-separate":
            keep_separate(session, user_id=user_id, transaction_id=transaction_id)
        refresh_links(session, user_id)
        session.flush()
    except ValueError as exc:
        raise TaskError(
            "not_found"
            if str(exc) == "transaction_not_found"
            else "quarantined_record"
            if str(exc) == "quarantined_record"
            else "invalid_decision"
        ) from None


def preview_decision(
    session: Session, *, user_id: UUID, transaction_id: UUID, request: DecisionRequest
) -> DecisionPreview:
    require_version(session, user_id, request.expected_version)
    before_summary = money_summary(session, user_id=user_id, period=PeriodSpec())
    before = _snapshot(session, user_id)
    source_count = sum(
        v["transaction_id"] == str(transaction_id) for v in before["source_events"].values()
    )
    nested = session.begin_nested()
    try:
        _apply(session, user_id, transaction_id, request)
        after_summary = money_summary(session, user_id=user_id, period=PeriodSpec())
        after = _snapshot(session, user_id)
        affected = [
            UUID(key)
            for key, value in after["transactions"].items()
            if before["transactions"].get(key) != value
        ]
    finally:
        nested.rollback()
        session.expire_all()
    return DecisionPreview(
        version=request.expected_version,
        action=request.action,
        transaction_id=transaction_id,
        keep_id=request.keep_id,
        source_count=source_count,
        affected_transaction_ids=affected,
        before_summary=before_summary,
        after_summary=after_summary,
    )


def decide(
    session: Session, *, user_id: UUID, transaction_id: UUID, request: DecisionRequest
) -> DecisionResult:
    try:
        require_version(session, user_id, request.expected_version)
        before = _snapshot(session, user_id)
        _apply(session, user_id, transaction_id, request)
        if request.correction is not None and request.correction.category is not None:
            # A chosen category is remembered for the payee's next entries (merchant memory).
            chosen = _get(session, user_id, transaction_id)
            merchants.learn(session, user_id, chosen.merchant, request.correction.category)
        after = _snapshot(session, user_id)
        # Store only changed entities; preserve all history rather than inverse SQL guesses.
        changed = {
            table: {key: value for key, value in rows.items() if before[table].get(key) != value}
            for table, rows in after.items()
        }
        original = {
            table: {key: before[table][key] for key in rows} for table, rows in changed.items()
        }
        decision = ReviewDecision(
            id=uuid4(),
            user_id=user_id,
            transaction_id=transaction_id,
            action=request.action,
            before_state=original,
            after_state=changed,
            result_version=data_version(session, user_id),
        )
        session.add(decision)
        audit(session, "review.completed", "transaction", transaction_id, user_id=user_id)
        session.flush()
        result = DecisionResult(
            detail=transaction_detail(session, user_id=user_id, transaction_id=transaction_id),
            decision_id=decision.id,
            data_version=data_version(session, user_id),
        )
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def undo_decision(
    session: Session,
    *,
    user_id: UUID,
    transaction_id: UUID,
    decision_id: UUID,
    expected_version: str,
) -> DecisionResult:
    try:
        require_version(session, user_id, expected_version)
        decision = session.scalar(
            select(ReviewDecision)
            .where(
                ReviewDecision.id == decision_id,
                ReviewDecision.user_id == user_id,
                ReviewDecision.transaction_id == transaction_id,
            )
            .with_for_update()
        )
        if decision is None:
            raise TaskError("not_found")
        if decision.undone_at is not None or decision.result_version != expected_version:
            raise TaskError("decision_conflict")
        for model in (Transaction, Commitment, SourceEvent):
            for key, values in decision.before_state.get(model.__tablename__, {}).items():
                row = session.get(model, UUID(key))
                if row is None or row.user_id != user_id:
                    raise TaskError("decision_conflict")
                for field, value in values.items():
                    if (
                        _json(getattr(row, field))
                        != decision.after_state[model.__tablename__][key][field]
                    ):
                        raise TaskError("decision_conflict")
                    if model is Transaction:
                        revision(
                            session,
                            row,
                            field,
                            _json(getattr(row, field)),
                            value,
                            reason="decision_undone",
                            changed_by="user",
                        )
                    if value is not None:
                        python_type = model.__table__.columns[field].type.python_type
                        if python_type is UUID:
                            value = UUID(value)
                        elif python_type is datetime:
                            value = datetime.fromisoformat(value)
                        elif python_type is date:
                            value = date.fromisoformat(value)
                        elif python_type is Decimal:
                            value = Decimal(value)
                    setattr(row, field, value)
                if model is Transaction:
                    row.updated_at = now_ist()
        decision.undone_at = now_ist()
        audit(session, "review.undone", "transaction", transaction_id, user_id=user_id)
        session.flush()
        result = DecisionResult(
            detail=transaction_detail(session, user_id=user_id, transaction_id=transaction_id),
            decision_id=decision.id,
            data_version=data_version(session, user_id),
        )
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
