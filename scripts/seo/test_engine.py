import json

import pytest

from scripts.seo.__main__ import (
    analyze,
    csv_safe,
    discover,
    import_serp,
    normalize,
    payload,
    reserve_cost,
    save,
)


def test_candidates_deduplicate_and_do_not_inherit_report_ranks(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text(
        "Keyword,Position\n WhatsApp Expense Tracker ,1\nwhatsapp expense tracker,2\n"
    )
    discover(source, "https://example.com/report", tmp_path)
    rows = json.loads((tmp_path / "candidates.json").read_text())
    assert len(rows) == 1
    assert rows[0]["evidence_status"] == "candidate"
    assert "position" not in rows[0]


def test_budget_rejects_before_loading_credentials(tmp_path, monkeypatch):
    save(tmp_path / "candidates.json", [{"keyword": "voice tracker", "source": "report"}])
    monkeypatch.setattr("scripts.seo.__main__.key_from_store", lambda: pytest.fail("key loaded"))
    with pytest.raises(ValueError, match="budget_exceeded"):
        analyze(tmp_path, 1, 0.000000001)
    assert reserve_cost(payload("voice tracker")) > 0


@pytest.mark.parametrize("text", ["=cmd()", " +SUM(A1)", "-1+1", "@test"])
def test_csv_formula_escape(text):
    assert csv_safe(text).startswith("'")


def test_unknown_metrics_and_normalization():
    assert csv_safe(None) == ""
    assert normalize("  Voice   TRACKER ") == "voice tracker"


def test_search_tool_order_cannot_be_imported_as_verified_ranking(tmp_path):
    observation = {
        "query": "voice tracker",
        "engine": "search_tool",
        "country": "IN",
        "language": "en",
        "device": "unknown",
        "observed_at": "2026-01-01T00:00:00Z",
        "evidence_url": "https://example.com/search",
        "ranking_verified": True,
        "results": [{"position": 1, "url": "https://example.com/", "title": "Tracker"}],
    }
    source = tmp_path / "serp.jsonl"
    source.write_text(json.dumps(observation))
    with pytest.raises(ValueError, match="unverified_ranking"):
        import_serp(source, tmp_path)


def test_opportunity_weights_and_bounds():
    from scripts.seo.assess import score

    assert score(5, 5, 5, 5) == 100
    assert score(5, 0, 0, 0) == 40
    assert score(0, 5, 0, 0) == 30
    with pytest.raises(ValueError, match="invalid_score"):
        score(6, 0, 0, 0)


def test_provider_malformed_response_is_not_cached(tmp_path, monkeypatch):
    import httpx

    from scripts.seo.__main__ import QUESTIONS, run_decisions

    real_client = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"answers": {}}))
    monkeypatch.setattr("scripts.seo.__main__.key_from_store", lambda: "local-test-key")
    monkeypatch.setattr(
        "scripts.seo.__main__.httpx.Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    path = tmp_path / "cache.json"
    results, reserved = run_decisions(
        [("voice tracker", payload("voice tracker"), path)], 0.25, QUESTIONS
    )
    assert results == {"voice tracker": None}
    assert reserved > 0
    assert not path.exists()


def test_retries_cannot_exceed_run_budget(tmp_path, monkeypatch):
    import httpx

    from scripts.seo.__main__ import QUESTIONS, run_decisions

    real_client = httpx.Client
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(429)

    transport = httpx.MockTransport(respond)
    monkeypatch.setattr("scripts.seo.__main__.key_from_store", lambda: "local-test-key")
    monkeypatch.setattr(
        "scripts.seo.__main__.httpx.Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    body = payload("voice tracker")
    amount = reserve_cost(body)
    results, reserved = run_decisions(
        [("voice tracker", body, tmp_path / "cache.json")], amount * 1.1, QUESTIONS
    )
    assert len(calls) == 1
    assert reserved == amount
    assert results["voice tracker"] is None


def test_cost_reservation_counts_every_question():
    body = payload("voice tracker")
    doubled = body | {"questions": body["questions"] | {"another": body["questions"]["fit"]}}
    assert reserve_cost(doubled) > reserve_cost(body)


def test_search_evidence_file_must_exist(tmp_path):
    observation = {
        "query": "voice tracker",
        "engine": "search_tool",
        "country": "unknown",
        "language": "en",
        "device": "unknown",
        "observed_at": "2026-01-01T00:00:00Z",
        "evidence_file": "search-evidence/query-001.txt",
        "results": [],
    }
    path = tmp_path / "serp.jsonl"
    path.write_text(json.dumps(observation))
    with pytest.raises(ValueError, match="missing_evidence_file"):
        import_serp(path, tmp_path)
