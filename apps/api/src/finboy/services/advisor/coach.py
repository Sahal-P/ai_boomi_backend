"""The proactive coach (docs/advisor-round/contract.md, phase 3).

Detectors read the household's money through the same read-only engine Toolbox the advisor's
tools use, so every figure is the engine's own: a budget close to or over its limit, the savings
goal from the 20th, a due within two days, the month's salary or wages arriving, a payment more
than three times the usual, a newly regular payment and, on Sundays, the week. Home shows the top
few ("For you"); WhatsApp sends opted-in households at most one a day (whatsapp/coach.py).

Each nudge has a line written by code from the engine's figures, in English, Hindi or Malayalam:
the web card's text, the approved template's parameter and every fallback. Inside WhatsApp's
24-hour window the advisor model may word the nudge itself with the household's memories; each
figure it writes must come from the nudge's facts or a memory (grounding.py), else the line goes.
"""

import json
import re
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal
from uuid import UUID

from openai import OpenAI
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from finboy.core.clock import IST
from finboy.core.config import Settings
from finboy.db.models.advisor import NUDGE_KINDS
from finboy.services.advisor import grounding, memory, prompt
from finboy.services.advisor.client import client_for
from finboy.services.advisor.tools import Toolbox, _first_of_month
from finboy.services.assistant.language import money
from finboy.services.money.budgets import BudgetStatus, MonthPlan
from finboy.services.money.engine import CommitmentView, PeriodSpec, TransactionView
from finboy.services.money.insights import RegularPayment, payee_group
from finboy.services.whatsapp import english, hindi, malayalam

Kind = Literal[
    "weekly_recap",
    "due_soon",
    "budget_over",
    "unusual_payment",
    "income_in",
    "budget_near",
    "goal_progress",
    "new_regular",
]
Tone = Literal["warning", "good", "info"]
WORDS = {"en": english, "hi": hindi, "ml": malayalam}
# Most important first: one nudge a day goes out on WhatsApp, and Home shows the first few.
ORDER = {kind: index for index, kind in enumerate(NUDGE_KINDS)}
EMOJI = {
    "weekly_recap": "📒",
    "due_soon": "📌",
    "budget_over": "🔴",
    "unusual_payment": "⚠️",
    "income_in": "💰",
    "budget_near": "🟡",
    "goal_progress": "🎯",
    "new_regular": "🔁",
}
RECENT = timedelta(days=3)  # how long a payment or an income stays news
DUE_AHEAD = timedelta(days=2)
WEEK_AHEAD = timedelta(days=7)
GOAL_FROM_DAY = 20
UNUSUAL_TIMES = 3
UNUSUAL_FLOOR = 100_000  # ₹1,000: a smaller payment is never "unusual"
UNUSUAL_CHECKED = 8  # the largest recent payments compared with their usual amount
PAYEE_HISTORY, PAYEE_DAYS = 3, 180  # earlier payments to the payee for a usual amount
CATEGORY_HISTORY, CATEGORY_DAYS = 5, 90  # else earlier payments in the category
INCOME_FLOOR = 100_000  # ₹1,000
INCOME_FIRST = 500_000  # ₹5,000, when last month shows no income
INCOME_KINDS = frozenset({"salary", "income_other"})
INCOME_CATEGORIES = frozenset({"salary", "wages", "farm_sales", "govt_benefit", "other_income"})
REGULAR_FRESH = timedelta(days=7)
NAME = 60  # characters of a payee or due name in a line
WEB_ITEMS = 3
MAX_NUDGE = 600  # a WhatsApp nudge, well inside an interactive body's 1,024
NATIVE = {"hi": re.compile(r"[ऀ-ॿ]"), "ml": re.compile(r"[ഀ-ൿ]")}


@dataclass(frozen=True)
class BudgetDetail:
    status: BudgetStatus
    days_left: int  # in the month, today included


@dataclass(frozen=True)
class GoalDetail:
    goal_minor: int
    kept_minor: int
    days_left: int


@dataclass(frozen=True)
class DueDetail:
    due: CommitmentView
    days: int  # 0 today, 1 tomorrow, 2 the day after


@dataclass(frozen=True)
class IncomeDetail:
    record: TransactionView
    goal_minor: int | None


@dataclass(frozen=True)
class UnusualDetail:
    record: TransactionView
    usual_minor: int
    basis: Literal["payee", "category"]


@dataclass(frozen=True)
class RegularDetail:
    payment: RegularPayment
    monthly_minor: int  # every regular payment together


@dataclass(frozen=True)
class RecapDetail:
    start: date
    end: date
    income_minor: int
    outflow_minor: int
    top: tuple[tuple[str, int], ...]
    ahead: tuple[CommitmentView, ...]
    overdue_minor: int
    waiting: int


Detail = (
    BudgetDetail
    | GoalDetail
    | DueDetail
    | IncomeDetail
    | UnusualDetail
    | RegularDetail
    | RecapDetail
)


@dataclass(frozen=True)
class Nudge:
    kind: Kind
    # Unique for its kind and period: "2026-11:food_dining", a record's id, a week, a payee.
    key: str
    tone: Tone
    detail: Detail


class WebItem(BaseModel):
    """One "For you" item on Home: code-written English with a place to look and a question."""

    kind: Kind
    tone: Tone
    title: str
    text: str
    href: str
    ask: str


class NudgeReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


@dataclass(frozen=True)
class Worded:
    text: str
    by: Literal["advisor", "fallback"]


def _day(record: TransactionView) -> date:
    return record.occurred_at.astimezone(IST).date()


def _name(value: str | None) -> str:
    """A name as a template parameter may hold it: one line, without runs of spaces."""
    return " ".join((value or "").split())[:NAME] or "—"


def _days_left(plan: MonthPlan, today: date) -> int:
    return max((plan.end - today).days + 1, 1)


def _budgets(plan: MonthPlan, today: date) -> list[Nudge]:
    found: list[Nudge] = []
    for status in plan.budgets:
        if status.level == "ok":
            continue
        kind: Kind = "budget_over" if status.level == "over" else "budget_near"
        detail = BudgetDetail(status, _days_left(plan, today))
        found.append(Nudge(kind, f"{today:%Y-%m}:{status.category}", "warning", detail))
    return found


def _goal(plan: MonthPlan, today: date) -> Nudge | None:
    """From the 20th, how the month's savings goal stands (only once income is recorded)."""
    if not plan.goal_minor or today.day < GOAL_FROM_DAY or plan.income_minor <= 0:
        return None
    kept = max(plan.saved_minor, 0)
    detail = GoalDetail(plan.goal_minor, kept, _days_left(plan, today))
    tone: Tone = "good" if kept >= plan.goal_minor else "warning"
    return Nudge("goal_progress", f"{today:%Y-%m}", tone, detail)


def _dues(box: Toolbox, today: date) -> list[Nudge]:
    rows = box.dues(PeriodSpec(kind="range", start_date=today, end_date=today + DUE_AHEAD))
    return [
        Nudge("due_soon", str(row.id), "warning", DueDetail(row, (row.due_date - today).days))
        for row in rows
        if row.status == "upcoming" and row.due_date >= today
    ]


def _income(recent: list[TransactionView], last_month_minor: int, goal: int | None) -> Nudge | None:
    """The month's salary, wages or crop money: one income at least half of last month's."""
    floor = max(INCOME_FLOOR, last_month_minor // 2) if last_month_minor > 0 else INCOME_FIRST
    rows = [
        row
        for row in recent
        if row.direction == "in"
        and row.kind in INCOME_KINDS
        and row.category in INCOME_CATEGORIES
        and row.amount_minor >= floor
    ]
    if not rows:
        return None
    row = max(rows, key=lambda item: (item.amount_minor, item.occurred_at))
    return Nudge("income_in", f"{_day(row):%Y-%m}", "good", IncomeDetail(row, goal))


def _usual(
    box: Toolbox, row: TransactionView, today: date
) -> tuple[int, Literal["payee", "category"]] | None:
    """The usual amount: the payee's median when paid three times before, else the category's."""
    name = (row.merchant or "").strip()
    if name and len(name) <= 160:
        group = payee_group(name)
        period = PeriodSpec(
            kind="range", start_date=today - timedelta(days=PAYEE_DAYS), end_date=today
        )
        earlier = [
            item.amount_minor
            for item in box.find_transactions(period, None, name)
            if item.id != row.id and item.direction == "out" and payee_group(item.merchant) == group
        ]
        if len(earlier) >= PAYEE_HISTORY:
            return int(statistics.median(earlier)), "payee"
    period = PeriodSpec(
        kind="range", start_date=today - timedelta(days=CATEGORY_DAYS), end_date=today
    )
    earlier = [
        item.amount_minor
        for item in box.find_transactions(period, row.category, None)
        if item.id != row.id and item.direction == "out" and item.kind != "transfer"
    ]
    if len(earlier) >= CATEGORY_HISTORY:
        return int(statistics.median(earlier)), "category"
    return None


def _unusual(box: Toolbox, recent: list[TransactionView], today: date) -> list[Nudge]:
    candidates = sorted(
        (
            row
            for row in recent
            if row.direction == "out"
            and row.kind != "transfer"
            and row.category not in {"investments", "transfer"}
            and row.amount_minor >= UNUSUAL_FLOOR
        ),
        key=lambda row: (-row.amount_minor, row.occurred_at),
    )[:UNUSUAL_CHECKED]
    found: list[Nudge] = []
    for row in candidates:
        usual = _usual(box, row, today)
        if usual is not None and usual[0] > 0 and row.amount_minor > UNUSUAL_TIMES * usual[0]:
            detail = UnusualDetail(row, usual[0], usual[1])
            found.append(Nudge("unusual_payment", str(row.id), "warning", detail))
    return found


def _regular(box: Toolbox, today: date) -> list[Nudge]:
    """Payees that became regular since last month ended, paid again in the last week."""
    current = box.insights(
        PeriodSpec(kind="range", start_date=_first_of_month(today, 2), end_date=today)
    )
    if not current.regular:
        return []
    last = _first_of_month(today, 1)
    before = box.insights(PeriodSpec(kind="month", year=last.year, month=last.month))
    known = {payee_group(item.name) for item in before.regular}
    return [
        Nudge(
            "new_regular",
            payee_group(item.name),
            "info",
            RegularDetail(item, current.regular_monthly_minor),
        )
        for item in current.regular
        if payee_group(item.name) not in known and item.last_paid >= today - REGULAR_FRESH
    ]


def _recap(box: Toolbox, today: date) -> Nudge | None:
    """On Sundays, the week from Monday: money in and out, where it went, dues ahead."""
    if today.weekday() != 6:
        return None
    monday = today - timedelta(days=6)
    summary = box.money_summary(PeriodSpec(kind="range", start_date=monday, end_date=today))
    ahead = box.dues(PeriodSpec(kind="range", start_date=today, end_date=today + WEEK_AHEAD))
    if not (summary.tracked_income_minor or summary.confirmed_outflows_minor or ahead):
        return None
    top = tuple(
        (item.category, item.amount_minor)
        for item in sorted(summary.categories, key=lambda item: -item.amount_minor)
        if item.amount_minor > 0 and item.category != "investments"
    )[:3]
    year, week, _ = today.isocalendar()
    detail = RecapDetail(
        start=monday,
        end=today,
        income_minor=summary.tracked_income_minor,
        outflow_minor=summary.confirmed_outflows_minor,
        top=top,
        ahead=tuple(ahead[:3]),
        overdue_minor=summary.overdue_commitments_minor,
        waiting=summary.pending_review_count,
    )
    return Nudge("weekly_recap", f"{year}-W{week:02}", "info", detail)


def detect(box: Toolbox, today: date) -> list[Nudge]:
    """Every nudge the household's money calls for today, most important first."""
    plan = box.month_plan(PeriodSpec())
    recent = box.find_transactions(
        PeriodSpec(kind="range", start_date=today - RECENT, end_date=today), None, None
    )
    last = _first_of_month(today, 1)
    last_month = box.money_summary(PeriodSpec(kind="month", year=last.year, month=last.month))
    found: list[Nudge] = [
        *(nudge for nudge in (_recap(box, today),) if nudge is not None),
        *_dues(box, today),
        *_budgets(plan, today),
        *_unusual(box, recent, today),
        *(
            nudge
            for nudge in (
                _income(recent, last_month.tracked_income_minor, plan.goal_minor),
                _goal(plan, today),
            )
            if nudge is not None
        ),
        *_regular(box, today),
    ]
    return sorted(found, key=lambda nudge: ORDER[nudge.kind])


def line(nudge: Nudge, language: str) -> str:
    """The nudge in a line from the engine's figures, in English, Hindi or Malayalam."""
    words = WORDS.get(language, english)
    detail = nudge.detail
    if isinstance(detail, BudgetDetail):
        status = detail.status
        return words.COACH[nudge.kind].format(
            name=words.label(status.category),
            spent=money(max(status.spent_minor, 0)),
            limit=money(status.limit_minor),
            left=money(max(status.limit_minor - status.spent_minor, 0)),
            over=money(max(status.spent_minor - status.limit_minor, 0)),
            days=words.days(detail.days_left),
        )
    if isinstance(detail, GoalDetail):
        reached = detail.kept_minor >= detail.goal_minor
        return words.COACH["goal_reached" if reached else "goal_behind"].format(
            goal=money(detail.goal_minor),
            kept=money(detail.kept_minor),
            still=money(max(detail.goal_minor - detail.kept_minor, 0)),
            days=words.days(detail.days_left),
        )
    if isinstance(detail, DueDetail):
        when = words.COACH_WHEN.get(detail.days) or words.COACH_ON_DATE.format(
            date=words.date_label(detail.due.due_date)
        )
        return words.COACH["due_soon"].format(
            name=_name(detail.due.label), amount=money(detail.due.amount_minor), when=when
        )
    if isinstance(detail, IncomeDetail):
        return words.COACH["income_goal" if detail.goal_minor else "income_no_goal"].format(
            amount=money(detail.record.amount_minor),
            name=_name(detail.record.merchant),
            goal=money(detail.goal_minor) if detail.goal_minor else "",
        )
    if isinstance(detail, UnusualDetail):
        return words.COACH["unusual_payment"].format(
            name=_name(detail.record.merchant),
            amount=money(detail.record.amount_minor),
            date=words.date_label(_day(detail.record)),
            usual=money(detail.usual_minor),
        )
    if isinstance(detail, RegularDetail):
        payment = detail.payment
        return words.COACH["new_regular"].format(
            name=_name(payment.name),
            usual=money(payment.usual_minor),
            next=words.date_label(payment.next_expected),
            total=money(detail.monthly_minor),
        )
    most = (
        words.COACH_MOST.format(
            top=", ".join(f"{words.label(category)} {money(a)}" for category, a in detail.top)
        )
        if detail.top
        else ""
    )
    first = detail.ahead[0] if detail.ahead else None
    ahead = (
        words.COACH_AHEAD.format(
            amount=money(first.amount_minor),
            name=_name(first.label),
            date=words.date_label(first.due_date),
        )
        if first
        else ""
    )
    return words.COACH["weekly_recap"].format(
        income=money(detail.income_minor),
        outflow=money(detail.outflow_minor),
        most=most,
        ahead=ahead,
    )


def message(nudge: Nudge, language: str) -> str:
    """The WhatsApp message when the advisor does not word it: the line with its picture cue,
    or the week the way "this week" shows it."""
    detail = nudge.detail
    if isinstance(detail, RecapDetail):
        words = WORDS.get(language, english)
        text, _ = words.week(
            income=detail.income_minor,
            outflow=detail.outflow_minor,
            top=list(detail.top),
            dues=[(row.amount_minor, row.label, row.due_date) for row in detail.ahead],
            overdue=detail.overdue_minor,
            waiting=detail.waiting,
        )
        return text
    return f"{EMOJI[nudge.kind]} {line(nudge, language)}"


def facts(nudge: Nudge) -> dict[str, Any]:
    """What the model may say, from the engine's figures: rupees as text, dates in ISO."""
    detail = nudge.detail
    found: dict[str, Any] = {"nudge": nudge.kind}
    if isinstance(detail, BudgetDetail):
        status = detail.status
        found |= {
            "what": "A monthly budget is over its limit"
            if status.level == "over"
            else "A monthly budget is close to its limit (80% or more spent)",
            "budget": english.label(status.category),
            "limit": money(status.limit_minor),
            "spent_this_month": money(max(status.spent_minor, 0)),
            "days_left_in_month": detail.days_left,
        }
        if status.level == "over":
            found["over_by"] = money(status.spent_minor - status.limit_minor)
        else:
            found["left"] = money(max(status.limit_minor - status.spent_minor, 0))
    elif isinstance(detail, GoalDetail):
        found |= {
            "what": "How this month's savings goal stands",
            "monthly_savings_goal": money(detail.goal_minor),
            "kept_this_month": money(detail.kept_minor),
            "still_to_keep": money(max(detail.goal_minor - detail.kept_minor, 0)),
            "goal_reached": detail.kept_minor >= detail.goal_minor,
            "days_left_in_month": detail.days_left,
        }
    elif isinstance(detail, DueDetail):
        found |= {
            "what": "A due is coming up and is not marked paid",
            "due": _name(detail.due.label),
            "amount": money(detail.due.amount_minor),
            "due_date": detail.due.due_date.isoformat(),
            "days_until_due": detail.days,
        }
    elif isinstance(detail, IncomeDetail):
        found |= {
            "what": "Their salary, wages or crop money came in",
            "from": _name(detail.record.merchant),
            "amount": money(detail.record.amount_minor),
            "date": _day(detail.record).isoformat(),
            "monthly_savings_goal": money(detail.goal_minor) if detail.goal_minor else None,
        }
    elif isinstance(detail, UnusualDetail):
        found |= {
            "what": "A payment more than three times the usual amount",
            "to": _name(detail.record.merchant),
            "category": english.label(detail.record.category),
            "amount": money(detail.record.amount_minor),
            "date": _day(detail.record).isoformat(),
            "usual_amount": money(detail.usual_minor),
            "usual_for": "this payee" if detail.basis == "payee" else "this category",
        }
    elif isinstance(detail, RegularDetail):
        payment = detail.payment
        found |= {
            "what": "A payment that now looks regular (monthly)",
            "to": _name(payment.name),
            "usual_amount": money(payment.usual_minor),
            "months_seen_of_last_6": payment.months,
            "next_expected_around": payment.next_expected.isoformat(),
            "all_regular_payments_per_month": money(detail.monthly_minor),
        }
    else:
        found |= {
            "what": "Their week, Monday to today",
            "period": f"{detail.start.isoformat()} to {detail.end.isoformat()}",
            "money_in": money(detail.income_minor),
            "money_out": money(detail.outflow_minor),
            "most_spent_on": [
                {"category": english.label(category), "amount": money(amount)}
                for category, amount in detail.top
            ],
            "dues_next_7_days": [
                {
                    "due": _name(row.label),
                    "amount": money(row.amount_minor),
                    "date": str(row.due_date),
                }
                for row in detail.ahead
            ],
            "overdue_total": money(detail.overdue_minor) if detail.overdue_minor else None,
            "entries_waiting_for_review": detail.waiting,
        }
    return found


TITLES: dict[str, str] = {
    "weekly_recap": "Your week",
    "due_soon": "Due soon",
    "budget_over": "Over budget",
    "unusual_payment": "Bigger than usual",
    "income_in": "Money in",
    "budget_near": "Budget running low",
    "goal_progress": "Savings goal",
    "new_regular": "New regular payment",
}


def _ask(nudge: Nudge) -> str:
    """A question Ask can take further, in the household's own words."""
    detail = nudge.detail
    if isinstance(detail, BudgetDetail):
        if detail.status.category == "total":
            return "How can I stay within my budget this month?"
        return f"How can I spend less on {english.label(detail.status.category).lower()}?"
    if isinstance(detail, UnusualDetail):
        return f"Show my payments to {_name(detail.record.merchant)}"
    return {
        "weekly_recap": "How did this week compare with last week?",
        "due_soon": "What do I have to pay this week?",
        "income_in": "Help me plan this month's money",
        "goal_progress": "How can I reach my savings goal this month?",
        "new_regular": "What are my regular payments?",
    }[nudge.kind]


def _href(nudge: Nudge) -> str:
    detail = nudge.detail
    if isinstance(detail, IncomeDetail | UnusualDetail):
        return f"/transactions?selected={detail.record.id}"
    if isinstance(detail, BudgetDetail | GoalDetail):
        return "#budgets-title"
    if isinstance(detail, DueDetail):
        return "#obligations"
    if isinstance(detail, RegularDetail):
        return "/reports#regular-title"
    return "/reports"


def web_items(found: list[Nudge]) -> list[WebItem]:
    """Home's "For you": the most important few, written by code in English."""
    return [
        WebItem(
            kind=nudge.kind,
            tone=nudge.tone,
            title=TITLES[nudge.kind],
            text=line(nudge, "en"),
            href=_href(nudge),
            ask=_ask(nudge),
        )
        for nudge in found[:WEB_ITEMS]
    ]


def _in_script(text: str, language: str) -> bool:
    """A Hindi or Malayalam nudge must be in its own script, like the reply style asks."""
    native = NATIVE.get(language)
    return native is None or bool(native.search(text))


def compose(
    session: Session,
    settings: Settings,
    user_id: UUID,
    nudge: Nudge,
    language: str,
    today: date,
    *,
    client: OpenAI | None = None,
) -> Worded:
    """The advisor's wording of a WhatsApp nudge, made personal with the household's memories.

    The model gets only the nudge's facts, its code-written version and the memories, and no
    tools. A figure it writes that is in none of them, a reply too long or in the wrong script,
    or any failure sends the code-written message instead. No transaction stays open over the
    network call.
    """
    fallback = Worded(message(nudge, language), "fallback")
    try:
        model = client or client_for(settings)
        remembered = (
            memory.recall(session, user_id, line(nudge, "en"), settings)
            if memory.enabled(session, user_id)
            else []
        )
    except Exception:  # no key, or memories out of reach: the nudge still goes, as written
        session.rollback()
        return fallback
    listing = memory.prompt_block(remembered)
    session.rollback()
    found = facts(nudge)
    known = grounding.allowed(
        [json.dumps(found, ensure_ascii=False), fallback.text, today.isoformat()]
        + list(listing.texts.values())
    )
    items: list[dict[str, str]] = [
        {"role": "system", "content": prompt.COACH},
        {
            "role": "developer",
            "content": prompt.nudge_context(
                today=today,
                language=language,
                memories=listing.block if remembered else "(none)",
                facts=found,
                plain=fallback.text,
            ),
        },
        {"role": "user", "content": "Write the message."},
    ]
    try:
        response = model.responses.parse(
            model=settings.advisor_model,
            input=items,
            text_format=NudgeReply,
            reasoning={"effort": settings.advisor_reasoning_effort},
            store=False,
            max_output_tokens=1500,
            prompt_cache_key="finboy-coach-v1",
            timeout=settings.advisor_timeout_seconds,
        )
    except Exception:
        return fallback
    reply = response.output_parsed
    text = reply.text.strip() if isinstance(reply, NudgeReply) else ""
    if (
        not text
        or len(text) > MAX_NUDGE
        or grounding.unchecked([text], known)
        or not _in_script(text, language)
    ):
        return fallback
    return Worded(text, "advisor")
