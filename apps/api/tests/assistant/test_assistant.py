import json
import re
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.services.assistant import intent
from finboy.services.assistant.intent import (
    ParsedIntent,
    amounts_in_question,
    parse_intent,
    rule_intent,
)
from finboy.services.assistant.language import normalize_speech, numeric_guard, resolve_style
from finboy.services.assistant.service import answer_question
from finboy.services.assistant.templates import DISCLAIMER
from finboy.services.money import engine
from pydantic import ValidationError

CASES = json.loads((Path(__file__).parents[2] / "fixtures/voice/intent_cases.json").read_text())


def summary() -> engine.MoneySummary:
    return engine.MoneySummary(
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        as_of=date(2026, 10, 28),
        tracked_income_minor=6200000,
        confirmed_outflows_minor=3742000,
        upcoming_commitments_minor=980000,
        estimated_unallocated_minor=1478000,
        pending_review_count=2,
        pending_review_minor=50000,
        income_transaction_count=1,
        outflow_transaction_count=20,
        commitment_count=3,
        categories=[
            engine.CategoryTotal(category="food_dining", amount_minor=786000, transaction_count=7)
        ],
        evidence_transaction_ids=[],
    )


@pytest.fixture
def money_engine(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    sample = summary()
    simulation = engine.CashFlowSimulation(
        summary=sample,
        proposed_monthly_minor=500000,
        remaining_after_proposal_minor=978000,
        lines=[
            engine.SimulationLine(label_key=key, amount_minor=amount, sign=sign)
            for key, amount, sign in [
                ("tracked_income", 6200000, "+"),
                ("confirmed_outflows", 3742000, "-"),
                ("upcoming_commitments", 980000, "-"),
                ("proposed_monthly", 500000, "-"),
            ]
        ],
        warnings=["pending_review_items"],
    )
    fakes = {
        "money_summary": MagicMock(return_value=sample),
        "category_breakdown": MagicMock(return_value=sample.categories),
        "find_transactions": MagicMock(return_value=[]),
        "simulate_monthly_commitment": MagicMock(return_value=simulation),
    }
    for name, fake in fakes.items():
        monkeypatch.setattr(engine, name, fake)
    return fakes


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_offline_closed_intents(case: dict[str, str | None]) -> None:
    parsed = rule_intent(case["text"])
    assert (parsed.intent, parsed.category) == (case["intent"], case["category"])


@pytest.mark.parametrize("style", ["en", "hi", "ml", "hinglish", "manglish"])
def test_equivalent_engine_facts_and_native_speech(
    style: str, settings: Settings, session: MagicMock, money_engine: dict[str, MagicMock]
) -> None:
    for question, expected in [
        ("How much did I spend on food this month?", 786000),
        ("What is my estimated unallocated amount?", 1478000),
        ("Would a 5000 monthly SIP fit?", 978000),
    ]:
        answer = answer_question(
            session, user_id=LOCAL_USER_ID, text=question, display_style=style, settings=settings
        )
        assert answer.policy == "answer"
        assert expected in [f.amount_minor for f in answer.facts]
        assert "pending_review_items" in answer.warnings
        if answer.simulation:
            assert answer.display_text.endswith(DISCLAIMER)
            assert answer.simulation.remaining_after_proposal_minor == expected
        if style in {"hi", "hinglish"}:
            assert answer.speech_language == "hi"
            assert re.search(r"[\u0900-\u097f]", answer.speech_text)
            assert not re.search(r"[A-Za-z]", answer.speech_text)
        if style in {"ml", "manglish"}:
            assert answer.speech_language == "ml"
            assert re.search(r"[\u0d00-\u0d7f]", answer.speech_text)
            assert not re.search(r"[A-Za-z]", answer.speech_text)
    money_engine["simulate_monthly_commitment"].assert_called_with(
        session,
        user_id=LOCAL_USER_ID,
        monthly_amount_minor=500000,
        label="Proposed monthly commitment",
    )


@pytest.mark.parametrize(
    "question", ["Which mutual fund should I buy?", "कौन सा शेयर खरीदना चाहिए?", "ഏത് ഫണ്ട് വാങ്ങണം?"]
)
def test_advice_declines_without_loading_money(
    question: str, settings: Settings, session: MagicMock, money_engine: dict[str, MagicMock]
) -> None:
    answer = answer_question(
        session, user_id=LOCAL_USER_ID, text=question, display_style="auto", settings=settings
    )
    assert answer.policy == "decline" and answer.intent == "regulated_advice"
    assert answer.facts == [] and answer.simulation is None
    for fake in money_engine.values():
        fake.assert_not_called()


def test_cashflow_amount_is_grounded_and_period_is_not_assumed(settings: Settings) -> None:
    assert amounts_in_question("₹5,000.25 / ५०००.२५ / ൫൦൦൦.൨൫") == {500025}
    assert rule_intent("Would a monthly SIP fit?").amount_minor is None
    assert rule_intent("food spending last month").intent == "clarification"
    assert rule_intent("food spending 2026-09").period == engine.PeriodSpec(
        kind="month", year=2026, month=9
    )
    with pytest.raises(ValidationError):
        ParsedIntent(intent="run_sql")
    with pytest.raises(ValidationError):
        ParsedIntent(intent="spending_query", category="arbitrary")


def test_numeric_hallucinations_and_dropped_numbers_are_rejected() -> None:
    template = "Tracked spending ₹7,860.50, remaining ₹9,780."
    assert numeric_guard("Spending ₹9,999.50, remaining ₹9,780.", template) == template
    assert numeric_guard("Spending ₹7,860.50.", template) == template
    assert (
        numeric_guard("Spending ₹7,860.50, remaining ₹9,780, 99 percent sure.", template)
        == template
    )
    assert numeric_guard("Recorded spend ₹7,860.50, left ₹9,780.", template) != template


def test_normalization_preserves_paise_dates_and_acronyms() -> None:
    assert (
        normalize_speech("₹7,860.50 SIP EMI UPI 2026-10-28", "hi")
        == "7,860 रुपये 50 पैसे एस आई पी ई एम आई यू पी आई 28 अक्टूबर 2026"
    )
    assert normalize_speech("₹0.25 SIP", "ml") == "0 രൂപ 25 പൈസ എസ് ഐ പി"
    assert resolve_style("Ee masam foodinu ethra poyi?", "auto") == ("manglish", "ml")
    assert resolve_style("Is mahine khane par kitna kharch hua?", "auto") == ("hinglish", "hi")


def test_provider_intent_cannot_invent_amount_or_merchant(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    settings = settings.model_copy(
        update={
            "openai_api_key": __import__("pydantic").SecretStr("synthetic"),
            "openai_assistant_model": "configured",
        }
    )
    fake = MagicMock()
    fake.return_value.__enter__.return_value.responses.parse.return_value.output_parsed = (
        ParsedIntent(intent="affordability_check", amount_minor=999900)
    )
    monkeypatch.setattr(intent, "OpenAI", fake)
    assert parse_intent("Can this payment work for me?", settings).intent == "clarification"
    request = fake.return_value.__enter__.return_value.responses.parse.call_args.kwargs
    assert request["store"] is False and "tools" not in request


@pytest.mark.anyio
async def test_http_answer_and_cors(
    client: httpx.AsyncClient, money_engine: dict[str, MagicMock]
) -> None:
    response = await client.post(
        "/api/v1/assistant/ask",
        json={"text": "इस महीने खाने पर कितना खर्च हुआ?", "display_style": "auto"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200
    assert response.json()["facts"][0]["amount_minor"] == 786000
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    bad = await client.post("/api/v1/assistant/ask", json={"text": " ", "display_style": "auto"})
    assert bad.status_code == 422


@pytest.mark.parametrize(
    "question", ["Can I buy a stock for 5000?", "Pick a fund for me", "Which share should I sell?"]
)
def test_security_recommendations_never_become_affordability(question: str) -> None:
    assert rule_intent(question).intent == "regulated_advice"
