"""Read-only tools the advisor model may call (docs/advisor-round/contract.md).

Each tool is a thin wrapper over the money engine, so every figure the model sees is the engine's
own, already formatted in rupees. The household is always the signed-in one: the model chooses
periods, categories and payees, never whose records are read. Sums, differences and percentages
are computed here, never by the model. A bad argument returns an error the model can correct.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal, Protocol, get_args
from uuid import UUID

from openai import pydantic_function_tool
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from finboy.core.clock import IST
from finboy.db.models.ledger import Category
from finboy.services.assistant.language import money
from finboy.services.money import budgets, engine, insights
from finboy.services.money.engine import PeriodSpec, TransactionView

PeriodKind = Literal[
    "today",
    "yesterday",
    "this_week",
    "last_week",
    "this_month",
    "last_month",
    "month",
    "range",
    "last_n_months",
]
CATEGORIES: tuple[str, ...] = get_args(Category)
MAX_PAYMENTS = 20
MAX_DAYS_AHEAD = 90


class ToolError(ValueError):
    """A tool argument the model can fix; the message goes back to the model."""


class ToolPeriod(BaseModel):
    """A period of time. Use the named kinds whenever they fit; code works out the dates."""

    model_config = ConfigDict(extra="forbid")
    kind: PeriodKind = Field(
        description=(
            "today, yesterday, this_week (Monday to today), last_week (Monday to Sunday), "
            "this_month, last_month, month (needs year and month), range (needs start_date and "
            "end_date) or last_n_months (needs months: this month and the months before it)"
        )
    )
    year: int | None = Field(description="For kind=month, like 2026")
    month: int | None = Field(description="For kind=month, 1 to 12")
    start_date: str | None = Field(description="For kind=range, YYYY-MM-DD")
    end_date: str | None = Field(description="For kind=range, YYYY-MM-DD")
    months: int | None = Field(description="For kind=last_n_months, 2 to 12")


class MoneySummaryArgs(BaseModel):
    """Money in, money out, what is left after dues, and spending by category for one period."""

    model_config = ConfigDict(extra="forbid")
    period: ToolPeriod


class CategorySpendingArgs(BaseModel):
    """Spending (or income) in one category for a period, or every category when none is named."""

    model_config = ConfigDict(extra="forbid")
    period: ToolPeriod
    category: str | None = Field(description="One of the closed category names, or null for all")


class FindPaymentsArgs(BaseModel):
    """The household's own payments in a period, newest first, optionally for one payee or
    category, with their count and total. Use it to list or total payments to someone."""

    model_config = ConfigDict(extra="forbid")
    period: ToolPeriod
    payee: str | None = Field(description="Part of the payee or payer name, as the person said it")
    category: str | None = Field(description="One of the closed category names, or null")
    direction: Literal["out", "in", "any"] = Field(description="out: paid; in: received")
    limit: int | None = Field(description="How many to list, 1 to 20 (default 10)")


class PayeesAndPeopleArgs(BaseModel):
    """Who they pay most, who pays them, their biggest payments, regular payments, money with
    people (sent to and received from the same person) and small payments, for a period."""

    model_config = ConfigDict(extra="forbid")
    period: ToolPeriod


class DuesArgs(BaseModel):
    """Bills, instalments and other dues still to pay in the coming days, with overdue ones."""

    model_config = ConfigDict(extra="forbid")
    days_ahead: int | None = Field(description="How many days ahead, 1 to 90 (default 30)")


class BudgetsAndGoalArgs(BaseModel):
    """Monthly budgets with spending against each, and the savings goal with what was kept."""

    model_config = ConfigDict(extra="forbid")
    period: ToolPeriod | None = Field(description="A month; null for this month")


class CompareArgs(BaseModel):
    """Compare two periods: amounts, the difference and the percentage change, computed by code."""

    model_config = ConfigDict(extra="forbid")
    metric: Literal["money_out", "money_in", "category"]
    category: str | None = Field(description="For metric=category: a closed category name")
    first: ToolPeriod
    second: ToolPeriod


class AffordMonthlyArgs(BaseModel):
    """Whether a new monthly payment (a SIP, EMI or other) fits this month's tracked money. Use
    only an amount the person said; never guess one."""

    model_config = ConfigDict(extra="forbid")
    monthly_rupees: float = Field(description="The monthly amount in rupees the person said")


@dataclass
class ToolResult:
    """What one call returned: JSON for the model, plus records the web may show as evidence."""

    output: str
    evidence: list[TransactionView] = field(default_factory=list)


class Toolbox(Protocol):
    """The engine reads the tools need; swapped for fixtures in tests and evals."""

    def money_summary(self, period: PeriodSpec) -> engine.MoneySummary: ...
    def category_breakdown(
        self, period: PeriodSpec, category: str | None
    ) -> list[engine.CategoryTotal]: ...
    def find_transactions(
        self, period: PeriodSpec, category: str | None, merchant: str | None
    ) -> list[TransactionView]: ...
    def insights(self, period: PeriodSpec) -> insights.Insights: ...
    def dues(self, period: PeriodSpec) -> list[engine.CommitmentView]: ...
    def month_plan(self, period: PeriodSpec) -> budgets.MonthPlan: ...
    def simulate(self, monthly_minor: int) -> engine.CashFlowSimulation: ...


@dataclass
class EngineToolbox:
    """The real engine, scoped to the signed-in household."""

    session: Session
    user_id: UUID

    def money_summary(self, period: PeriodSpec) -> engine.MoneySummary:
        return engine.money_summary(self.session, user_id=self.user_id, period=period)

    def category_breakdown(
        self, period: PeriodSpec, category: str | None
    ) -> list[engine.CategoryTotal]:
        return engine.category_breakdown(
            self.session,
            user_id=self.user_id,
            period=period,
            category=category,  # type: ignore[arg-type]
        )

    def find_transactions(
        self, period: PeriodSpec, category: str | None, merchant: str | None
    ) -> list[TransactionView]:
        return engine.find_transactions(
            self.session,
            user_id=self.user_id,
            period=period,
            category=category,  # type: ignore[arg-type]
            merchant=merchant,
            status="confirmed",
            limit=200,
        )

    def insights(self, period: PeriodSpec) -> insights.Insights:
        return insights.money_insights(self.session, user_id=self.user_id, period=period)

    def dues(self, period: PeriodSpec) -> list[engine.CommitmentView]:
        return engine.upcoming_commitments(self.session, user_id=self.user_id, period=period)

    def month_plan(self, period: PeriodSpec) -> budgets.MonthPlan:
        return budgets.month_plan(self.session, self.user_id, period)

    def simulate(self, monthly_minor: int) -> engine.CashFlowSimulation:
        return engine.simulate_monthly_commitment(
            self.session,
            user_id=self.user_id,
            monthly_amount_minor=monthly_minor,
            label="Proposed monthly commitment",
        )


def _date(value: str | None, name: str) -> date:
    try:
        return date.fromisoformat(value or "")
    except ValueError:
        raise ToolError(f"{name} must be a date like 2026-11-07") from None


def _first_of_month(day: date, back: int) -> date:
    month = day.year * 12 + day.month - 1 - back
    return date(month // 12, month % 12 + 1, 1)


def to_spec(period: ToolPeriod, today: date) -> PeriodSpec:
    """The engine's period for a tool period; the model never does date arithmetic."""
    kind = period.kind
    if kind == "today":
        return PeriodSpec(kind="range", start_date=today, end_date=today)
    if kind == "yesterday":
        day = today - timedelta(days=1)
        return PeriodSpec(kind="range", start_date=day, end_date=day)
    if kind == "this_week":
        monday = today - timedelta(days=today.weekday())
        return PeriodSpec(kind="range", start_date=monday, end_date=today)
    if kind == "last_week":
        monday = today - timedelta(days=today.weekday() + 7)
        return PeriodSpec(kind="range", start_date=monday, end_date=monday + timedelta(days=6))
    if kind == "this_month":
        return PeriodSpec()
    if kind == "last_month":
        first = _first_of_month(today, 1)
        return PeriodSpec(kind="month", year=first.year, month=first.month)
    if kind == "month":
        if period.year is None or period.month is None or not 1 <= period.month <= 12:
            raise ToolError("kind=month needs year and month (1 to 12)")
        if (period.year, period.month) == (today.year, today.month):
            return PeriodSpec()
        if (period.year, period.month) > (today.year, today.month):
            raise ToolError("That month has not happened yet")
        if period.year < 2000:
            raise ToolError("year must be a full year like 2026")
        return PeriodSpec(kind="month", year=period.year, month=period.month)
    if kind == "range":
        start, end = _date(period.start_date, "start_date"), _date(period.end_date, "end_date")
        if start > end:
            raise ToolError("start_date must not be after end_date")
        if (end - start).days > 731:
            raise ToolError("A range can be at most two years long")
        return PeriodSpec(kind="range", start_date=start, end_date=end)
    months = period.months
    if months is None or not 2 <= months <= 12:
        raise ToolError("kind=last_n_months needs months from 2 to 12")
    return PeriodSpec(kind="range", start_date=_first_of_month(today, months - 1), end_date=today)


def _category(value: str | None) -> str | None:
    if value is None or value in {"", "all", "none"}:
        return None
    if value not in CATEGORIES:
        raise ToolError("category must be one of: " + ", ".join(CATEGORIES))
    return value


def _period_label(start: date, end: date) -> str:
    return f"{start.isoformat()} to {end.isoformat()}"


def _percent(change: int, base: int) -> str | None:
    if base == 0:
        return None
    value = (Decimal(change) * 100 / Decimal(abs(base))).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    return f"{value}%"


def _summary(box: Toolbox, args: MoneySummaryArgs, today: date) -> dict[str, Any]:
    summary = box.money_summary(to_spec(args.period, today))
    return {
        "period": _period_label(summary.period_start, summary.period_end),
        "money_in": money(summary.tracked_income_minor),
        "money_out": money(summary.confirmed_outflows_minor),
        "dues_still_to_pay": money(summary.unresolved_commitments_minor),
        "overdue_dues": money(summary.overdue_commitments_minor),
        "estimated_left_over": money(summary.estimated_unallocated_minor),
        "left_over_means": "money in minus money out minus dues still to pay",
        "payments_in": summary.income_transaction_count,
        "payments_out": summary.outflow_transaction_count,
        "entries_waiting_for_review": summary.pending_review_count,
        "spending_by_category": [
            {
                "category": item.category,
                "amount": money(item.amount_minor),
                "payments": item.transaction_count,
            }
            for item in summary.categories
            if item.amount_minor
        ],
    }


def _category_spending(box: Toolbox, args: CategorySpendingArgs, today: date) -> dict[str, Any]:
    spec = to_spec(args.period, today)
    start, end = engine.period_dates(spec, today)
    rows = box.category_breakdown(spec, _category(args.category))
    return {
        "period": _period_label(start, end),
        "categories": [
            {
                "category": row.category,
                "amount": money(row.amount_minor),
                "payments": row.transaction_count,
            }
            for row in rows
        ],
    }


def _find(box: Toolbox, args: FindPaymentsArgs, today: date) -> tuple[dict[str, Any], list]:
    spec = to_spec(args.period, today)
    start, end = engine.period_dates(spec, today)
    payee = (args.payee or "").strip() or None
    if payee is not None and len(payee) > 80:
        raise ToolError("payee must be at most 80 characters")
    limit = args.limit or 10
    if not 1 <= limit <= MAX_PAYMENTS:
        raise ToolError(f"limit must be from 1 to {MAX_PAYMENTS}")
    found = box.find_transactions(spec, _category(args.category), payee)
    rows = [row for row in found if args.direction == "any" or row.direction == args.direction]
    out = sum(row.amount_minor for row in rows if row.direction == "out")
    back = sum(row.amount_minor for row in rows if row.direction == "in")
    shown = rows[:limit]
    return (
        {
            "period": _period_label(start, end),
            "payments_found": len(rows),
            "only_the_latest_200_counted": len(found) >= 200,
            "total_paid": money(out),
            "total_received": money(back),
            "listed": [
                {
                    "date": row.occurred_at.astimezone(IST).date().isoformat(),
                    "payee": row.merchant,
                    "amount": money(row.amount_minor),
                    "direction": row.direction,
                    "category": row.category,
                }
                for row in shown
            ],
        },
        shown,
    )


def _payees(box: Toolbox, args: PayeesAndPeopleArgs, today: date) -> dict[str, Any]:
    found = box.insights(to_spec(args.period, today))

    def totals(items: list[insights.PayeeTotal]) -> list[dict[str, Any]]:
        return [
            {
                "name": item.name,
                "amount": money(item.amount_minor),
                "payments": item.count,
                "category": item.category,
            }
            for item in items[:5]
        ]

    return {
        "period": _period_label(found.period_start, found.period_end),
        "money_out": money(found.money_out_minor),
        "money_in": money(found.money_in_minor),
        "who_they_pay_most": totals(found.top_payees),
        "who_pays_them_most": totals(found.top_senders),
        "biggest_payments": [
            {
                "name": item.name,
                "amount": money(item.amount_minor),
                "date": item.occurred_at.astimezone(IST).date().isoformat(),
            }
            for item in found.biggest[:3]
        ],
        "regular_payments": [
            {
                "name": item.name,
                "usual_amount": money(item.usual_minor),
                "months_seen": item.months,
                "next_expected": item.next_expected.isoformat(),
            }
            for item in found.regular
        ],
        "regular_payments_per_month": money(found.regular_monthly_minor),
        "money_with_people": [
            {
                "name": person.name,
                "they_sent_to_person": money(person.sent_minor),
                "person_sent_back": money(person.received_minor),
                "difference": money(abs(person.balance_minor)),
                "difference_means": "more came back"
                if person.balance_minor > 0
                else "more went out"
                if person.balance_minor < 0
                else "even",
            }
            for person in found.people
        ],
        "small_payments": {
            "under": money(found.small.threshold_minor),
            "count": found.small.count,
            "amount": money(found.small.amount_minor),
            "per_month": money(found.small.per_month_minor),
        },
    }


def _dues(box: Toolbox, args: DuesArgs, today: date) -> dict[str, Any]:
    days = args.days_ahead or 30
    if not 1 <= days <= MAX_DAYS_AHEAD:
        raise ToolError(f"days_ahead must be from 1 to {MAX_DAYS_AHEAD}")
    end = today + timedelta(days=days)
    rows = box.dues(PeriodSpec(kind="range", start_date=today, end_date=end))
    summary = box.money_summary(PeriodSpec())
    return {
        "from": today.isoformat(),
        "to": end.isoformat(),
        "dues": [
            {
                "label": row.label,
                "amount": money(row.amount_minor),
                "due_date": row.due_date.isoformat(),
                "kind": row.kind,
            }
            for row in rows
        ],
        "total": money(sum(row.amount_minor for row in rows)),
        "overdue_count": summary.overdue_commitment_count,
        "overdue_total": money(summary.overdue_commitments_minor),
    }


def _budgets(box: Toolbox, args: BudgetsAndGoalArgs, today: date) -> dict[str, Any]:
    spec = PeriodSpec() if args.period is None else to_spec(args.period, today)
    plan = box.month_plan(spec)
    return {
        "period": _period_label(plan.start, plan.end),
        "money_in": money(plan.income_minor),
        "money_out": money(plan.spent_minor),
        "kept": money(plan.saved_minor),
        "savings_goal_per_month": money(plan.goal_minor) if plan.goal_minor else None,
        "budgets": [
            {
                "category": item.category,
                "limit": money(item.limit_minor),
                "spent": money(item.spent_minor),
                "left": money(max(item.limit_minor - item.spent_minor, 0)),
                "over_by": money(item.spent_minor - item.limit_minor)
                if item.spent_minor > item.limit_minor
                else None,
                "level": item.level,
            }
            for item in plan.budgets
        ],
        "entries_waiting_for_review": plan.waiting,
    }


def _metric(box: Toolbox, args: CompareArgs, spec: PeriodSpec) -> int:
    if args.metric == "category":
        category = _category(args.category)
        if category is None:
            raise ToolError("metric=category needs a category")
        return sum(row.amount_minor for row in box.category_breakdown(spec, category))
    summary = box.money_summary(spec)
    return (
        summary.confirmed_outflows_minor
        if args.metric == "money_out"
        else summary.tracked_income_minor
    )


def _compare(box: Toolbox, args: CompareArgs, today: date) -> dict[str, Any]:
    first, second = to_spec(args.first, today), to_spec(args.second, today)
    a, b = _metric(box, args, first), _metric(box, args, second)
    change = b - a
    return {
        "metric": args.metric,
        "category": args.category if args.metric == "category" else None,
        "first_period": _period_label(*engine.period_dates(first, today)),
        "first_amount": money(a),
        "second_period": _period_label(*engine.period_dates(second, today)),
        "second_amount": money(b),
        "change": ("up " if change > 0 else "down " if change < 0 else "") + money(abs(change)),
        "percent_change": _percent(change, a),
        "note": "A period that is still running is not finished yet",
    }


def _afford(box: Toolbox, args: AffordMonthlyArgs, today: date, said: set[int]) -> dict[str, Any]:
    try:
        minor = int((Decimal(str(args.monthly_rupees)) * 100).to_integral_value())
    except ArithmeticError:
        raise ToolError("monthly_rupees must be a number") from None
    if minor <= 0 or minor > 10**12:
        raise ToolError("monthly_rupees must be a positive amount")
    if minor not in said:
        raise ToolError(
            "Use only a monthly amount the person said in this conversation; otherwise ask them"
        )
    result = box.simulate(minor)
    summary = result.summary
    return {
        "this_month": _period_label(summary.period_start, summary.period_end),
        "money_in": money(summary.tracked_income_minor),
        "money_out": money(summary.confirmed_outflows_minor),
        "dues_still_to_pay": money(summary.unresolved_commitments_minor),
        "proposed_monthly": money(result.proposed_monthly_minor),
        "left_after_proposal": money(result.remaining_after_proposal_minor),
        "warnings": list(result.warnings),
        "note": "A model of tracked money only, not advice to buy any product",
    }


@dataclass(frozen=True)
class Tool:
    name: str
    args: type[BaseModel]
    run: Callable[..., Any]


TOOLS: tuple[Tool, ...] = (
    Tool("money_summary", MoneySummaryArgs, _summary),
    Tool("category_spending", CategorySpendingArgs, _category_spending),
    Tool("find_payments", FindPaymentsArgs, _find),
    Tool("payees_and_people", PayeesAndPeopleArgs, _payees),
    Tool("dues", DuesArgs, _dues),
    Tool("budgets_and_goal", BudgetsAndGoalArgs, _budgets),
    Tool("compare", CompareArgs, _compare),
    Tool("afford_monthly", AffordMonthlyArgs, _afford),
)
BY_NAME = {tool.name: tool for tool in TOOLS}


def definitions() -> list[Any]:
    """The tool definitions for the Responses API, strict JSON schemas from the models."""
    return [
        pydantic_function_tool(tool.args, name=tool.name, description=tool.args.__doc__)
        for tool in TOOLS
    ]


def run(box: Toolbox, name: str, arguments: str, today: date, said: set[int]) -> ToolResult:
    """One tool call. Errors the model can fix come back as {"error": ...}; nothing raises."""
    tool = BY_NAME.get(name)
    if tool is None:
        return ToolResult(json.dumps({"error": "unknown tool"}))
    try:
        args = tool.args.model_validate_json(arguments or "{}")
        if tool.name == "find_payments":
            output, evidence = _find(box, args, today)  # type: ignore[arg-type]
            return ToolResult(json.dumps(output, ensure_ascii=False), evidence)
        if tool.name == "afford_monthly":
            output = _afford(box, args, today, said)  # type: ignore[arg-type]
        else:
            output = tool.run(box, args, today)
    except ValidationError:
        return ToolResult(json.dumps({"error": "arguments do not match the tool's schema"}))
    except ToolError as error:
        return ToolResult(json.dumps({"error": str(error)}))
    except ValueError:
        return ToolResult(json.dumps({"error": "these arguments are not supported"}))
    return ToolResult(json.dumps(output, ensure_ascii=False))
