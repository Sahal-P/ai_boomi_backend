"""Monthly budgets and the savings goal, measured against confirmed records only.

docs/money-manager-round/contract.md. Spending is the engine's own figure (`money_summary`):
confirmed outflows by category, refunds netted, transfers between own accounts excluded. Money put
into savings or investments counts towards the savings goal, not against it.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal, get_args
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from finboy.db.models.core import User
from finboy.db.models.money import Budget
from finboy.services.ingestion.types import Category
from finboy.services.money.engine import PeriodSpec, money_summary

INCOME: frozenset[str] = frozenset(
    {"salary", "other_income", "wages", "farm_sales", "govt_benefit", "transfer"}
)
# What a budget can be set for: every spending category, or "total" for all spending.
BUDGETED: tuple[str, ...] = ("total", *(c for c in get_args(Category) if c not in INCOME))
MAX_MINOR = 10**9  # ₹1 crore, like quick add


@dataclass(frozen=True)
class BudgetStatus:
    category: str  # a spending Category or "total"
    limit_minor: int
    spent_minor: int

    @property
    def level(self) -> Literal["ok", "near", "over"]:
        """ "near" from 80% of the limit; "over" once spending passes it."""
        if self.spent_minor > self.limit_minor:
            return "over"
        return "near" if self.spent_minor * 5 >= self.limit_minor * 4 else "ok"


@dataclass(frozen=True)
class MonthPlan:
    start: date
    end: date
    as_of: date
    income_minor: int
    spent_minor: int
    saved_minor: int  # income minus spending, with money put into savings counted as kept
    goal_minor: int | None
    budgets: list[BudgetStatus]
    top: list[tuple[str, int]]  # the largest spending categories, at most three
    waiting: int  # entries FinBoy was unsure about, still waiting for review

    def budget_for(self, category: str) -> BudgetStatus | None:
        """The category's own budget, else the budget for all spending."""
        found = {item.category: item for item in self.budgets}
        return found.get(category) or found.get("total")


def month_plan(session: Session, user_id: UUID, period: PeriodSpec | None = None) -> MonthPlan:
    summary = money_summary(session, user_id=user_id, period=period or PeriodSpec())
    spent: dict[str, int] = {item.category: item.amount_minor for item in summary.categories}
    limits = session.execute(
        select(Budget.category, Budget.limit_minor).where(Budget.user_id == user_id)
    ).all()
    goal = session.scalar(select(User.monthly_savings_goal_minor).where(User.id == user_id))
    budgets = [
        BudgetStatus(
            category,
            limit,
            summary.confirmed_outflows_minor
            if category == "total"
            else max(0, spent.get(category, 0)),
        )
        for category, limit in limits
    ]
    budgets.sort(key=lambda item: (item.category != "total", -item.spent_minor / item.limit_minor))
    kept = max(0, spent.get("investments", 0))
    return MonthPlan(
        start=summary.period_start,
        end=summary.period_end,
        as_of=summary.as_of,
        income_minor=summary.tracked_income_minor,
        spent_minor=summary.confirmed_outflows_minor,
        saved_minor=summary.tracked_income_minor - summary.confirmed_outflows_minor + kept,
        goal_minor=goal,
        budgets=budgets,
        top=[
            (item.category, item.amount_minor)
            for item in summary.categories
            if item.amount_minor > 0 and item.category != "investments"
        ][:3],
        waiting=summary.pending_review_count,
    )


def set_budget(session: Session, user_id: UUID, category: str, limit_minor: int | None) -> None:
    """Set or (with None) remove one monthly budget; the caller commits."""
    if category not in BUDGETED or (limit_minor is not None and not 0 < limit_minor <= MAX_MINOR):
        raise ValueError("invalid_budget")
    if limit_minor is None:
        session.execute(
            delete(Budget).where(Budget.user_id == user_id, Budget.category == category)
        )
        return
    session.execute(
        insert(Budget)
        .values(user_id=user_id, category=category, limit_minor=limit_minor)
        .on_conflict_do_update(
            index_elements=[Budget.user_id, Budget.category],
            set_={"limit_minor": limit_minor, "updated_at": func.now()},
        )
    )


def set_goal(session: Session, user_id: UUID, goal_minor: int | None) -> None:
    """Set or (with None) clear the monthly savings goal; the caller commits."""
    if goal_minor is not None and not 0 < goal_minor <= MAX_MINOR:
        raise ValueError("invalid_goal")
    session.execute(
        update(User).where(User.id == user_id).values(monthly_savings_goal_minor=goal_minor)
    )
