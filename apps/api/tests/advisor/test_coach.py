"""The coach's detectors, lines and wording (docs/advisor-round/contract.md, phase 3).

A fake engine toolbox with the figures each test sets; the scripted model stands in for OpenAI.
"""

import json
from datetime import date, datetime, time, timedelta
from uuid import uuid4

import pytest
from finboy.core.clock import IST
from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.advisor import NUDGE_KINDS
from finboy.services.advisor import coach, memory
from finboy.services.money import budgets, engine, insights
from finboy.services.money.engine import (
    CategoryTotal,
    CommitmentView,
    MoneySummary,
    PeriodSpec,
    TransactionView,
)

from .support import ScriptedModel

TODAY = date(2026, 11, 18)  # a Wednesday: 13 days left in November, today included
SUNDAY = date(2026, 11, 22)


def record(
    name: str,
    amount: int,
    *,
    day: date = TODAY,
    out: bool = True,
    category: str = "food_dining",
    kind: str | None = None,
) -> TransactionView:
    return TransactionView(
        id=uuid4(),
        direction="out" if out else "in",
        kind=kind or ("purchase" if out else "salary"),
        amount_minor=amount,
        merchant=name,
        category=category,
        occurred_at=datetime.combine(day, time(12), IST),
        status="confirmed",
        confidence=0.9,
    )


def due(label: str, amount: int, day: date) -> CommitmentView:
    return CommitmentView(
        id=uuid4(),
        kind="bill",
        label=label,
        amount_minor=amount,
        due_date=day,
        status="upcoming",
        confidence=0.9,
    )


def regular(name: str, usual: int, last_paid: date) -> insights.RegularPayment:
    return insights.RegularPayment(
        name=name,
        usual_minor=usual,
        months=3,
        last_paid=last_paid,
        next_expected=insights.next_month(last_paid),
        category="subscriptions",
    )


class CoachBox:
    """The engine reads the detectors use, with the figures each test sets."""

    def __init__(
        self,
        today: date = TODAY,
        *,
        budget: list[budgets.BudgetStatus] | None = None,
        goal: int | None = None,
        income: int = 0,
        saved: int = 0,
        dues: list[CommitmentView] | None = None,
        records: list[TransactionView] | None = None,
        regular_now: list[insights.RegularPayment] | None = None,
        regular_before: list[insights.RegularPayment] | None = None,
        last_month_income: int = 0,
        week: tuple[int, int, list[tuple[str, int]]] = (0, 0, []),
    ) -> None:
        self.today, self.budget, self.goal = today, budget or [], goal
        self.income, self.saved = income, saved
        self.due_rows, self.records = dues or [], records or []
        self.regular_now, self.regular_before = regular_now or [], regular_before or []
        self.last_month_income, self.week = last_month_income, week
        self.reads: list[str] = []

    def month_plan(self, period: PeriodSpec) -> budgets.MonthPlan:
        self.reads.append("month_plan")
        start, end = engine.period_dates(period, self.today)
        return budgets.MonthPlan(
            start=start,
            end=end,
            as_of=self.today,
            income_minor=self.income,
            spent_minor=0,
            saved_minor=self.saved,
            goal_minor=self.goal,
            budgets=list(self.budget),
            top=[],
            waiting=0,
        )

    def money_summary(self, period: PeriodSpec) -> MoneySummary:
        self.reads.append("money_summary")
        start, end = engine.period_dates(period, self.today)
        income, outflow, top = (
            (self.last_month_income, 0, []) if period.kind == "month" else self.week
        )
        return MoneySummary(
            period_start=start,
            period_end=end,
            as_of=self.today,
            tracked_income_minor=income,
            confirmed_outflows_minor=outflow,
            upcoming_commitments_minor=0,
            estimated_unallocated_minor=0,
            pending_review_count=0,
            pending_review_minor=0,
            income_transaction_count=0,
            outflow_transaction_count=0,
            commitment_count=0,
            categories=[
                CategoryTotal(category=category, amount_minor=amount, transaction_count=1)
                for category, amount in top
            ],
            evidence_transaction_ids=[],
        )

    def dues(self, period: PeriodSpec) -> list[CommitmentView]:
        self.reads.append("dues")
        start, end = engine.period_dates(period, self.today)
        return [row for row in self.due_rows if start <= row.due_date <= end]

    def find_transactions(
        self, period: PeriodSpec, category: str | None, merchant: str | None
    ) -> list[TransactionView]:
        self.reads.append("find_transactions")
        start, end = engine.period_dates(period, self.today)
        return [
            row
            for row in self.records
            if start <= row.occurred_at.astimezone(IST).date() <= end
            and (category is None or row.category == category)
            and (merchant is None or merchant.casefold() in row.merchant.casefold())
        ]

    def insights(self, period: PeriodSpec) -> insights.Insights:
        self.reads.append("insights")
        start, end = engine.period_dates(period, self.today)
        rows = list(self.regular_now if period.kind == "range" else self.regular_before)
        return insights.Insights(
            period_start=start,
            period_end=end,
            months=3,
            money_out_minor=0,
            money_in_minor=0,
            payment_count=0,
            top_payees=[],
            top_senders=[],
            biggest=[],
            regular=rows,
            regular_monthly_minor=sum(item.usual_minor for item in rows),
            people=[],
            small=insights.SmallPayments(
                threshold_minor=20000,
                count=0,
                amount_minor=0,
                per_month_minor=0,
                count_share=0,
                amount_share=0,
                places=[],
            ),
        )


def every_kind() -> CoachBox:
    """A Sunday after the 20th with something of every kind."""
    payee = [record("Swiggy", 40000, day=SUNDAY - timedelta(days=d)) for d in (10, 20, 30)]
    return CoachBox(
        SUNDAY,
        budget=[
            budgets.BudgetStatus("total", 2000000, 2100000),
            budgets.BudgetStatus("food_dining", 500000, 420000),
        ],
        goal=500000,
        income=3000000,
        saved=200000,
        dues=[due("Electricity bill", 150000, SUNDAY + timedelta(days=1))],
        records=[
            *payee,
            record("Swiggy", 250000, day=SUNDAY),
            record(
                "Acme Pvt Ltd", 3000000, out=False, category="salary", day=SUNDAY - timedelta(1)
            ),
        ],
        regular_now=[regular("Netflix", 64900, SUNDAY - timedelta(days=2))],
        last_month_income=3000000,
        week=(3000000, 842050, [("food_dining", 420000), ("groceries", 310000)]),
    )


def test_a_quiet_month_needs_no_nudge() -> None:
    assert coach.detect(CoachBox(), TODAY) == []


def test_budgets_close_to_or_over_their_limit() -> None:
    box = CoachBox(
        budget=[
            budgets.BudgetStatus("total", 2000000, 2100000),
            budgets.BudgetStatus("food_dining", 500000, 420000),
            budgets.BudgetStatus("transport", 300000, 100000),
        ]
    )
    found = coach.detect(box, TODAY)
    assert [(nudge.kind, nudge.key) for nudge in found] == [
        ("budget_over", "2026-11:total"),
        ("budget_near", "2026-11:food_dining"),
    ]
    assert coach.line(found[0], "en") == (
        "All spending: ₹21,000 spent, ₹1,000 over your ₹20,000 budget, with 13 days to go."
    )
    assert coach.line(found[1], "en") == (
        "Food & dining: ₹4,200 of your ₹5,000 budget spent, ₹800 left with 13 days to go."
    )
    hindi = coach.line(found[1], "hi")
    assert "₹800" in hindi and "13 दिन" in hindi
    assert "₹800" in coach.line(found[1], "ml") and "13 ദിവസം" in coach.line(found[1], "ml")
    assert coach.message(found[0], "en").startswith("🔴 All spending")


def test_the_savings_goal_from_the_twentieth_once_income_is_in() -> None:
    assert coach.detect(CoachBox(goal=500000, income=3000000, saved=200000), TODAY) == []
    late = date(2026, 11, 24)
    [behind] = coach.detect(CoachBox(late, goal=500000, income=3000000, saved=200000), late)
    assert (behind.kind, behind.key, behind.tone) == ("goal_progress", "2026-11", "warning")
    assert coach.line(behind, "en") == (
        "Savings goal: ₹2,000 kept of your ₹5,000 this month, ₹3,000 still to keep with "
        "7 days to go."
    )
    [reached] = coach.detect(CoachBox(late, goal=500000, income=3000000, saved=600000), late)
    assert reached.tone == "good"
    assert coach.line(reached, "en") == (
        "Savings goal: ₹6,000 kept this month, so your ₹5,000 goal is reached."
    )
    assert coach.detect(CoachBox(late, goal=500000, saved=-50000), late) == []


def test_dues_in_the_next_two_days() -> None:
    box = CoachBox(
        dues=[
            due("Electricity bill", 150000, TODAY + timedelta(days=1)),
            due("School fees", 800000, TODAY + timedelta(days=3)),
        ]
    )
    [nudge] = coach.detect(box, TODAY)
    assert nudge.kind == "due_soon" and nudge.key == str(box.due_rows[0].id)
    assert coach.line(nudge, "en") == "Electricity bill: ₹1,500 due tomorrow."
    assert coach.line(nudge, "hi") == "Electricity bill: ₹1,500 कल देना है।"
    assert coach.line(nudge, "ml") == "Electricity bill: ₹1,500 നാളെ അടയ്ക്കണം."


def test_the_months_salary_wages_or_crop_money_coming_in() -> None:
    salary = record("Acme Pvt Ltd", 3000000, out=False, category="salary", day=TODAY - timedelta(1))
    [nudge] = coach.detect(
        CoachBox(records=[salary], last_month_income=3000000, goal=500000), TODAY
    )
    assert (nudge.kind, nudge.key, nudge.tone) == ("income_in", "2026-11", "good")
    assert coach.line(nudge, "en") == (
        "₹30,000 came in from Acme Pvt Ltd. Setting your ₹5,000 savings goal aside today keeps "
        "it safe."
    )
    # A day's wages are not the month's income, so they never bring a message each day.
    wage = record("Contractor", 50000, out=False, category="wages", kind="income_other")
    assert coach.detect(CoachBox(records=[wage], last_month_income=1500000), TODAY) == []
    # With no income last month, ₹5,000 or more counts; without a goal, it suggests one.
    crop = record("Mandi", 600000, out=False, category="farm_sales", kind="income_other")
    [first] = coach.detect(CoachBox(records=[crop]), TODAY)
    assert '"save 5000 a month"' in coach.line(first, "en")
    # Older than three days, a refund, or money between own accounts is not news.
    old = record("Acme", 3000000, out=False, category="salary", day=TODAY - timedelta(4))
    refund = record("Shop", 900000, out=False, category="other_income", kind="refund")
    assert coach.detect(CoachBox(records=[old, refund]), TODAY) == []


def test_a_payment_far_above_the_payees_or_categorys_usual() -> None:
    earlier = [record("Swiggy", 40000, day=TODAY - timedelta(days=d)) for d in (10, 20, 30)]
    big = record("Swiggy", 250000)
    [nudge] = coach.detect(CoachBox(records=[*earlier, big]), TODAY)
    assert (nudge.kind, nudge.key) == ("unusual_payment", str(big.id))
    assert nudge.detail.basis == "payee"  # type: ignore[union-attr]
    assert coach.line(nudge, "en") == (
        "Swiggy: ₹2,500 on 18 November, more than three times the usual ₹400. If that's not "
        "right, fix it in FinBoy."
    )
    # Exactly three times, or under ₹1,000, is not unusual.
    assert coach.detect(CoachBox(records=[*earlier, record("Swiggy", 120000)]), TODAY) == []
    small = [record("Chai", 2000, day=TODAY - timedelta(days=d)) for d in (1, 2, 3)]
    assert coach.detect(CoachBox(records=[*small, record("Chai", 90000)]), TODAY) == []
    # A payee seen fewer than three times is compared with its category.
    shops = [
        record(f"Shop {index}", 50000, category="shopping", day=TODAY - timedelta(days=index + 1))
        for index in range(5)
    ]
    [tv] = coach.detect(
        CoachBox(records=[*shops, record("Croma", 2500000, category="shopping")]), TODAY
    )
    assert tv.detail.basis == "category"  # type: ignore[union-attr]
    # Money moved to savings or between own accounts is never "unusual".
    moved = record("Own account", 2500000, category="transfer", kind="transfer")
    saved = record("RD", 2500000, category="investments", kind="investment")
    assert coach.detect(CoachBox(records=[*shops, moved, saved]), TODAY) == []


def test_a_payment_that_just_became_regular() -> None:
    netflix = regular("Netflix", 64900, TODAY - timedelta(days=2))
    jio = regular("Jio", 29900, TODAY - timedelta(days=5))
    [nudge] = coach.detect(CoachBox(regular_now=[netflix, jio], regular_before=[jio]), TODAY)
    assert (nudge.kind, nudge.key, nudge.tone) == ("new_regular", "netflix", "info")
    assert coach.line(nudge, "en") == (
        "Netflix now looks like a regular payment: about ₹649 a month, next around 16 December. "
        "Your regular payments come to ₹948 a month."
    )
    stale = regular("Gym", 100000, TODAY - timedelta(days=12))
    assert coach.detect(CoachBox(regular_now=[stale]), TODAY) == []


def test_the_sunday_recap() -> None:
    box = CoachBox(
        SUNDAY,
        dues=[due("Rent", 1200000, SUNDAY + timedelta(days=3))],
        week=(3000000, 842050, [("food_dining", 420000), ("groceries", 310000)]),
    )
    [recap] = coach.detect(box, SUNDAY)
    assert (recap.kind, recap.key) == ("weekly_recap", "2026-W47")
    assert coach.line(recap, "en") == (
        "This week: ₹30,000 in, ₹8,420.50 out. Most went on Food & dining ₹4,200, Groceries "
        "₹3,100. Coming up: ₹12,000 for Rent on 25 November."
    )
    assert coach.message(recap, "en").startswith("📒 This week (Monday to today)")
    assert coach.detect(CoachBox(SUNDAY), SUNDAY) == [], "a week with nothing gets no recap"
    weekday = CoachBox(TODAY, week=(3000000, 842050, []))
    assert coach.detect(weekday, TODAY) == [], "only on Sundays"


def test_the_most_important_comes_first() -> None:
    found = coach.detect(every_kind(), SUNDAY)
    assert [nudge.kind for nudge in found] == list(NUDGE_KINDS)


@pytest.mark.parametrize("language", ["en", "hi", "ml"])
def test_every_line_fits_a_template_parameter(language: str) -> None:
    """Meta refuses a parameter with a line break, a tab or more than four spaces in a row."""
    for nudge in coach.detect(every_kind(), SUNDAY):
        text = coach.line(nudge, language)
        assert 1 <= len(text) <= 1024 and "{" not in text
        assert "\n" not in text and "\t" not in text and "     " not in text
        json.dumps(coach.facts(nudge), ensure_ascii=False)


def test_home_shows_the_first_three_in_english() -> None:
    items = coach.web_items(coach.detect(every_kind(), SUNDAY))
    assert [(item.kind, item.title, item.href) for item in items] == [
        ("weekly_recap", "Your week", "/reports"),
        ("due_soon", "Due soon", "#obligations"),
        ("budget_over", "Over budget", "#budgets-title"),
    ]
    assert items[1].text == "Electricity bill: ₹1,500 due tomorrow."
    assert items[2].ask == "How can I stay within my budget this month?"


# The advisor's wording (compose): personal, checked, and never at the cost of the message.


def near() -> coach.Nudge:
    box = CoachBox(budget=[budgets.BudgetStatus("food_dining", 500000, 420000)])
    return coach.detect(box, TODAY)[0]


def test_the_advisor_words_a_nudge_with_the_households_memory(session, settings) -> None:
    memory.remember(
        session, LOCAL_USER_ID, "goal", "Saving ₹40,000 for a bike by March 2027", "web", 300
    )
    session.commit()
    text = (
        "Food & dining is at *₹4,200* of ₹5,000, with ₹800 left. Cooking at home this week keeps "
        "your ₹40,000 bike plan on track."
    )
    model = ScriptedModel(coach.NudgeReply(text=text))
    worded = coach.compose(session, settings, LOCAL_USER_ID, near(), "en", TODAY, client=model)
    assert worded == coach.Worded(text, "advisor")
    call = model.calls[0]
    assert call["store"] is False and call["text_format"] is coach.NudgeReply
    assert "tools" not in call, "a nudge reads only its facts"
    context = call["input"][1]["content"]
    assert "bike" in context and "₹800" in context and "Reply language: en" in context


def test_an_invented_figure_sends_the_plain_message(session, settings) -> None:
    model = ScriptedModel(coach.NudgeReply(text="You can still spend ₹2,000 on food this month."))
    worded = coach.compose(session, settings, LOCAL_USER_ID, near(), "en", TODAY, client=model)
    assert worded == coach.Worded(coach.message(near(), "en"), "fallback")


def test_a_hindi_nudge_must_be_in_devanagari(session, settings) -> None:
    model = ScriptedModel(coach.NudgeReply(text="Khane ka budget lagbhag khatam, ₹800 bache."))
    worded = coach.compose(session, settings, LOCAL_USER_ID, near(), "hi", TODAY, client=model)
    assert worded.by == "fallback" and "₹800" in worded.text and "दिन" in worded.text


def test_a_long_reply_or_any_failure_sends_the_plain_message(session, settings) -> None:
    long = ScriptedModel(coach.NudgeReply(text="₹800 left. " * 80))
    assert coach.compose(session, settings, LOCAL_USER_ID, near(), "en", TODAY, client=long).by == (
        "fallback"
    )
    broken = ScriptedModel(TimeoutError())
    assert coach.compose(
        session, settings, LOCAL_USER_ID, near(), "en", TODAY, client=broken
    ).by == ("fallback")
    keyless = settings.model_copy(update={"openai_api_key": None})
    assert coach.compose(session, keyless, LOCAL_USER_ID, near(), "en", TODAY).by == "fallback"


def test_with_memory_off_no_memory_is_used(session, settings) -> None:
    memory.remember(session, LOCAL_USER_ID, "goal", "Saving for a bike", "web", 300)
    memory.set_enabled(session, LOCAL_USER_ID, False)
    session.commit()
    model = ScriptedModel(coach.NudgeReply(text="₹800 left for food this month."))
    coach.compose(session, settings, LOCAL_USER_ID, near(), "en", TODAY, client=model)
    context = model.calls[0]["input"][1]["content"]
    assert "bike" not in context and "(none)" in context


def test_memories_out_of_reach_still_send_the_plain_message(session, settings, monkeypatch) -> None:
    def unavailable(*_args, **_kwargs):
        raise RuntimeError("synthetic outage")

    monkeypatch.setattr(memory, "recall", unavailable)
    model = ScriptedModel(coach.NudgeReply(text="₹800 left."))
    worded = coach.compose(session, settings, LOCAL_USER_ID, near(), "en", TODAY, client=model)
    assert worded.by == "fallback" and model.calls == []
