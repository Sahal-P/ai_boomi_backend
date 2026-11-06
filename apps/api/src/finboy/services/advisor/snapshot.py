"""A compact picture of the household's money, preloaded so most questions need no tool call.

Built from the same engine reads the tools use (docs/advisor-round/contract.md): this month and
last month, budgets and the savings goal, dues ahead, who they pay, regular payments, money with
people and their usual income day. Figures are formatted rupees, as the model must quote them.
"""

from collections import Counter
from datetime import date, timedelta
from typing import Any

from finboy.core.clock import IST
from finboy.services.advisor.tools import Toolbox, _first_of_month
from finboy.services.assistant.language import money
from finboy.services.money.engine import MoneySummary, PeriodSpec

INCOME_CATEGORIES = {"salary", "wages", "farm_sales", "govt_benefit", "other_income"}


def _month(summary: MoneySummary) -> dict[str, Any]:
    return {
        "period": f"{summary.period_start.isoformat()} to {summary.period_end.isoformat()}",
        "money_in": money(summary.tracked_income_minor),
        "money_out": money(summary.confirmed_outflows_minor),
        "estimated_left_over": money(summary.estimated_unallocated_minor),
        "top_spending": [
            {"category": item.category, "amount": money(item.amount_minor)}
            for item in sorted(summary.categories, key=lambda c: -c.amount_minor)[:3]
            if item.amount_minor
        ],
    }


def income_pattern(box: Toolbox, today: date) -> dict[str, Any]:
    """The usual day income arrives, from the last three months of confirmed income."""
    start = _first_of_month(today, 2)
    rows = [
        row
        for row in box.find_transactions(
            PeriodSpec(kind="range", start_date=start, end_date=today), None, None
        )
        if row.direction == "in" and row.category in INCOME_CATEGORIES
    ]
    if not rows:
        return {"kind": "unknown"}
    days = Counter(row.occurred_at.astimezone(IST).day for row in rows)
    months = {row.occurred_at.astimezone(IST).strftime("%Y-%m") for row in rows}
    day, count = days.most_common(1)[0]
    regular = len(months) >= 2 and count >= 2 and len(rows) <= len(months) * 2
    return {
        "kind": "regular" if regular else "irregular",
        "usual_day_of_month": day if regular else None,
        "payments_seen": len(rows),
        "months_seen": len(months),
    }


def build(box: Toolbox, today: date) -> tuple[dict[str, Any], str, int]:
    """(snapshot, data version, entries waiting for review)."""
    this_month = box.money_summary(PeriodSpec())
    last = _first_of_month(today, 1)
    last_month = box.money_summary(PeriodSpec(kind="month", year=last.year, month=last.month))
    plan = box.month_plan(PeriodSpec())
    dues = box.dues(PeriodSpec(kind="range", start_date=today, end_date=today + timedelta(days=30)))
    found = box.insights(
        PeriodSpec(kind="range", start_date=_first_of_month(today, 2), end_date=today)
    )
    goal_left = max((plan.goal_minor or 0) - max(plan.saved_minor, 0), 0)
    snapshot: dict[str, Any] = {
        "today": today.isoformat(),
        "weekday": today.strftime("%A"),
        "this_month": _month(this_month),
        "last_month": _month(last_month),
        "entries_waiting_for_review": this_month.pending_review_count,
        "budgets_this_month": [
            {
                "category": item.category,
                "limit": money(item.limit_minor),
                "spent": money(item.spent_minor),
                "left": money(max(item.limit_minor - item.spent_minor, 0)),
                "level": item.level,
            }
            for item in plan.budgets
        ],
        "savings_goal": {
            "per_month": money(plan.goal_minor),
            "kept_this_month": money(plan.saved_minor),
            "still_to_keep": money(goal_left),
        }
        if plan.goal_minor
        else None,
        "dues_next_30_days": [
            {"label": row.label, "amount": money(row.amount_minor), "due": row.due_date.isoformat()}
            for row in dues[:8]
        ],
        "overdue_dues": {
            "count": this_month.overdue_commitment_count,
            "total": money(this_month.overdue_commitments_minor),
        }
        if this_month.overdue_commitment_count
        else None,
        "last_3_months": {
            "period": f"{found.period_start.isoformat()} to {found.period_end.isoformat()}",
            "who_they_pay_most": [
                {"name": item.name, "amount": money(item.amount_minor), "payments": item.count}
                for item in found.top_payees[:5]
            ],
            "regular_payments": [
                {
                    "name": item.name,
                    "usual_amount": money(item.usual_minor),
                    "next_expected": item.next_expected.isoformat(),
                }
                for item in found.regular[:6]
            ],
            "money_with_people": [
                {
                    "name": person.name,
                    "they_sent_to_person": money(person.sent_minor),
                    "person_sent_back": money(person.received_minor),
                }
                for person in found.people[:3]
            ],
        },
        "income_pattern": income_pattern(box, today),
    }
    return snapshot, this_month.data_version, this_month.pending_review_count
