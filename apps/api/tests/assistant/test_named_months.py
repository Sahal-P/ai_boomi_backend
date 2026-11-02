"""Questions that name a month ("How much did I spend in September?"); no network or database."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from finboy.core.config import Settings
from finboy.services.assistant import intent
from finboy.services.assistant.intent import (
    AssistantReply,
    ModelPeriod,
    ModelReading,
    amounts_in_question,
    normalized,
    parse_intent,
    resolve_period,
    rule_intent,
)
from finboy.services.money.engine import PeriodSpec
from pydantic import SecretStr

QUESTION = "how much did i spend on september ?"
SEPTEMBER = PeriodSpec(kind="month", year=2026, month=9)
REPLY = AssistantReply(
    display_text="Here is your spending for that month.",
    speech_text="Here is your spending for that month.",
)


@pytest.fixture(autouse=True)
def today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(intent, "today_ist", lambda: date(2026, 11, 2))


@pytest.fixture
def configured(settings: Settings) -> Settings:
    return settings.model_copy(
        update={"openai_api_key": SecretStr("synthetic"), "openai_assistant_model": "configured"}
    )


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    fake = MagicMock()
    monkeypatch.setattr(intent, "OpenAI", fake)
    return fake.return_value.__enter__.return_value.responses.parse


@pytest.mark.parametrize(
    "question,period",
    [
        (QUESTION, SEPTEMBER),
        ("How much did I spend in September?", SEPTEMBER),
        ("sept spending", SEPTEMBER),
        ("How much did I spend in December?", PeriodSpec(kind="month", year=2025, month=12)),
        ("Spending in November", PeriodSpec()),
        ("Spending for 2026-11", PeriodSpec()),
        ("Food spending in September 2025", PeriodSpec(kind="month", year=2025, month=9)),
        ("How much did I spend in May?", PeriodSpec(kind="month", year=2026, month=5)),
        ("सितंबर में कितना खर्च हुआ?", SEPTEMBER),
        ("സെപ്റ്റംബറിൽ എത്ര ചെലവായി?", SEPTEMBER),
        ("May I know my spending this month?", PeriodSpec()),
    ],
)
def test_a_named_month_is_its_latest_occurrence(question, period):
    assert resolve_period(normalized(question)) == (period, False)


@pytest.mark.parametrize(
    "question",
    [
        "How much will I spend next September?",
        "How much did I spend last September?",
        "पिछले सितंबर में कितना खर्च हुआ?",
        "How much did I spend on 20 September?",
        "Spending on Sep 20th",
        "Spending in September and October",
        "Spending in September last month",
    ],
)
def test_ambiguous_or_dated_months_ask_for_the_period(question):
    assert resolve_period(normalized(question))[1] is True


def test_a_named_month_is_never_a_payee():
    parsed = rule_intent(QUESTION)
    assert parsed.intent == "spending_query" and parsed.merchant is None
    assert parsed.period == SEPTEMBER
    shop = rule_intent("How much did I spend at Ramesh Stores in September?")
    assert shop.intent == "merchant_lookup" and shop.merchant == "ramesh stores"
    assert shop.period == SEPTEMBER


def test_a_year_after_a_month_is_not_an_amount():
    assert amounts_in_question("Spending in September 2025") == set()
    assert amounts_in_question("Can I afford 2025 a month from September?") == {202500}


def test_a_month_the_model_reads_without_its_year_is_answered(configured, provider):
    provider.return_value.output_parsed = ModelReading(
        intent="spending_query", period=ModelPeriod(kind="month", month=9), reply=REPLY
    )
    parsed = parse_intent(QUESTION, configured)
    assert parsed.intent == "spending_query" and parsed.period == SEPTEMBER
    assert type(parsed.period) is PeriodSpec and parsed.reply == REPLY
    assert provider.call_args.kwargs["text_format"] is ModelReading


def test_a_spending_question_naming_a_payee_totals_that_payee(configured, provider):
    provider.return_value.output_parsed = ModelReading(
        intent="spending_query",
        merchant="swiggy",
        period=ModelPeriod(kind="month", month=10),
        reply=REPLY,
    )
    parsed = parse_intent("How much did I spend at Swiggy in October?", configured)
    assert parsed.intent == "merchant_lookup" and parsed.merchant == "swiggy"
    assert parsed.period == PeriodSpec(kind="month", year=2026, month=10)


def test_the_current_month_reads_alike_however_it_is_named(configured, provider):
    provider.return_value.output_parsed = ModelReading(
        intent="spending_query", period=ModelPeriod(kind="month", year=2026, month=11), reply=REPLY
    )
    assert parse_intent("How much did I spend this month?", configured).period == PeriodSpec()


@pytest.mark.parametrize(
    "period",
    [
        ModelPeriod(kind="month"),
        ModelPeriod(kind="month", year=2026, month=13),
        ModelPeriod(kind="range", start_date=date(2026, 9, 1)),
        ModelPeriod(kind="month", year=2026, month=8),
    ],
)
def test_an_unusable_model_period_asks_instead_of_failing(configured, provider, period):
    provider.return_value.output_parsed = ModelReading(
        intent="spending_query", period=period, reply=REPLY
    )
    parsed = parse_intent(QUESTION, configured)
    assert parsed.intent == "clarification" and parsed.clarification_reason == "period"
