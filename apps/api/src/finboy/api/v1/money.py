from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.api.deps import CurrentUser
from finboy.db.models.ledger import Commitment
from finboy.db.session import get_session
from finboy.services.money.compat import simulation_response
from finboy.services.money.engine import (
    CashFlowSimulation,
    CommitmentView,
    MoneySummary,
    commitment_view,
    money_summary,
    simulate_monthly_commitment,
    upcoming_commitments,
)
from finboy.services.money.http import MoneyRoute
from finboy.services.money.models import PeriodQuery, SimulationRequest
from finboy.services.ux.contracts import ObligationDetail, ObligationList
from finboy.services.ux.obligations import (
    ObligationCorrection,
    correct_obligation,
    obligation_detail,
)
from finboy.services.ux.state import data_version

router = APIRouter(prefix="/money", tags=["money"], route_class=MoneyRoute)
DB = Annotated[Session, Depends(get_session)]


@router.get("/summary")
def summary(
    session: DB, user_id: CurrentUser, query: Annotated[PeriodQuery, Query()]
) -> MoneySummary:
    return money_summary(session, user_id=user_id, period=query.to_period())


@router.get("/commitments")
def commitments(
    session: DB, user_id: CurrentUser, query: Annotated[PeriodQuery, Query()]
) -> list[CommitmentView]:
    return upcoming_commitments(session, user_id=user_id, period=query.to_period())


@router.post("/simulations")
def simulate(session: DB, user_id: CurrentUser, body: SimulationRequest) -> CashFlowSimulation:
    result = simulate_monthly_commitment(
        session,
        user_id=user_id,
        monthly_amount_minor=body.monthly_amount_minor,
        label=body.label,
    )
    return simulation_response(result, include_overdue_line=body.include_overdue_line)


@router.get("/obligations", response_model=ObligationList)
def obligations(
    session: DB,
    user_id: CurrentUser,
    status: Literal["unresolved", "all", "paid", "dismissed"] = "unresolved",
) -> dict:
    # A spoken pilot due waiting for the household's "हाँ" is never listed or counted.
    query = select(Commitment).where(
        Commitment.user_id == user_id,
        Commitment.dataset == "household",
        Commitment.status != "pending",
    )
    if status != "all":
        query = query.where(Commitment.status == ("upcoming" if status == "unresolved" else status))
    version = data_version(session, user_id)
    return {
        "items": [
            commitment_view(row, version=version)
            for row in session.scalars(query.order_by(Commitment.due_date, Commitment.id))
        ],
        "data_version": version,
    }


@router.get("/obligations/{obligation_id}", response_model=ObligationDetail)
def obligation(obligation_id: UUID, session: DB, user_id: CurrentUser) -> dict:
    return obligation_detail(session, user_id=user_id, obligation_id=obligation_id)


@router.patch("/obligations/{obligation_id}", response_model=ObligationDetail)
def repair_obligation(
    obligation_id: UUID, body: ObligationCorrection, session: DB, user_id: CurrentUser
) -> dict:
    return correct_obligation(session, user_id=user_id, obligation_id=obligation_id, request=body)
