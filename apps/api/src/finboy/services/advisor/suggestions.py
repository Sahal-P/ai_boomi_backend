"""Starter questions picked from the household's own money, with no model call (advisor round).

A budget close to its limit, dues this week, a savings goal and last month's figures each suggest
a question worth asking; a household with no records yet gets questions about getting started.
"""

from datetime import date, timedelta

from finboy.services.advisor.tools import Toolbox
from finboy.services.assistant.templates import CATEGORY_NAMES
from finboy.services.money.engine import PeriodSpec

STARTERS = (
    "How do I start a monthly budget?",
    "How can I save a little every month?",
    "What is an emergency fund, and how much should I keep?",
    "Help me plan for a big purchase",
)


def _name(category: str) -> str:
    return CATEGORY_NAMES.get(category, (category.replace("_", " "),))[0]


def suggestions(box: Toolbox, today: date) -> list[str]:
    summary = box.money_summary(PeriodSpec())
    plan = box.month_plan(PeriodSpec())
    if not (summary.outflow_transaction_count or summary.income_transaction_count):
        return list(STARTERS)
    found: list[str] = []
    tight = sorted(
        (item for item in plan.budgets if item.level != "ok"),
        key=lambda item: (item.level != "over", item.category),
    )
    if tight:
        item = tight[0]
        label = "total" if item.category == "total" else _name(item.category)
        found.append(f"How much is left in my {label} budget?")
    week = PeriodSpec(kind="range", start_date=today, end_date=today + timedelta(days=7))
    if box.dues(week):
        found.append("What do I have to pay this week?")
    found.append("Where did most of my money go this month?")
    found.append("How does this month compare with last month?")
    found.append(
        "Am I on track with my savings goal?"
        if plan.goal_minor
        else "Help me set a savings goal I can keep"
    )
    found.append("Who do I pay the most?")
    return list(dict.fromkeys(found))[:4]
