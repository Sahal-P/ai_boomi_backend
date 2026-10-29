"""Monthly budgets and the savings goal for the Overview (docs/money-manager-round/contract.md).

The household sets them here or on WhatsApp ("food budget 5000", "save 5000 a month"). Spending is
the money engine's figure for confirmed records; writes are PATCH because the API's CORS policy
allows no PUT.
"""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from finboy.api.deps import CurrentUser
from finboy.db.session import get_session
from finboy.services.money import budgets
from finboy.services.money.http import MoneyRoute
from finboy.services.money.models import PeriodQuery

router = APIRouter(prefix="/money", tags=["money"], route_class=MoneyRoute)
DB = Annotated[Session, Depends(get_session)]


class BudgetItem(BaseModel):
    category: str
    limit_minor: int
    spent_minor: int
    level: Literal["ok", "near", "over"]


class BudgetPlan(BaseModel):
    period_start: date
    period_end: date
    as_of: date
    income_minor: int
    spent_minor: int
    saved_minor: int
    goal_minor: int | None
    items: list[BudgetItem]
    categories: list[str]  # what a budget can be set for: "total" and every spending category


class BudgetChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str
    limit_minor: int | None = Field(gt=0, le=budgets.MAX_MINOR, strict=True)  # None removes it

    @field_validator("category")
    @classmethod
    def budgeted(cls, value: str) -> str:
        if value not in budgets.BUDGETED:
            raise ValueError("Not a spending category")
        return value


class GoalChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal_minor: int | None = Field(gt=0, le=budgets.MAX_MINOR, strict=True)  # None clears it


def _plan(session: Session, user_id: UUID, query: PeriodQuery | None = None) -> BudgetPlan:
    plan = budgets.month_plan(session, user_id, query.to_period() if query else None)
    return BudgetPlan(
        period_start=plan.start,
        period_end=plan.end,
        as_of=plan.as_of,
        income_minor=plan.income_minor,
        spent_minor=plan.spent_minor,
        saved_minor=plan.saved_minor,
        goal_minor=plan.goal_minor,
        items=[
            BudgetItem(
                category=item.category,
                limit_minor=item.limit_minor,
                spent_minor=item.spent_minor,
                level=item.level,
            )
            for item in plan.budgets
        ],
        categories=list(budgets.BUDGETED),
    )


@router.get("/budgets")
def get_budgets(
    session: DB, user_id: CurrentUser, query: Annotated[PeriodQuery, Query()]
) -> BudgetPlan:
    return _plan(session, user_id, query)


@router.patch("/budgets")
def change_budget(session: DB, user_id: CurrentUser, body: BudgetChange) -> BudgetPlan:
    budgets.set_budget(session, user_id, body.category, body.limit_minor)
    session.commit()
    return _plan(session, user_id)


@router.patch("/goal")
def change_goal(session: DB, user_id: CurrentUser, body: GoalChange) -> BudgetPlan:
    budgets.set_goal(session, user_id, body.goal_minor)
    session.commit()
    return _plan(session, user_id)
