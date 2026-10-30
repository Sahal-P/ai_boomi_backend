"""The d1-ultra adapter and the race with today's model call; no credentials or network."""

import json
import logging
import threading
import time
from unittest.mock import MagicMock

import httpx
import pytest
from finboy.api.v1.readiness import _triage
from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.logging import JsonFormatter
from finboy.services.triage import evaluate, provider, service
from finboy.services.triage.provider import Choice, Noul
from finboy.services.triage.service import Sorted
from pydantic import ValidationError

from .support import choice, held, noul, sorted_answers, triaged

QUESTIONS: dict[str, provider.Question] = {
    "kind": Choice(instructions="What is it?", criteria={"spent": "Paid", "other": "Else"}),
    "payee": Noul(instructions="Does it name a payee?"),
}
KIND = {"type": "choice", "choice": "spent", "probabilities": {"spent": 0.97, "other": 0.03}}


@pytest.fixture
def liquid(settings: Settings) -> Settings:
    return triaged(settings)


def mock_http(monkeypatch: pytest.MonkeyPatch, handler) -> MagicMock:
    calls = MagicMock(side_effect=handler)
    monkeypatch.setattr(
        provider,
        "decision_client",
        lambda settings: httpx.Client(transport=httpx.MockTransport(calls)),
    )
    return calls


def answered(**answers: object) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "d1-ultra",
            "answers": answers,
            "usage": {"input_tokens": 84, "output_tokens": 0},
        },
    )


def test_a_decision_request_and_its_answers(monkeypatch, liquid) -> None:
    calls = mock_http(
        monkeypatch,
        lambda request: answered(
            kind=KIND | {"confidence": 0.96}, payee={"type": "noul", "noul": 0.02}
        ),
    )
    answers = provider.decide("chai 20", QUESTIONS, liquid, images=(b"jpeg",))
    assert answers["kind"].choice == "spent" and answers["payee"].noul == 0.02
    request: httpx.Request = calls.call_args.args[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.liquid.ai/decisions/v1/systemone"
    assert request.headers["authorization"] == "Bearer liquid_synthetic"
    body = json.loads(request.content)
    assert body["model"] == "d1-ultra" and body["state"] == "chai 20"
    assert body["questions"] == {
        "kind": {
            "type": "choice",
            "instructions": "What is it?",
            "criteria": {"spent": "Paid", "other": "Else"},
        },
        "payee": {"type": "noul", "instructions": "Does it name a payee?"},
    }
    assert body["images"] == [{"content_type": "image/jpeg", "base64": "anBlZw=="}]


def _status(status: int):
    return lambda request: httpx.Response(status, json={"error": "NEVER-LEAK"})


def _timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("NEVER-LEAK-timeout", request=request)


@pytest.mark.parametrize(
    "handler",
    [
        *[_status(status) for status in (401, 403, 429, 500, 503)],
        lambda request: httpx.Response(302, headers={"Location": "https://redirect.test/"}),
        lambda request: httpx.Response(200, content=b"NEVER-LEAK not json"),
        lambda request: httpx.Response(200, content=b'{"answers":"' + b"x" * 70_000 + b'"}'),
        lambda request: answered(kind=KIND),  # a question left unanswered
        lambda request: answered(kind=KIND, payee=KIND),  # the wrong type
        lambda request: answered(kind=KIND | {"choice": "due"}, payee={"type": "noul", "noul": 0}),
        lambda request: answered(kind=KIND, payee={"type": "noul", "noul": 1.5}),
        _timeout,
    ],
)
def test_failures_are_fixed_and_redacted(monkeypatch, liquid, handler, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    mock_http(monkeypatch, handler)
    with pytest.raises(ProviderUnavailable) as exc:
        provider.decide("PRIVATE chai 20", QUESTIONS, liquid)
    assert exc.value.code == "provider_unavailable"
    assert "NEVER-LEAK" not in str(exc.value) and "NEVER-LEAK" not in caplog.text
    assert "PRIVATE" not in caplog.text


@pytest.mark.parametrize(
    "update",
    [
        {"liquid_api_key": None},
        {"liquid_decision_model": None},
        {"liquid_decision_model": "d1.1"},  # only the model that passed the gate
    ],
)
def test_unconfigured_decisions_are_never_sent(monkeypatch, liquid, update) -> None:
    calls = mock_http(monkeypatch, lambda request: answered(kind=KIND))
    with pytest.raises(ProviderUnavailable) as exc:
        provider.decide("chai 20", QUESTIONS, liquid.model_copy(update=update))
    assert exc.value.code == "configuration_missing" and not calls.called


@pytest.mark.parametrize(
    ("probability", "expected"), [(0.97, "spent"), (0.85, "spent"), (0.84, None)]
)
def test_a_choice_counts_only_when_sure(probability: float, expected: str | None) -> None:
    sort = sorted_answers(kind=choice("spent", probability))
    assert sort.pick("kind") == expected
    assert sort.pick("kind", 0.98) is None and sort.pick("missing") is None


@pytest.mark.parametrize(
    ("probability", "expected"),
    [(0.02, False), (0.1, False), (0.5, None), (0.9, True), (0.97, True)],
)
def test_yes_or_no_only_when_clear(probability: float, expected: bool | None) -> None:
    assert sorted_answers(payee=noul(probability)).says("payee") is expected


def test_sorting_is_skipped_when_off_or_not_for_the_language(monkeypatch, liquid) -> None:
    decide = MagicMock(return_value={"kind": choice("spent")})
    monkeypatch.setattr(provider, "decide", decide)
    assert (
        service.sort_message("chai 20", "en", liquid.model_copy(update={"triage_enabled": False}))
        is None
    )
    malayalam_off = liquid.model_copy(update={"triage_languages": ["en", "hi"]})
    assert service.sort_message("ചായ 20", "ml", malayalam_off) is None
    assert not decide.called
    sort = service.sort_message("chai 20", "en", liquid)
    assert sort is not None and sort.pick("kind") == "spent"
    assert decide.call_args.args[:2] == ("chai 20", service.MESSAGE)


def test_an_unavailable_sort_is_none_and_logs_no_content(monkeypatch, liquid, caplog) -> None:
    caplog.set_level(logging.INFO)

    def down(*_args, **_kwargs):
        raise ProviderUnavailable()

    monkeypatch.setattr(provider, "decide", down)
    assert service.sort_question("PRIVATE how much on food?", "en", liquid) is None
    record = next(r for r in caplog.records if r.msg == "triage.sorted")
    logged = json.loads(JsonFormatter().format(record))
    assert logged["outcome"] == "unavailable" and logged["provider"] == "liquid"
    assert logged["model"] == "d1-ultra" and "latency_ms" in logged
    assert "PRIVATE" not in caplog.text


def outcomes(caplog) -> list[str]:
    return [r.outcome for r in caplog.records if r.msg == "triage.answered"]


def slow(value: str) -> str:
    time.sleep(0.05)
    return value


def test_off_runs_only_the_model(settings, caplog) -> None:
    caplog.set_level(logging.INFO)
    sort = MagicMock()
    assert service.first("message", settings, lambda: "model", sort, lambda _: "fast") == "model"
    assert not sort.called and outcomes(caplog) == ["model"]


def test_a_sure_sort_answers_while_the_model_is_still_working(liquid, caplog) -> None:
    caplog.set_level(logging.INFO)
    release = threading.Event()
    try:
        answer = service.first(
            "message", liquid, held("model", release), lambda: "sorted", lambda _: "fast"
        )
    finally:
        release.set()
    assert answer == "fast" and outcomes(caplog) == ["fast"]


def test_the_model_answers_when_it_finishes_first(liquid) -> None:
    release = threading.Event()
    try:
        answer = service.first(
            "message", liquid, lambda: "model", held("sorted", release), lambda _: "fast"
        )
    finally:
        release.set()
    assert answer == "model"


def test_an_unsure_sort_waits_for_the_model(liquid) -> None:
    assert (
        service.first("message", liquid, lambda: slow("model"), lambda: "sorted", lambda _: None)
        == "model"
    )
    assert (
        service.first("message", liquid, lambda: slow("model"), lambda: None, lambda _: "fast")
        == "model"
    )


def test_a_failed_model_is_covered_by_a_sure_sort(liquid) -> None:
    def broken() -> str:
        raise ProviderUnavailable("assistant_unavailable")

    assert (
        service.first("question", liquid, broken, lambda: slow("sorted"), lambda _: "fast")
        == "fast"
    )


def test_without_a_sure_sort_the_models_error_stands(liquid, caplog) -> None:
    caplog.set_level(logging.INFO)

    def broken() -> str:
        raise ProviderUnavailable("assistant_unavailable")

    with pytest.raises(ProviderUnavailable) as exc:
        service.first("question", liquid, broken, lambda: "sorted", lambda _: None)
    assert exc.value.code == "assistant_unavailable" and outcomes(caplog) == ["failed"]


def test_a_broken_sort_or_reading_falls_back_to_the_model(liquid, caplog) -> None:
    caplog.set_level(logging.INFO)

    def boom(*_args: object) -> str:
        raise RuntimeError("NEVER-LEAK")

    assert (
        service.first("message", liquid, lambda: slow("model"), boom, lambda _: "fast") == "model"
    )
    assert (
        service.first("message", liquid, lambda: slow("model"), lambda: "sorted", boom) == "model"
    )
    assert "NEVER-LEAK" not in caplog.text


def test_the_category_hints_cover_every_category() -> None:
    from typing import get_args

    from finboy.services.ingestion.types import Category

    assert list(service.CATEGORIES) == list(service.CATEGORY_HINTS)
    assert set(service.CATEGORY_HINTS) == set(get_args(Category))
    criteria = service.MESSAGE["category"]
    assert isinstance(criteria, Choice) and set(criteria.criteria) == {*get_args(Category), "none"}


@pytest.mark.parametrize(
    ("update", "expected"),
    [
        ({"triage_enabled": False}, "off"),
        ({"liquid_api_key": None}, "missing"),
        ({"liquid_decision_model": "d1.1"}, "missing"),
        ({}, "configured"),
    ],
)
def test_readiness_reports_the_triage_configuration(liquid, update, expected) -> None:
    assert _triage(liquid.model_copy(update=update)) == expected


def test_the_liquid_url_must_be_https() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
            liquid_base_url="http://api.liquid.ai",
        )


def test_the_gate_cases_agree_with_the_code() -> None:
    """With perfect d1-ultra answers every case is answered as labelled, and no rule answers a
    case before d1-ultra sees it (`pnpm eval:triage --check`)."""
    assert evaluate.check() == []
    labels = {case["route"] for case in evaluate.cases()}
    assert labels == {"message", "question", "image"}


def test_the_gate_report_passes_perfect_answers_and_blocks_a_dropped_payee(
    monkeypatch, liquid
) -> None:
    monkeypatch.setattr(evaluate, "sort_case", lambda case, settings: (evaluate.ideal(case), 5.0))
    result = evaluate.evaluate(liquid)
    assert result["latency_ms"] == {"p50": 5, "p95": 5} and result["runs"] == evaluate.RUNS
    assert {name for name in result["gate"]} == {"en", "hi", "ml", "images"}
    assert all(
        group["passed"] and not group["mistakes"] and group["fast_share"] == 1
        for group in result["gate"].values()
    )

    def unsure_of_payees(case, settings):
        sort = evaluate.ideal(case)
        if case.get("why") == "payee":  # d1-ultra misses the name: a fast answer drops it
            sort = Sorted({**sort.answers, "payee": noul(0.02)})
        return sort, 5.0

    monkeypatch.setattr(evaluate, "sort_case", unsure_of_payees)
    gate = evaluate.evaluate(liquid)["gate"]
    assert not gate["en"]["passed"] and gate["en"]["mistakes"][0]["blocking"]


def test_the_gate_report_counts_a_wrong_category_without_blocking(monkeypatch, liquid) -> None:
    def tea_as_groceries(case, settings):
        sort = evaluate.ideal(case)
        if case["id"] == "en-m01":  # "chai 20"
            sort = Sorted({**sort.answers, "category": choice("groceries", 1.0)})
        return sort, 5.0

    monkeypatch.setattr(evaluate, "sort_case", tea_as_groceries)
    english = evaluate.evaluate(liquid, runs=1)["gate"]["en"]
    assert english["mistakes"] == [{"id": "en-m01", "mistake": "detail", "blocking": False}]
    assert english["mistake_rate"] == round(1 / english["answers"], 3) and english["passed"]
