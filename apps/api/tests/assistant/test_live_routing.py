"""Provider-boundary regressions; no credentials, network, or database required."""

import threading
from unittest.mock import MagicMock

import httpx
import pytest
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.core.errors import ProviderUnavailable
from finboy.services.assistant import intent
from finboy.services.assistant.intent import AssistantReply, ParsedIntent, parse_intent
from finboy.services.assistant.service import answer_question
from finboy.services.triage.service import Sorted
from openai import APIConnectionError
from pydantic import SecretStr, ValidationError
from triage.support import choice, held, late, noul, triaged


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
    "question,parsed",
    [
        (
            "I need to buy gt 650 next month, what is your opinion?",
            ParsedIntent(intent="purchase_planning"),
        ),
        (
            "Food spending this month?",
            ParsedIntent(intent="spending_query", category="food_dining"),
        ),
    ],
)
def test_rules_do_not_bypass_configured_ai(question, parsed, configured, provider):
    parsed.reply = AssistantReply(
        display_text="What is the on-road quote, and are you paying cash or financing?",
        speech_text="What is the on-road quote, and are you paying cash or financing?",
    )
    provider.return_value.output_parsed = parsed
    result = parse_intent(question, configured)
    assert result.intent == parsed.intent and result.reply is not None
    provider.assert_called_once()
    request = provider.call_args.kwargs
    assert request["store"] is False and "tools" not in request


def test_purchase_model_number_never_becomes_a_commitment(
    configured, provider, session, monkeypatch
):
    provider.return_value.output_parsed = ParsedIntent(
        intent="purchase_planning",
        amount_minor=65000,
        reply=AssistantReply(
            display_text="Is this the Continental GT? Share the on-road quote and payment plan.",
            speech_text="Is this the Continental GT? Share the on-road quote and payment plan.",
        ),
    )
    engine = MagicMock()
    monkeypatch.setattr("finboy.services.assistant.service.engine", engine)
    answer = answer_question(
        session,
        user_id=LOCAL_USER_ID,
        text="I need to buy gt 650 next month, what is your opinion?",
        display_style="en",
        settings=configured,
    )
    assert answer.intent == "purchase_planning" and answer.policy == "clarify"
    assert "on-road quote" in answer.display_text
    assert "Which period" not in answer.display_text
    assert answer.facts == [] and answer.simulation is None and answer.resolved_period is None
    engine.money_summary.assert_not_called()
    engine.simulate_monthly_commitment.assert_not_called()


@pytest.mark.parametrize("value", ["It costs ₹650", "The price is 650", "Save १००", "Try 20%"])
def test_provider_prose_cannot_introduce_figures(value):
    with pytest.raises(ValidationError):
        AssistantReply(display_text=value, speech_text="Please share the actual quote.")


def test_provider_failure_is_explicit_instead_of_a_canned_fallback(configured, provider):
    provider.side_effect = APIConnectionError(
        message="sensitive provider details",
        request=httpx.Request("POST", "https://example.invalid"),
    )
    with pytest.raises(ProviderUnavailable, match="^assistant_unavailable$"):
        parse_intent("Food spending this month?", configured)


@pytest.mark.parametrize("output", [None, ParsedIntent(intent="spending_query")])
def test_refused_or_incomplete_provider_output_is_explicit(configured, provider, output):
    provider.return_value.output_parsed = output
    with pytest.raises(ProviderUnavailable, match="^assistant_unavailable$"):
        parse_intent("Food spending this month?", configured)


def test_missing_production_configuration_does_not_look_like_ai(settings):
    settings.environment = "production"
    with pytest.raises(ProviderUnavailable, match="^configuration_missing$"):
        parse_intent("Food spending this month?", settings)


@pytest.mark.parametrize("language", ["hi", "ml"])
def test_purchase_speech_must_use_requested_native_script(configured, provider, language):
    provider.return_value.output_parsed = ParsedIntent(
        intent="purchase_planning",
        reply=AssistantReply(display_text="Share the quote.", speech_text="Share the quote."),
    )
    with pytest.raises(ProviderUnavailable, match="^assistant_unavailable$"):
        parse_intent("Buy a motorcycle next month?", configured, speech_language=language)


def test_ai_cannot_override_explicit_security_pick_boundary(configured, provider):
    provider.return_value.output_parsed = ParsedIntent(intent="purchase_planning")
    assert parse_intent("Which stock should I buy?", configured).intent == "regulated_advice"


@pytest.mark.anyio
async def test_http_provider_errors_are_redacted_and_cors_is_preserved(client, settings, provider):
    settings.openai_api_key = SecretStr("synthetic")
    settings.openai_assistant_model = "configured"
    provider.side_effect = APIConnectionError(
        message="sensitive provider details",
        request=httpx.Request("POST", "https://example.invalid"),
    )
    response = await client.post(
        "/api/v1/assistant/ask",
        json={"text": "Food spending this month?", "display_style": "en"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "assistant_unavailable"
    assert response.json()["error"]["request_id"]
    assert "sensitive" not in response.text
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"


# d1-ultra fast answers (docs/triage-round/contract.md).

MODEL = ParsedIntent(intent="out_of_scope")


def asked(**overrides) -> Sorted:
    """A sure question about all spending this month, unless overridden."""
    answers = {
        "intent": choice("spending"),
        "topic": choice("none"),
        "category": choice("none"),
        "merchant": noul(0.02),
    }
    return Sorted(answers | overrides)


@pytest.mark.parametrize(
    ("question", "answers", "expected"),
    [
        (
            "How much did I spend on food this month?",
            {"category": choice("food_dining")},
            ParsedIntent(intent="spending_query", category="food_dining"),
        ),
        (
            "How much did I spend on food this month?",
            # The rules name food, so d1-ultra need only lean the same way.
            {"category": choice("food_dining", 0.6)},
            ParsedIntent(intent="spending_query", category="food_dining"),
        ),
        ("इस महीने कुल कितना खर्च हुआ?", {}, ParsedIntent(intent="spending_query")),
        (
            "What income was recorded this month?",
            {"intent": choice("income")},
            ParsedIntent(intent="income_query"),
        ),
        (
            "How much is left?",
            {"intent": choice("left_over")},
            ParsedIntent(intent="unallocated_query"),
        ),
        (
            "What bills are coming up?",
            {"intent": choice("bills")},
            ParsedIntent(intent="upcoming_commitments"),
        ),
        (
            "SIP enthanu?",
            {"intent": choice("explain"), "topic": choice("sip")},
            ParsedIntent(intent="education", topic="sip"),
        ),
        (
            "Konsa share lena chahiye?",
            {"intent": choice("investment_pick")},
            ParsedIntent(intent="regulated_advice"),
        ),
        (
            "How much did I spend last week?",
            {},
            ParsedIntent(intent="clarification", clarification_reason="period"),
        ),
    ],
)
def test_sure_common_questions_do_not_wait_for_the_model(
    question, answers, expected, configured, monkeypatch
):
    release = threading.Event()
    monkeypatch.setattr(intent, "_model_intent", held(MODEL, release))
    monkeypatch.setattr(intent.triage, "sort_question", lambda *_args: asked(**answers))
    try:
        assert parse_intent(question, triaged(configured)) == expected
    finally:
        release.set()


@pytest.mark.parametrize(
    ("question", "answers"),
    [
        ("I need to buy gt 650 next month, what is your opinion?", {"intent": choice("purchase")}),
        # Even sorted as spending, a number in the question keeps it off the fast path.
        ("I need to buy gt 650 next month, what is your opinion?", {}),
        (
            "Would a 5000 monthly SIP fit the tracked cash flow?",
            {"intent": choice("afford_monthly")},
        ),
        ("How much did I pay Ramesh this month?", {"merchant": noul(0.96)}),
        ("How much did I spend at Swiggy this month?", {}),  # the rules found a merchant
        ("How much did I spend on food this month?", {"category": choice("groceries")}),
        ("How much did I spend on food this month?", {"category": choice("groceries", 0.6)}),
        ("How much did I spend this month?", {"category": choice("none", 0.6)}),
        ("How much did I spend this month?", {"intent": choice("spending", 0.7)}),
        ("How much did I spend this month?", {"merchant": noul(0.5)}),
        ("How much did I spend in dollars?", {}),  # the rules ask about the currency
        ("What is the weather today?", {"intent": choice("other")}),
    ],
)
def test_other_questions_wait_for_the_model(question, answers, configured, monkeypatch):
    monkeypatch.setattr(intent, "_model_intent", late(MODEL))
    monkeypatch.setattr(intent.triage, "sort_question", lambda *_args: asked(**answers))
    assert parse_intent(question, triaged(configured)) is MODEL


def test_a_security_pick_declines_without_asking_any_model(configured, provider, monkeypatch):
    sort = MagicMock()
    monkeypatch.setattr(intent.triage, "sort_question", sort)
    assert (
        parse_intent("Which stock should I buy?", triaged(configured)).intent == "regulated_advice"
    )
    assert not provider.called and not sort.called
