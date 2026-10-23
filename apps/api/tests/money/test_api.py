import json
from pathlib import Path
from uuid import uuid4

import pytest
from finboy.core.errors import ErrorResponse
from finboy.services.money.engine import (
    CashFlowSimulation,
    CommitmentView,
    MoneySummary,
    TransactionView,
)
from finboy.services.money.models import TransactionDetail
from pydantic import TypeAdapter
from sqlalchemy.exc import OperationalError

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    "path",
    [
        "/money/summary?period=month",
        "/money/summary?period=month&year=2026&month=13",
        "/money/summary?period=current_month&year=2026",
        "/money/summary?period=all",
        "/transactions?status=unknown",
        "/transactions?category=unknown",
        "/transactions?limit=0",
        "/transactions?limit=201",
        "/transactions?limit=1.5",
        "/transactions?q=",
        "/transactions?q=%20%20",
        "/transactions?user_id=private-input",
        "/transactions/not-a-private-uuid",
    ],
)
async def test_invalid_filters_are_redacted_and_not_cached(client, session, path):
    response = await client.get("/api/v1" + path)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert "private" not in response.text
    session.scalars.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"category": "invalid"},
        {"category": None},
        {"merchant": " "},
        {"merchant": "x\ny"},
        {"merchant": "x" * 161},
        {"amount_minor": 0},
        {"amount_minor": -1},
        {"amount_minor": 1.2},
        {"amount_minor": True},
        {"amount_minor": "500"},
        {"amount_minor": 10**14 + 1},
        {"status": "confirmed"},
        {"user_id": str(uuid4())},
        {"confidence": 1},
        {"evidence": {"private": "secret"}},
    ],
)
async def test_corrections_allow_only_valid_fields(client, session, body):
    response = await client.patch(f"/api/v1/transactions/{uuid4()}", json=body)
    assert response.status_code == 422 and response.headers["cache-control"] == "no-store"
    assert "private" not in response.text and "secret" not in response.text
    session.execute.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"monthly_amount_minor": 0},
        {"monthly_amount_minor": -1},
        {"monthly_amount_minor": True},
        {"monthly_amount_minor": 500.5},
        {"monthly_amount_minor": 500, "label": " "},
        {"monthly_amount_minor": 500, "fund": "private fund"},
    ],
)
async def test_invalid_simulations_are_rejected(client, body):
    response = await client.post("/api/v1/money/simulations", json=body)
    assert response.status_code == 422 and response.headers["cache-control"] == "no-store"


async def test_empty_ledger_and_array_contract(client, session):
    session.scalars.return_value = []
    response = await client.get("/api/v1/money/summary")
    assert response.status_code == 200
    summary = MoneySummary.model_validate(response.json())
    assert summary.estimated_unallocated_minor == 0 and summary.evidence_transaction_ids == []
    assert (await client.get("/api/v1/transactions")).json() == []
    assert (await client.get("/api/v1/money/commitments")).json() == []


async def test_detail_unknown_or_wrong_user_is_404(client, session):
    session.scalar.return_value = None
    response = await client.get(f"/api/v1/transactions/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Not Found"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("PATCH", "", {"category": "food_dining"}),
        ("POST", "/confirm", None),
        ("POST", "/reject", None),
        ("POST", "/merge", {"keep_id": str(uuid4())}),
        ("POST", "/keep-separate", None),
    ],
)
async def test_cross_origin_writes_block_before_mutation(client, session, method, suffix, body):
    response = await client.request(
        method,
        f"/api/v1/transactions/{uuid4()}{suffix}",
        json=body,
        headers={"Origin": "https://untrusted.invalid"},
    )
    assert response.status_code == 403 and response.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in response.headers
    session.execute.assert_not_called()


async def test_finance_cors_allows_only_configured_origin(client, session):
    session.scalars.return_value = []
    response = await client.get(
        "/api/v1/money/summary", headers={"Origin": "http://localhost:3000"}
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    response = await client.options(
        "/api/v1/transactions",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert (
        response.status_code == 200 and "PATCH" in response.headers["access-control-allow-methods"]
    )


async def test_database_error_is_truthful_redacted_and_uncached(client, session, caplog):
    session.scalars.side_effect = OperationalError(
        "private SQL", {"amount": "private"}, Exception("secret")
    )
    response = await client.get("/api/v1/money/summary?q=private")
    assert response.status_code == 422
    response = await client.get("/api/v1/money/summary")
    assert (
        response.status_code == 503 and response.json()["error"]["code"] == "database_unavailable"
    )
    assert response.headers["cache-control"] == "no-store"
    assert (
        "private" not in response.text + caplog.text and "secret" not in response.text + caplog.text
    )


async def test_unexpected_error_redacts_exception(client, monkeypatch, caplog):
    from finboy.api.v1 import money

    def fail(*args, **kwargs):
        raise RuntimeError("private financial content")

    monkeypatch.setattr(money, "money_summary", fail)
    response = await client.get("/api/v1/money/summary")
    assert response.status_code == 500 and response.headers["cache-control"] == "no-store"
    assert "private financial content" not in response.text + caplog.text


def test_published_examples_validate_against_frozen_types():
    path = Path(__file__).resolve().parents[4] / "docs/handoffs/agent-1-api-examples.json"
    examples = json.loads(path.read_text())
    MoneySummary.model_validate(examples["money_summary"])
    MoneySummary.model_validate(examples["money_summary_before_correction"])
    TypeAdapter(list[TransactionView]).validate_python(examples["transactions"])
    TypeAdapter(list[CommitmentView]).validate_python(examples["commitments"])
    TransactionDetail.model_validate(examples["transaction_detail"])
    TransactionDetail.model_validate(examples["corrected_detail"])
    CashFlowSimulation.model_validate(examples["simulation"])
    for value in examples["errors"].values():
        ErrorResponse.model_validate(value)
