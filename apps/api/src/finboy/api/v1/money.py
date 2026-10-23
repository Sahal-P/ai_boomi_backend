from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from finboy.core.config import LOCAL_USER_ID
from finboy.db.session import get_session
from finboy.services.money.engine import (
    CashFlowSimulation,
    CommitmentView,
    MoneySummary,
    money_summary,
    simulate_monthly_commitment,
    upcoming_commitments,
)
from finboy.services.money.http import MoneyRoute
from finboy.services.money.models import PeriodQuery, SimulationRequest

router = APIRouter(prefix="/money", tags=["money"], route_class=MoneyRoute)
DB = Annotated[Session, Depends(get_session)]


@router.get("/summary")
def summary(session: DB, query: Annotated[PeriodQuery, Query()]) -> MoneySummary:
    return money_summary(session, user_id=LOCAL_USER_ID, period=query.to_period())


@router.get("/commitments")
def commitments(session: DB, query: Annotated[PeriodQuery, Query()]) -> list[CommitmentView]:
    return upcoming_commitments(session, user_id=LOCAL_USER_ID, period=query.to_period())


@router.post("/simulations")
def simulate(session: DB, body: SimulationRequest) -> CashFlowSimulation:
    return simulate_monthly_commitment(
        session,
        user_id=LOCAL_USER_ID,
        monthly_amount_minor=body.monthly_amount_minor,
        label=body.label,
    )
