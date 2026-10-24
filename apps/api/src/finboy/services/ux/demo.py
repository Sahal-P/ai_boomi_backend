"""A fixed synthetic example assembled in memory; never opens a household session."""

import json
from datetime import date
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from finboy.services.money.engine import (
    CommitmentView,
    PeriodSpec,
    TransactionView,
    calculate_summary,
)


def demo_view() -> dict:
    path = (
        Path(__file__).resolve().parents[4] / "fixtures" / "demo_mailbox" / "expected_ledger.json"
    )
    data = json.loads(path.read_text())
    anchor = date.fromisoformat(data["anchor"])
    ids = {
        row["id"]: uuid5(NAMESPACE_URL, "finboy-demo:" + row["id"]) for row in data["transactions"]
    }
    kinds = {
        "debit": "purchase",
        "credit": "income_other",
        "salary": "salary",
        "refund": "refund",
        "reversal": "reversal",
        "investment": "investment",
        "transfer": "transfer",
        "failed": "purchase",
        "fee": "fee",
    }
    records = [
        TransactionView(
            id=ids[row["id"]],
            direction=row["direction"],
            kind=kinds[row["event_type"]],
            amount_minor=row["amount_minor"],
            merchant=row["merchant"],
            category=row["category"],
            occurred_at=row["occurred_at"],
            status=row["status"],
            review_reason=row.get("review_reason"),
            confidence=0.8,
            dataset="demo",
            source_modes=["demo_mailbox"],
            source_count=row["source_count"],
            extraction_quality="complete",
            payment_verification="failed"
            if row["status"] == "failed"
            else "verified"
            if row["status"] == "confirmed"
            else "unverified",
            version="demo-v1",
            linked_transaction_id=ids.get(row.get("linked_to")),
        )
        for row in data["transactions"]
    ]
    commitments = [
        CommitmentView(
            id=uuid5(NAMESPACE_URL, f"finboy-demo:obligation:{i}"),
            kind="emi" if row["id"] == "emi" else "bill",
            label=row["merchant"],
            amount_minor=row["amount_minor"],
            due_date=row["due_date"],
            status=row["status"],
            confidence=0.8,
            dataset="demo",
            version="demo-v1",
        )
        for i, row in enumerate(data["commitments"])
    ]
    summary = calculate_summary(
        records, commitments, period=PeriodSpec(), today=anchor, dataset="demo"
    )
    summary.dataset, summary.data_version = "demo", "demo-v1"
    return {
        "dataset": "demo",
        "read_only": True,
        "as_of": anchor.isoformat(),
        "summary": summary,
        "transactions": records,
        "commitments": commitments,
    }
