from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from finboy.core.config import LOCAL_USER_ID
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

router = APIRouter(prefix="/transactions", tags=["transactions"], route_class=MoneyRoute)
DB = Annotated[Session, Depends(get_session)]


@router.get("")
def transactions(
    session: DB, query: Annotated[TransactionFilters, Query()]
) -> list[TransactionView]:
    return find_transactions(
        session,
        user_id=LOCAL_USER_ID,
        period=query.to_period(),
        category=query.category,
        merchant=query.q,
        status=query.status,
        limit=query.limit,
    )


@router.get("/{transaction_id}")
def detail(transaction_id: UUID, session: DB) -> TransactionDetail:
    try:
        return transaction_detail(session, user_id=LOCAL_USER_ID, transaction_id=transaction_id)
    except ValueError:
        raise HTTPException(404) from None


def _review(
    session: Session,
    transaction_id: UUID,
    action: ReviewAction,
    *,
    correction: Correction | None = None,
    keep_id: UUID | None = None,
) -> TransactionDetail:
    try:
        return review_transaction(
            session,
            user_id=LOCAL_USER_ID,
            transaction_id=transaction_id,
            action=action,
            correction=correction,
            keep_id=keep_id,
        )
    except ValueError as exc:
        raise HTTPException(404 if str(exc) == "transaction_not_found" else 409) from None


@router.patch("/{transaction_id}")
def correct(transaction_id: UUID, body: Correction, session: DB) -> TransactionDetail:
    return _review(session, transaction_id, "correct", correction=body)


@router.post("/{transaction_id}/confirm")
def confirm(transaction_id: UUID, session: DB) -> TransactionDetail:
    return _review(session, transaction_id, "confirm")


@router.post("/{transaction_id}/reject")
def reject(transaction_id: UUID, session: DB) -> TransactionDetail:
    return _review(session, transaction_id, "reject")


@router.post("/{transaction_id}/merge")
def merge(transaction_id: UUID, body: MergeRequest, session: DB) -> TransactionDetail:
    return _review(session, transaction_id, "merge", keep_id=body.keep_id)


@router.post("/{transaction_id}/keep-separate")
def separate(transaction_id: UUID, session: DB) -> TransactionDetail:
    return _review(session, transaction_id, "keep-separate")
