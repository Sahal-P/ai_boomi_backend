import json
import logging
from types import SimpleNamespace

import pytest
from finboy.core.config import Settings
from finboy.core.logging import JsonFormatter
from finboy.services.ingestion import llm
from finboy.services.ingestion.normalize import NormalizedMessage
from finboy.services.ingestion.types import Event, Extraction


def test_cache_version_and_model_are_part_of_key():
    message = NormalizedMessage("example.test", "subject", None, "minimized", "hash")
    assert llm.cache_key(message, "first") != llm.cache_key(message, "second")
    assert len(llm.cache_key(message, "first")) == 64


def test_live_sdk_contract_failure_redaction(monkeypatch, caplog):
    # Import is lazy so ordinary offline unit tests do not need the SDK.
    import sys

    seen = {}
    private = "private@upi.test INR 799 Amazon"

    def parse(**kwargs):
        seen.update(kwargs)
        raise RuntimeError(private)

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["timeout"] == 30 and kwargs["max_retries"] == 2
            self.responses = SimpleNamespace(parse=parse)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Client))
    settings = SimpleNamespace(
        openai_api_key=SimpleNamespace(get_secret_value=lambda: "local-test-key"),
        openai_extraction_model="configured-model",
    )
    message = NormalizedMessage("example.test", "s", None, private, "h")
    with caplog.at_level(logging.DEBUG), pytest.raises(llm.ExtractionUnavailable) as caught:
        llm.live_extract(message, settings)
    assert str(caught.value) == "extraction_unavailable"
    assert private not in caplog.text
    assert seen["store"] is False and seen["text_format"] is llm.LLMResult
    assert "tools" not in seen and seen["reasoning"] == {"effort": "none"}
    assert "UNTRUSTED DATA" in seen["input"][0]["content"]


def test_application_formatter_discards_library_payloads():
    record = logging.LogRecord(
        "openai._base_client", logging.DEBUG, "", 0, "private@upi.test INR 799 Amazon", (), None
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["event"] == "server.event"
    assert not any(value in json.dumps(payload) for value in ("private@upi.test", "799", "Amazon"))


def test_llm_unknowns_cannot_fill_unevidenced_values():
    message = NormalizedMessage("example.test", "s", None, "A debit for INR 12.00 occurred.", "h")
    result = llm.LLMResult.model_validate(
        {
            "not_transaction": False,
            "events": [
                {
                    "event_type": "debit",
                    "amount_minor": 1200,
                    "currency": "INR",
                    "merchant": "Made up",
                    "occurred_at": None,
                    "due_date": None,
                    "reference_id": None,
                    "payment_instrument": None,
                    "account_last4": None,
                    "category": "other",
                    "payment_proof": True,
                    "evidence": [
                        {"field": "event_type", "snippet": "debit", "confidence": 1},
                        {"field": "amount_minor", "snippet": "INR 12.00", "confidence": 1},
                    ],
                }
            ],
        }
    )
    event = llm.supported_events(result, message).events[0]
    assert event.merchant is None and not event.payment_proof
    assert event.extraction_method == "llm"


def test_rules_win_on_amount_direction_and_receipt_proof():
    rules = Extraction(events=[Event(event_type="debit", amount_minor=79900, payment_proof=False)])
    model = Extraction(
        events=[Event(event_type="credit", amount_minor=99999900, payment_proof=True)]
    )
    assert llm.merge_evidence(rules, model) == rules


def test_recording_contains_only_structured_output(tmp_path):
    message = NormalizedMessage("example.test", "s", None, "RAW BODY THAT MUST NOT PERSIST", "hash")
    result = llm.LLMResult(events=[], not_transaction=True)
    llm.record(message, result, "configured", tmp_path)
    content = next(tmp_path.glob("*.json")).read_text()
    assert message.text not in content
    assert llm.cassette_extract(message, "configured", tmp_path) == result
    with pytest.raises(llm.ExtractionUnavailable, match="cassette_missing"):
        llm.cassette_extract(message, "other-model", tmp_path)


def test_offline_live_cassettes_match_truth_table():
    from finboy.services.ingestion import evaluate

    result = evaluate.evaluate(
        settings=Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
            environment="test",
            openai_extraction_model=None,
        )
    )
    assert result["passed"], result


def test_llm_amount_evidence_must_match_the_value():
    message = NormalizedMessage("example.test", "s", None, "Debited INR 799.", "h")
    result = llm.LLMResult.model_validate(
        {
            "not_transaction": False,
            "events": [
                {
                    "event_type": "debit",
                    "amount_minor": 99999900,
                    "currency": "INR",
                    "merchant": None,
                    "occurred_at": None,
                    "due_date": None,
                    "reference_id": None,
                    "payment_instrument": None,
                    "account_last4": None,
                    "category": None,
                    "payment_proof": True,
                    "evidence": [
                        {"field": "event_type", "snippet": "Debited", "confidence": 1},
                        {"field": "amount_minor", "snippet": "INR 799", "confidence": 1},
                    ],
                }
            ],
        }
    )
    assert not llm.supported_events(result, message).events


def test_global_live_concurrency_is_bounded(monkeypatch):
    import sys
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    lock = threading.Lock()
    active = peak = 0

    def parse(**kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(active, peak)
        time.sleep(0.02)
        with lock:
            active -= 1
        return SimpleNamespace(output_parsed=llm.LLMResult(events=[], not_transaction=True))

    class Client:
        def __init__(self, **kwargs):
            self.responses = SimpleNamespace(parse=parse)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Client))
    settings = SimpleNamespace(
        openai_api_key=SimpleNamespace(get_secret_value=lambda: "local-test-key"),
        openai_extraction_model="configured-model",
    )
    message = NormalizedMessage("example.test", "s", None, "Synthetic input", "h")
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda _: llm.live_extract(message, settings), range(12)))
    assert 1 < peak <= 4
