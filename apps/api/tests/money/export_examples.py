"""Export typed synthetic API examples after seed:fixture-ledger; never reads other databases."""

import json
from pathlib import Path

from fastapi.testclient import TestClient
from finboy.core.config import Settings
from finboy.main import create_app
from finboy.services.money.engine import (
    CashFlowSimulation,
    CommitmentView,
    MoneySummary,
    TransactionView,
)
from finboy.services.money.models import TransactionDetail
from pydantic import TypeAdapter


def main() -> None:
    settings = Settings()
    app = create_app(settings)
    if settings.environment == "production" or app.state.engine.url.database != "finboy_p1":
        raise SystemExit("Examples require the isolated synthetic finboy_p1 ledger.")
    with TestClient(app) as client:
        transactions = client.get("/api/v1/transactions").json()
        TypeAdapter(list[TransactionView]).validate_python(transactions)
        arya = next(item for item in transactions if item["merchant"] == "HOTEL ARYA")
        amazon = next(item for item in transactions if item["amount_minor"] == 79900)
        if arya["category"] != "travel":
            raise SystemExit("Export examples before the first Hotel Arya correction.")
        before = client.get("/api/v1/money/summary").json()
        MoneySummary.model_validate(before)
        correction = {"category": "food_dining"}
        corrected = client.patch(f"/api/v1/transactions/{arya['id']}", json=correction)
        corrected.raise_for_status()
        TransactionDetail.model_validate(corrected.json())
        after = client.get("/api/v1/money/summary").json()
        MoneySummary.model_validate(after)
        commitments = client.get("/api/v1/money/commitments").json()
        TypeAdapter(list[CommitmentView]).validate_python(commitments)
        simulation_request = {"monthly_amount_minor": 500000, "label": "Monthly SIP"}
        simulation = client.post("/api/v1/money/simulations", json=simulation_request).json()
        CashFlowSimulation.model_validate(simulation)
        detail = client.get(f"/api/v1/transactions/{amazon['id']}").json()
        TransactionDetail.model_validate(detail)
        payload = {
            "_provenance": (
                "Rendered 42-message mailbox ingested by the real A1 rules pipeline "
                "into finboy_p1; all data synthetic."
            ),
            "_types": {
                "money_summary": "MoneySummary",
                "transactions": "TransactionView[]",
                "transaction_detail": "TransactionDetail",
                "corrected_detail": "TransactionDetail",
                "commitments": "CommitmentView[]",
                "simulation": "CashFlowSimulation",
                "errors": "ErrorResponse",
            },
            "requests": {
                "summary": "/api/v1/money/summary?period=current_month",
                "explicit_month": (
                    "/api/v1/transactions?period=month&year=2026&month=10"
                    "&status=confirmed&category=food_dining&q=swiggy&limit=50"
                ),
                "correction": correction,
                "simulation": simulation_request,
                "merge": {"keep_id": amazon["id"]},
                "merge_semantics": (
                    "POST /transactions/{merge_id}/merge keeps keep_id; "
                    "response detail is for merge_id (status merged)."
                ),
            },
            "money_summary_before_correction": before,
            "money_summary": after,
            "transactions": client.get("/api/v1/transactions").json(),
            "transaction_detail": detail,
            "corrected_detail": corrected.json(),
            "commitments": commitments,
            "simulation": simulation,
            "errors": {
                "invalid_request_422": client.get("/api/v1/transactions/not-a-uuid").json(),
                "not_found_404": client.get(
                    "/api/v1/transactions/00000000-0000-0000-0000-000000000099"
                ).json(),
                "conflict_409": client.post(
                    f"/api/v1/transactions/{amazon['id']}/merge", json={"keep_id": amazon["id"]}
                ).json(),
            },
        }
    target = Path(__file__).resolve().parents[4] / "docs/handoffs/agent-1-api-examples.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n")
    print("Published typed synthetic API examples.")


if __name__ == "__main__":
    main()
