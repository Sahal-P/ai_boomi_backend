from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from finboy.api.deps import CurrentUser
from finboy.db.session import get_session
from finboy.services.money.detail import transaction_detail
from finboy.services.money.engine import TransactionView, find_transactions
from finboy.services.money.http import MoneyRoute
from finboy.services.money.models import (
    Correction,
    MergeRequest,
    TransactionDetail,
    TransactionFilters,
)
from finboy.services.money.review import ReviewAction, review_transaction
from finboy.services.ux.decisions import (
    DecisionPreview,
    DecisionRequest,
    DecisionResult,
    VersionRequest,
    decide,
    preview_decision,
    undo_decision,
)
from finboy.services.ux.records import (
    MergeCandidates,
    PageQuery,
    TransactionPage,
    merge_candidates,
    transaction_page,
)

router = APIRouter(prefix="/transactions", tags=["transactions"], route_class=MoneyRoute)
DB = Annotated[Session, Depends(get_session)]


@router.get("")
def transactions(
    session: DB, user_id: CurrentUser, query: Annotated[TransactionFilters, Query()]
) -> list[TransactionView]:
    return find_transactions(
        session,
        user_id=user_id,
        period=query.to_period(),
        category=query.category,
        merchant=query.q,
        status=query.status,
        limit=query.limit,
    )


@router.get("/page")
def page(
    session: DB, user_id: CurrentUser, query: Annotated[PageQuery, Query()]
) -> TransactionPage:
    return transaction_page(session, user_id=user_id, query=query)


@router.get("/{transaction_id}/merge-candidates")
def candidates(transaction_id: UUID, session: DB, user_id: CurrentUser) -> MergeCandidates:
    return merge_candidates(session, user_id=user_id, transaction_id=transaction_id)


@router.post("/{transaction_id}/decision-preview")
def preview(
    transaction_id: UUID, body: DecisionRequest, session: DB, user_id: CurrentUser
) -> DecisionPreview:
    return preview_decision(session, user_id=user_id, transaction_id=transaction_id, request=body)


@router.post("/{transaction_id}/decisions")
def decision(
    transaction_id: UUID, body: DecisionRequest, session: DB, user_id: CurrentUser
) -> DecisionResult:
    return decide(session, user_id=user_id, transaction_id=transaction_id, request=body)


@router.post("/{transaction_id}/decisions/{decision_id}/undo")
def undo(
    transaction_id: UUID,
    decision_id: UUID,
    body: VersionRequest,
    session: DB,
    user_id: CurrentUser,
) -> DecisionResult:
    return undo_decision(
        session,
        user_id=user_id,
        transaction_id=transaction_id,
        decision_id=decision_id,
        expected_version=body.expected_version,
    )


@router.get("/{transaction_id}")
def detail(transaction_id: UUID, session: DB, user_id: CurrentUser) -> TransactionDetail:
    try:
        return transaction_detail(session, user_id=user_id, transaction_id=transaction_id)
    except ValueError:
        raise HTTPException(404) from None


def _review(
    session: Session,
    user_id: UUID,
    transaction_id: UUID,
    action: ReviewAction,
    *,
    correction: Correction | None = None,
    keep_id: UUID | None = None,
) -> TransactionDetail:
    try:
        return review_transaction(
            session,
            user_id=user_id,
            transaction_id=transaction_id,
            action=action,
            correction=correction,
            keep_id=keep_id,
        )
    except ValueError as exc:
        raise HTTPException(404 if str(exc) == "transaction_not_found" else 409) from None


@router.patch("/{transaction_id}")
def correct(
    transaction_id: UUID, body: Correction, session: DB, user_id: CurrentUser
) -> TransactionDetail:
    return _review(session, user_id, transaction_id, "correct", correction=body)


@router.post("/{transaction_id}/confirm")
def confirm(transaction_id: UUID, session: DB, user_id: CurrentUser) -> TransactionDetail:
    return _review(session, user_id, transaction_id, "confirm")


@router.post("/{transaction_id}/reject")
def reject(transaction_id: UUID, session: DB, user_id: CurrentUser) -> TransactionDetail:
    return _review(session, user_id, transaction_id, "reject")


@router.post("/{transaction_id}/merge")
def merge(
    transaction_id: UUID, body: MergeRequest, session: DB, user_id: CurrentUser
) -> TransactionDetail:
    return _review(session, user_id, transaction_id, "merge", keep_id=body.keep_id)


@router.post("/{transaction_id}/keep-separate")
def separate(transaction_id: UUID, session: DB, user_id: CurrentUser) -> TransactionDetail:
    return _review(session, user_id, transaction_id, "keep-separate")
