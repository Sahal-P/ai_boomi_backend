"""Read-only tools the advisor model may call (docs/advisor-round/contract.md).

Each tool is a thin wrapper over the money engine, so every figure the model sees is the engine's
own, already formatted in rupees. The household is always the signed-in one: the model chooses
periods, categories and payees, never whose records are read. Sums, differences and percentages
are computed here, never by the model. A bad argument returns an error the model can correct.
search_web is the one tool that reads outside FinBoy: public prices and rates, from a question
that carries none of the household's amounts (docs/names-search-round/contract.md).
propose_changes is the one tool that prepares a change, and it changes nothing itself: the checked
proposal is shown to the household, who apply it with a tap (docs/advisor-edits-round).
"""

import calendar
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Any, Literal, Protocol, get_args
from urllib.parse import urlsplit
from uuid import UUID

from openai import pydantic_function_tool
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from finboy.core.clock import IST
from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.db.models.ledger import Category
from finboy.services import providers
from finboy.services.advisor import changes, embeddings, grounding, history, knowledge, web_search
from finboy.services.assistant.language import money
from finboy.services.money import budgets, engine, insights, payees
from finboy.services.money.engine import PeriodSpec, TransactionView
from finboy.services.whatsapp import english

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
MAX_OFFSET = 180  # find_payments counts the latest 200
# A spending review's fixed costs and saving; the rest of spending is flexible.
FIXED = ("rent", "loan_emi", "utilities", "subscriptions", "phone_recharge", "education", "fees")
SAVING = ("investments",)
MAX_DAYS_AHEAD = 366  # a due next March or next year's January is still a due


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
    offset: int | None = Field(
        default=None,  # strict schemas still ask for it; older callers may leave it out
        description="How many of the newest to skip, to list the next ones (default 0)",
    )


class PayeesAndPeopleArgs(BaseModel):
    """Who they pay most, who pays them, their biggest payments, regular payments, money with
    people (sent to and received from the same person) and small payments, for a period."""

    model_config = ConfigDict(extra="forbid")
    period: ToolPeriod


class OtherPayeesArgs(BaseModel):
    """Payees whose spending is still in "Other", grouped by payee with their payments, total and
    latest date, largest first, and payments categorised "transfer" that still count as
    spending. Use it to see or sort their Other payments; last_n_months with 12 covers most."""

    model_config = ConfigDict(extra="forbid")
    period: ToolPeriod


class SpendingReviewArgs(BaseModel):
    """One month's spending sorted for a review, computed by code: flexible spending by category
    against its usual level in the three months before, fixed costs, saving, "Other", payments
    categorised "transfer" that still count as spending, moves between their own accounts (not
    spending), regular payments and money with people. Use it for where they can improve."""

    model_config = ConfigDict(extra="forbid")
    period: ToolPeriod | None = Field(description="A month; null for this month")


class ChangeArgs(BaseModel):
    """One change. payee_category: every spending payment to a payee. record_category: one
    payment. own_transfer: a payee's payments, or one payment, are moves between their own
    accounts and stop counting as spending. rename_payee: a payee's name, or one payment's.
    budget: a monthly budget. savings_goal: the monthly savings goal."""

    model_config = ConfigDict(extra="forbid")
    type: changes.ChangeType
    payee: str | None = Field(
        description="Every payment to a payee: the name exactly as a tool listed it"
    )
    ref: str | None = Field(
        description="One payment: its ref from find_payments in this answer, like p3"
    )
    category: str | None = Field(
        description=(
            "payee_category, record_category: the new category; budget: a category, or total "
            "for all spending"
        )
    )
    new_name: str | None = Field(description="rename_payee: the name to use, 1 to 60 characters")
    monthly_rupees: float | None = Field(
        description="budget, savings_goal: the monthly amount the person said"
    )
    remove: bool | None = Field(description="budget, savings_goal: true to remove it")


class ProposeChangesArgs(BaseModel):
    """Propose changes to their records for them to approve with one tap: categories, moves
    between their own accounts (which then stop counting as spending), payee names, budgets and
    the savings goal. Nothing changes until they tap Apply, and one Undo puts it all back. Call
    it only when they ask for a change; a new call replaces the earlier proposal."""

    model_config = ConfigDict(extra="forbid")
    changes: list[ChangeArgs] = Field(description="1 to 80 changes")


class DuesArgs(BaseModel):
    """Bills, instalments and other dues still to pay in the coming days, with overdue ones."""

    model_config = ConfigDict(extra="forbid")
    days_ahead: int | None = Field(
        description=(
            "How many days ahead, 1 to 366 (default 30). For a named month, like dues in "
            "January, count the days to that month's end."
        )
    )


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


class SearchKnowledgeArgs(BaseModel):
    """Search FinBoy's reviewed money guides: government schemes (PM-KISAN, Jan Dhan, Atal
    Pension, PMSBY, PMJJBY, Ayushman Bharat, Sukanya Samriddhi, PPF, NPS, Kisan Credit Card),
    loans, EMIs and getting out of debt, fraud safety (UPI, loan apps, OTP and KYC scams), bank
    complaints, credit scores, budgeting and saving methods, insurance, deposits, and what SIPs,
    index funds and diversification are."""

    model_config = ConfigDict(extra="forbid")
    query: str = Field(description="What to look up, in the person's words or in English")


class SearchPastChatsArgs(BaseModel):
    """Search this household's earlier chats with FinBoy, when they refer to something discussed
    before that the summaries shown do not cover."""

    model_config = ConfigDict(extra="forbid")
    query: str = Field(description="What was discussed, in any language")


class SearchWebArgs(BaseModel):
    """Look up a public fact on the web: a price (on-road or ex-showroom, a fee), typical loan
    interest rates in India, fuel or gold rates. Ask in English about the public fact only, with
    the city when the person gave one; never include their amounts, names or other details.
    Returns a short summary and the pages it came from."""

    model_config = ConfigDict(extra="forbid")
    question: str = Field(
        description="The public fact to find, like 'Honda Activa 6G on-road price in Pune'"
    )


class PlanNumbersArgs(BaseModel):
    """Work out planning figures with code, never by hand: the monthly saving for a target by a
    month, how many months a monthly saving takes, or a loan's EMI, total paid and interest from
    a rate the person gave or search_web found. Use only amounts the person said or FinBoy
    showed, including prices search_web found."""

    model_config = ConfigDict(extra="forbid")
    calculation: Literal["save_per_month", "months_to_goal", "emi"]
    amount_rupees: float | None = Field(
        description="The target (save_per_month, months_to_goal) or the price or loan amount (emi)"
    )
    by_month: str | None = Field(description="save_per_month: the target month, YYYY-MM")
    months: int | None = Field(description="emi: the loan length in months")
    monthly_rupees: float | None = Field(description="months_to_goal: the monthly saving")
    annual_interest_percent: float | None = Field(
        description="emi: the yearly interest rate the person gave or search_web found"
    )
    down_payment_rupees: float | None = Field(
        description="emi: what the person pays upfront, taken off amount_rupees"
    )


@dataclass
class Context:
    """What a tool call may rely on besides the engine."""

    today: date
    # Rupee amounts (in paise) the person said in this chat or that their memories hold.
    said: set[int] = field(default_factory=set)
    # Every number in the person's own words and memories (rates, months).
    stated: set[Decimal] = field(default_factory=set)
    # FinBoy's own figures so far: the snapshot and every tool result (grows as tools run).
    known: set[Decimal] = field(default_factory=set)
    # Guides returned by search_knowledge in this chat turn, for citing.
    guides: dict[str, knowledge.Guide] = field(default_factory=dict)
    # Pages search_web cited in this chat turn ("web-1", …), for citing, and their numbers.
    pages: dict[str, web_search.Page] = field(default_factory=dict)
    found: set[Decimal] = field(default_factory=set)
    # Short refs for the payments find_payments listed in this answer ("p1", …), for changes.
    refs: dict[str, UUID] = field(default_factory=dict)
    # The latest checked proposal from propose_changes, saved with the answer.
    proposal: changes.Proposal | None = None


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
    def knowledge(self, query: str) -> list[knowledge.Hit]: ...
    def past_chats(self, query: str) -> list[history.ChatHit]: ...
    def search_web(self, question: str) -> web_search.Found: ...
    def other_payees(self, period: PeriodSpec) -> payees.OtherPayees: ...
    def own_transfers(self, period: PeriodSpec) -> engine.TransferTotal: ...
    def plan_changes(self, proposed: list[changes.Change]) -> changes.Plan: ...


@dataclass
class EngineToolbox:
    """The real engine, scoped to the signed-in household."""

    session: Session
    user_id: UUID
    settings: Settings | None = None
    thread_id: UUID | None = None  # the current chat, left out of past-chat search
    _vectors: dict[str, list[float] | None] = field(default_factory=dict, repr=False)

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

    def _vector(self, query: str) -> list[float] | None:
        """The query's embedding, or None when embeddings are off or unavailable."""
        if self.settings is None or not embeddings.available(self.settings):
            return None
        if query not in self._vectors:
            self.session.rollback()  # never hold the engine's read lock over a network call
            found = embeddings.embed([query], self.settings)
            self._vectors[query] = found[0] if found else None
        return self._vectors[query]

    def knowledge(self, query: str) -> list[knowledge.Hit]:
        vector = self._vector(query)
        self.session.rollback()  # missing guide embeddings are fetched over the network
        return knowledge.search(
            query, settings=self.settings, session=self.session, query_vector=vector
        )

    def past_chats(self, query: str) -> list[history.ChatHit]:
        return history.search(
            self.session,
            self.user_id,
            query,
            exclude=self.thread_id,
            settings=self.settings,
            query_vector=self._vector(query),
        )

    def search_web(self, question: str) -> web_search.Found:
        if self.settings is None:
            raise ProviderUnavailable
        self.session.rollback()  # never hold the engine's read lock over a network call
        return web_search.search(question, self.settings)

    def other_payees(self, period: PeriodSpec) -> payees.OtherPayees:
        return payees.other_payees(self.session, user_id=self.user_id, period=period)

    def own_transfers(self, period: PeriodSpec) -> engine.TransferTotal:
        return engine.own_transfers(self.session, user_id=self.user_id, period=period)

    def plan_changes(self, proposed: list[changes.Change]) -> changes.Plan:
        return changes.plan(changes.load(self.session, self.user_id), proposed)


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


def _summary(box: Toolbox, args: MoneySummaryArgs, ctx: Context) -> dict[str, Any]:
    today = ctx.today
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


def _category_spending(box: Toolbox, args: CategorySpendingArgs, ctx: Context) -> dict[str, Any]:
    today = ctx.today
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


def _find(box: Toolbox, args: FindPaymentsArgs, ctx: Context) -> tuple[dict[str, Any], list]:
    today = ctx.today
    spec = to_spec(args.period, today)
    start, end = engine.period_dates(spec, today)
    payee = (args.payee or "").strip() or None
    if payee is not None and len(payee) > 80:
        raise ToolError("payee must be at most 80 characters")
    limit = args.limit or 10
    if not 1 <= limit <= MAX_PAYMENTS:
        raise ToolError(f"limit must be from 1 to {MAX_PAYMENTS}")
    offset = args.offset or 0
    if not 0 <= offset <= MAX_OFFSET:
        raise ToolError(f"offset must be from 0 to {MAX_OFFSET}")
    found = box.find_transactions(spec, _category(args.category), payee)
    rows = [row for row in found if args.direction == "any" or row.direction == args.direction]
    out = sum(row.amount_minor for row in rows if row.direction == "out")
    back = sum(row.amount_minor for row in rows if row.direction == "in")
    shown = rows[offset : offset + limit]
    return (
        {
            "period": _period_label(start, end),
            "payments_found": len(rows),
            "only_the_latest_200_counted": len(found) >= 200,
            "total_paid": money(out),
            "total_received": money(back),
            "offset": offset,
            "remaining": max(len(rows) - offset - len(shown), 0),
            "listed": [
                {
                    "ref": _ref(ctx, row.id),
                    "date": row.occurred_at.astimezone(IST).date().isoformat(),
                    "payee": row.merchant,
                    "amount": money(row.amount_minor),
                    "direction": row.direction,
                    "category": row.category,
                    "own_account_move": row.kind == "transfer",
                }
                for row in shown
            ],
        },
        shown,
    )


def _ref(ctx: Context, record_id: UUID) -> str:
    """A short, stable ref for a listed payment, so the model never handles record IDs."""
    for ref, known in ctx.refs.items():
        if known == record_id:
            return ref
    ref = f"p{len(ctx.refs) + 1}"
    ctx.refs[ref] = record_id
    return ref


def _payees(box: Toolbox, args: PayeesAndPeopleArgs, ctx: Context) -> dict[str, Any]:
    today = ctx.today
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


def _other_payees(box: Toolbox, args: OtherPayeesArgs, ctx: Context) -> dict[str, Any]:
    spec = to_spec(args.period, ctx.today)
    start, end = engine.period_dates(spec, ctx.today)
    found = box.other_payees(spec)
    return {
        "period": _period_label(start, end),
        "spending": money(found.spent_minor),
        "in_other": money(found.other_minor),
        "payments_in_other": found.other_count,
        "share_of_spending": _percent(found.other_minor, found.spent_minor),
        "payees": [
            {
                "payee": item.name,
                "payments": item.count,
                "total": money(item.amount_minor),
                "latest": item.latest.isoformat(),
                "remembered_category": item.remembered,
            }
            for item in found.items
        ],
        "payees_found": found.payees,
        "payees_listed": len(found.items),
        "unknown_or_hidden_names": {
            "payments": found.unnamed_count,
            "total": money(found.unnamed_minor),
            "note": "May be several people: list them with find_payments and change one by ref",
        },
        "categorised_transfer_still_counted_as_spending": {
            "payments": found.transfer_count,
            "total": money(found.transfer_minor),
        },
    }


def _average(total: int, months: int) -> int:
    return int((Decimal(total) / months).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _review(box: Toolbox, args: SpendingReviewArgs, ctx: Context) -> dict[str, Any]:
    today = ctx.today
    spec = PeriodSpec() if args.period is None else to_spec(args.period, today)
    start, end = engine.period_dates(spec, today)
    if start.day != 1 or end != start.replace(day=calendar.monthrange(start.year, start.month)[1]):
        raise ToolError("spending_review takes one month: this_month, last_month or month")
    summary = box.money_summary(spec)
    earlier = [
        box.money_summary(PeriodSpec(kind="month", year=first.year, month=first.month))
        for first in (_first_of_month(start, back) for back in (1, 2, 3))
    ]
    counted = [item for item in earlier if item.outflow_transaction_count]
    usual: dict[str, int] = {}
    for item in counted:
        for row in item.categories:
            usual[row.category] = usual.get(row.category, 0) + row.amount_minor
    found = box.insights(spec)
    own = box.own_transfers(spec)
    spent = summary.confirmed_outflows_minor

    def flexible(item: engine.CategoryTotal) -> dict[str, Any]:
        if not counted:
            return {"category": item.category, "amount": money(item.amount_minor)}
        average = _average(usual.get(item.category, 0), len(counted))
        change = item.amount_minor - average
        return {
            "category": item.category,
            "amount": money(item.amount_minor),
            "payments": item.transaction_count,
            "usual_per_month": money(average),
            "change": ("up " if change > 0 else "down " if change < 0 else "") + money(abs(change)),
            "percent_change": _percent(change, average),
        }

    spending = [item for item in summary.categories if item.amount_minor > 0]
    other = next((item for item in spending if item.category == "other"), None)
    moved = next((item for item in spending if item.category == "transfer"), None)
    fixed = [item for item in spending if item.category in FIXED]
    running = start <= today <= end
    return {
        "month": _period_label(start, end),
        "still_running": running,
        "days_counted": (today - start).days + 1 if running else None,
        "spending": money(spent),
        "money_in": money(summary.tracked_income_minor),
        "months_averaged": len(counted),
        "flexible_spending": [
            flexible(item)
            for item in spending
            if item.category not in {*FIXED, *SAVING, "other", "transfer"}
        ],
        "fixed_costs": [
            {"category": item.category, "amount": money(item.amount_minor)} for item in fixed
        ],
        "fixed_total": money(sum(item.amount_minor for item in fixed)),
        "saving": [
            {"category": item.category, "amount": money(item.amount_minor)}
            for item in spending
            if item.category in SAVING
        ],
        "other_not_sorted": {
            "amount": money(other.amount_minor),
            "payments": other.transaction_count,
            "share_of_spending": _percent(other.amount_minor, spent),
        }
        if other
        else None,
        "categorised_transfer_still_counted": {
            "amount": money(moved.amount_minor),
            "payments": moved.transaction_count,
            "note": "Counted as spending: ask whether these are moves between their own accounts",
        }
        if moved
        else None,
        "own_account_moves_not_spending": {
            "amount": money(own.amount_minor),
            "payments": own.count,
        },
        "regular_payments": [
            {
                "name": item.name,
                "usual_amount": money(item.usual_minor),
                "next_expected": item.next_expected.isoformat(),
            }
            for item in found.regular[:5]
        ],
        "regular_payments_per_month": money(found.regular_monthly_minor),
        "money_with_people": [
            {
                "name": person.name,
                "they_sent_to_person": money(person.sent_minor),
                "person_sent_back": money(person.received_minor),
            }
            for person in found.people[:3]
        ],
        "entries_waiting_for_review": summary.pending_review_count,
        "note": (
            "Improve flexible spending that grew. Fixed costs, saving and moves between their own "
            "accounts are not where to cut first. A running month is set against whole months."
        ),
    }


def _dues(box: Toolbox, args: DuesArgs, ctx: Context) -> dict[str, Any]:
    today = ctx.today
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


def _budgets(box: Toolbox, args: BudgetsAndGoalArgs, ctx: Context) -> dict[str, Any]:
    today = ctx.today
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


def _compare(box: Toolbox, args: CompareArgs, ctx: Context) -> dict[str, Any]:
    today = ctx.today
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


def _afford(box: Toolbox, args: AffordMonthlyArgs, ctx: Context) -> dict[str, Any]:
    try:
        minor = int((Decimal(str(args.monthly_rupees)) * 100).to_integral_value())
    except ArithmeticError:
        raise ToolError("monthly_rupees must be a number") from None
    if minor <= 0 or minor > 10**12:
        raise ToolError("monthly_rupees must be a positive amount")
    if minor not in ctx.said:
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


def _rupees(value: float | None, name: str) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except ArithmeticError, TypeError:
        raise ToolError(f"{name} is needed") from None
    if amount <= 0 or amount > Decimal(10**10):
        raise ToolError(f"{name} must be a positive amount")
    return amount


def _given(amount: Decimal, ctx: Context, name: str) -> None:
    """An input amount must be one the person said or FinBoy showed, never a guess."""
    if int(amount * 100) not in ctx.said and amount not in ctx.known:
        raise ToolError(f"Use a {name} the person said or FinBoy showed; otherwise ask them")


def _whole(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_CEILING))


def _plan(box: Toolbox, args: PlanNumbersArgs, ctx: Context) -> dict[str, Any]:
    if args.calculation == "save_per_month":
        target = _rupees(args.amount_rupees, "amount_rupees")
        _given(target, ctx, "target")
        try:
            year, month = (int(part) for part in (args.by_month or "").split("-"))
            last = date(year, month, 1)
        except ValueError:
            raise ToolError("by_month must look like 2027-03") from None
        months = (year * 12 + month) - (ctx.today.year * 12 + ctx.today.month)
        if not 1 <= months <= 600:
            raise ToolError("by_month must be a later month, at most 50 years ahead")
        return {
            "target": money(int(target * 100)),
            "months_counted": months,
            "from_month": _first_of_month(ctx.today, -1).strftime("%B %Y"),
            "to_month": last.strftime("%B %Y"),
            "save_each_month": money(_whole(target / months) * 100),
        }
    if args.calculation == "months_to_goal":
        target = _rupees(args.amount_rupees, "amount_rupees")
        monthly = _rupees(args.monthly_rupees, "monthly_rupees")
        _given(target, ctx, "target")
        _given(monthly, ctx, "monthly amount")
        months = _whole(target / monthly)
        return {
            "target": money(int(target * 100)),
            "each_month": money(int(monthly * 100)),
            "months_needed": months,
        }
    price = _rupees(args.amount_rupees, "amount_rupees")
    _given(price, ctx, "loan amount or price")
    upfront: dict[str, str] = {}
    principal = price
    if args.down_payment_rupees:  # 0 means nothing upfront
        down = _rupees(args.down_payment_rupees, "down_payment_rupees")
        _given(down, ctx, "down payment")
        if down >= price:
            raise ToolError("down_payment_rupees must be less than amount_rupees")
        principal = price - down
        upfront = {"price": money(int(price * 100)), "down_payment": money(int(down * 100))}
    months = args.months or 0
    if not 1 <= months <= 480:
        raise ToolError("months must be from 1 to 480")
    if args.annual_interest_percent is None:
        raise ToolError("annual_interest_percent is needed; ask the person for the rate")
    rate = Decimal(str(args.annual_interest_percent))
    if (rate not in ctx.stated and rate not in ctx.found) or not Decimal(0) <= rate <= Decimal(60):
        raise ToolError(
            "Use only an interest rate the person gave or search_web found; otherwise ask them"
        )
    monthly_rate = rate / 1200
    if monthly_rate == 0:
        emi = principal / months
    else:
        growth = (1 + monthly_rate) ** months
        emi = principal * monthly_rate * growth / (growth - 1)
    emi_whole = _whole(emi)
    total = emi_whole * months
    return upfront | {
        "loan": money(int(principal * 100)),
        "annual_rate": f"{rate.normalize():f}%",
        "months": months,
        "emi": money(emi_whole * 100),
        "total_paid": money(total * 100),
        "total_interest": money(max(total * 100 - int(principal * 100), 0)),
        "note": "An estimate from the rate given; the lender's own schedule may differ slightly",
    }


def _minor(value: float | None) -> int:
    try:
        minor = int((Decimal(str(value)) * 100).to_integral_value(rounding=ROUND_HALF_UP))
    except ArithmeticError, TypeError, ValueError:
        raise ToolError("monthly_rupees must be a number") from None
    if not 0 < minor <= budgets.MAX_MINOR:
        raise ToolError("monthly_rupees must be from ₹1 to ₹1 crore")
    return minor


def _change(item: ChangeArgs, ctx: Context) -> changes.Change:
    """One change, checked for what code can tell without the records."""
    if item.type in {"budget", "savings_goal"}:
        amount = None
        if not item.remove:
            amount = _minor(item.monthly_rupees)
            if amount not in ctx.said:
                raise ToolError("use only a monthly amount the person said; otherwise ask them")
        if item.type == "savings_goal":
            return changes.Change(type="savings_goal", amount_minor=amount)
        named = (item.category or "").strip().lower()
        category = "total" if named in {"total", "overall"} else _category(item.category)
        if category is None:
            raise ToolError("a budget needs a spending category, or total for all spending")
        return changes.Change(type="budget", category=category, amount_minor=amount)
    target: dict[str, Any]
    if item.ref:
        record_id = ctx.refs.get(item.ref.strip().lower())
        if record_id is None:
            raise ToolError("ref must be one find_payments listed in this answer, like p3")
        target = {"record_id": record_id}
    else:
        payee = " ".join((item.payee or "").split())
        if not payee or len(payee) > 160:
            raise ToolError("give the payee's name as a tool listed it, or one payment's ref")
        target = {"payee": payee}
    if item.type == "payee_category" and "payee" not in target:
        raise ToolError("payee_category is for a payee; use record_category for one payment")
    if item.type == "record_category" and "record_id" not in target:
        raise ToolError("record_category needs a ref; use payee_category for a payee")
    if item.type in {"payee_category", "record_category"}:
        category = _category(item.category)
        if category is None:
            raise ToolError("category is needed")
        if category == "transfer":
            raise ToolError(
                "for moves between their own accounts use own_transfer; for money to people use "
                "friends, remittance or family_events"
            )
        return changes.Change(type=item.type, category=category, **target)
    if item.type == "own_transfer":
        return changes.Change(type="own_transfer", **target)
    name = changes.clean_name(item.new_name)
    if name is None:
        raise ToolError("new_name must be 1 to 60 characters, and not Unknown")
    return changes.Change(type="rename_payee", new_name=name, **target)


def _propose(box: Toolbox, args: ProposeChangesArgs, ctx: Context) -> dict[str, Any]:
    if not 1 <= len(args.changes) <= changes.MAX_CHANGES:
        raise ToolError(f"propose 1 to {changes.MAX_CHANGES} changes")
    built: list[changes.Change] = []
    problems: list[str] = []
    for number, item in enumerate(args.changes, start=1):
        try:
            built.append(_change(item, ctx))
        except ToolError as error:
            problems.append(f"change {number}: {error}")
    found = None if problems else box.plan_changes(built)
    if found is not None:
        problems = found.problems
    if found is None or problems:
        raise ToolError(
            "Nothing was proposed. Fix these and call again: " + "; ".join(problems[:6])
        )
    if found.count == 0:
        raise ToolError("Nothing would change: those payments, budgets and goal already look so")
    ctx.proposal = changes.Proposal(built, found)
    return {
        "proposed": found.count,
        "shown_to_them": [changes.line(group, english) for group in found.groups],
        "left_as_they_set_it": found.kept,
        "note": (
            "Nothing has changed yet. FinBoy shows these lines with Apply and Not now buttons. "
            "Describe the proposal in a line or two with these figures, say nothing changes "
            "until they tap Apply, and never say it is done."
        ),
    }


def _search_knowledge(box: Toolbox, args: SearchKnowledgeArgs, ctx: Context) -> dict[str, Any]:
    query = args.query.strip()
    if not query or len(query) > 300:
        raise ToolError("query must be 1 to 300 characters")
    hits = box.knowledge(query)
    for hit in hits:
        ctx.guides[hit.guide.id] = hit.guide
    return knowledge.tool_output(hits)


def _search_past_chats(box: Toolbox, args: SearchPastChatsArgs, ctx: Context) -> dict[str, Any]:
    query = args.query.strip()
    if not query or len(query) > 300:
        raise ToolError("query must be 1 to 300 characters")
    hits = box.past_chats(query)
    if not hits:
        return {"chats": [], "note": "No earlier chat matches; say so if they ask."}
    return {
        "chats": [
            {
                "date": hit.last_at.astimezone(IST).date().isoformat(),
                "title": hit.title,
                "summary": hit.summary,
                "closest_exchange": hit.excerpt,
            }
            for hit in hits
        ],
        "note": "These are earlier chats; figures in them may be out of date.",
    }


def _search_web(box: Toolbox, args: SearchWebArgs, ctx: Context) -> dict[str, Any]:
    question = " ".join(args.question.split())
    if not question or len(question) > 300:
        raise ToolError("question must be 1 to 300 characters")
    # Only the public fact leaves FinBoy: an amount in the question could be the household's own.
    if any(money_like for _, money_like in grounding.figures(question)):
        raise ToolError("Leave amounts out of the search and ask only about the public fact")
    try:
        found = box.search_web(question)
    except ProviderUnavailable:
        raise ToolError("Web search is unavailable right now; answer without it") from None
    if found.summary is None:
        return {"found": None, "note": "The web did not say; tell them you couldn't find it."}
    cited = []
    for page in found.pages:
        key = f"web-{len(ctx.pages) + 1}"
        ctx.pages[key] = page
        cited.append({"id": key, "title": page.title, "site": urlsplit(page.url).hostname})
    ctx.found |= {value for value, _ in grounding.figures(found.summary)}
    return {
        "found": found.summary,
        "pages": cited,
        "note": (
            "Public figures from the web, not the person's records. They vary by city, lender "
            "and date: say they are approximate and put the ids of the pages you used in sources."
        ),
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
    Tool("other_payees", OtherPayeesArgs, _other_payees),
    Tool("spending_review", SpendingReviewArgs, _review),
    Tool("dues", DuesArgs, _dues),
    Tool("budgets_and_goal", BudgetsAndGoalArgs, _budgets),
    Tool("compare", CompareArgs, _compare),
    Tool("afford_monthly", AffordMonthlyArgs, _afford),
    Tool("plan_numbers", PlanNumbersArgs, _plan),
    Tool("search_past_chats", SearchPastChatsArgs, _search_past_chats),
    Tool("search_knowledge", SearchKnowledgeArgs, _search_knowledge),
    Tool("search_web", SearchWebArgs, _search_web),
    Tool("propose_changes", ProposeChangesArgs, _propose),
)
BY_NAME = {tool.name: tool for tool in TOOLS}


def offered(settings: Settings | None) -> tuple[Tool, ...]:
    """The tools the model may call: the guides only while the library is released, web search
    only while it is released and configured, and proposals only while edits are released."""
    hidden = set()
    if settings is None or not settings.knowledge_enabled:
        hidden.add("search_knowledge")
    if settings is None or providers.web_search(settings) != "configured":
        hidden.add("search_web")
    if settings is None or not settings.advisor_edits_enabled:
        hidden.add("propose_changes")
    return tuple(tool for tool in TOOLS if tool.name not in hidden)


def definitions(settings: Settings | None = None) -> list[Any]:
    """The tool definitions for the Responses API, strict JSON schemas from the models."""
    return [
        pydantic_function_tool(tool.args, name=tool.name, description=tool.args.__doc__)
        for tool in offered(settings)
    ]


def run(
    box: Toolbox,
    name: str,
    arguments: str,
    ctx: Context,
    settings: Settings | None = None,
) -> ToolResult:
    """One tool call. Errors the model can fix come back as {"error": ...}; nothing raises."""
    tool = BY_NAME.get(name)
    if tool is None or (settings is not None and tool not in offered(settings)):
        return ToolResult(json.dumps({"error": "unknown tool"}))
    try:
        args = tool.args.model_validate_json(arguments or "{}")
        if tool.name == "find_payments":
            output, evidence = _find(box, args, ctx)  # type: ignore[arg-type]
            return ToolResult(json.dumps(output, ensure_ascii=False), evidence)
        output = tool.run(box, args, ctx)
    except ValidationError:
        return ToolResult(json.dumps({"error": "arguments do not match the tool's schema"}))
    except ToolError as error:
        return ToolResult(json.dumps({"error": str(error)}))
    except ValueError:
        return ToolResult(json.dumps({"error": "these arguments are not supported"}))
    return ToolResult(json.dumps(output, ensure_ascii=False))
