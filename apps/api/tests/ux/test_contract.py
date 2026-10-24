"""Trust semantics and safe HTTP failures without a PostgreSQL dependency."""

from datetime import date, datetime
from uuid import uuid4

import pytest
from finboy.core.clock import IST
from finboy.services.assistant.intent import rule_intent
from finboy.services.money.engine import (
    CommitmentView,
    PeriodSpec,
    TransactionView,
    calculate_summary,
)
from finboy.services.money.models import Correction
from finboy.services.ux.decisions import DecisionRequest
from finboy.services.ux.demo import demo_view
from finboy.services.ux.state import TaskError
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError


def test_due_day_and_month_rollover_never_release_an_unpaid_liability():
    income = TransactionView(
        id=uuid4(),
        direction="in",
        kind="salary",
        amount_minor=1000000,
        merchant="Synthetic employer",
        category="salary",
        occurred_at=datetime(2026, 10, 1, tzinfo=IST),
        status="confirmed",
        confidence=1,
    )
    obligation = CommitmentView(
        id=uuid4(),
        kind="bill",
        label="Synthetic bill",
        amount_minor=100000,
        due_date=date(2026, 10, 23),
        status="upcoming",
        confidence=0.4,
    )
    values = []
    for day in [date(2026, 10, 22), date(2026, 10, 23), date(2026, 10, 24)]:
        summary = calculate_summary([income], [obligation], period=PeriodSpec(), today=day)
        values.append(summary.estimated_unallocated_minor)
        assert summary.unresolved_commitments_minor == summary.uncertain_commitments_minor == 100000
    assert values == [900000] * 3
    next_month = calculate_summary([], [obligation], period=PeriodSpec(), today=date(2026, 11, 1))
    assert next_month.overdue_commitments_minor == 100000
    assert next_month.estimated_unallocated_minor == -100000
    for status in ["paid", "dismissed"]:
        resolved = obligation.model_copy(update={"status": status})
        assert (
            calculate_summary(
                [income], [resolved], period=PeriodSpec(), today=date(2026, 10, 24)
            ).estimated_unallocated_minor
            == 1000000
        )


def test_pure_summary_rejects_cross_dataset_claims_and_demo_has_fixed_identity():
    sample = demo_view()
    assert sample["summary"].estimated_unallocated_minor == 1478000
    assert sample["summary"].dataset == "demo"
    household = calculate_summary(
        sample["transactions"], sample["commitments"], period=PeriodSpec(), today=date(2026, 10, 28)
    )
    assert (
        household.tracked_income_minor
        == household.confirmed_outflows_minor
        == household.unresolved_commitments_minor
        == 0
    )
    assert {row.id for row in sample["transactions"]} == {
        row.id for row in demo_view()["transactions"]
    }


def test_relative_periods_resolve_against_ist_across_year_boundary(monkeypatch):
    monkeypatch.setattr("finboy.services.assistant.intent.today_ist", lambda: date(2027, 1, 1))
    assert rule_intent("Amazon spending last month").period == PeriodSpec(
        kind="month", year=2026, month=12
    )
    assert rule_intent("food spending yesterday").period.start_date == date(2026, 12, 31)
    assert rule_intent("food spending today").period.end_date == date(2027, 1, 1)
    assert rule_intent("food spending this week").clarification_reason == "period"
    assert rule_intent("food spending 2026-13").clarification_reason == "period"
    assert rule_intent("food spending 2026-10").period == PeriodSpec(
        kind="month", year=2026, month=10
    )


@pytest.mark.parametrize(
    "body",
    [
        {"occurred_at": "2026-10-24T10:00:00"},
        {"amount_minor": True},
        {"kind": "bill_due"},
        {"direction": "unknown"},
    ],
)
def test_invalid_fact_corrections_are_rejected(body):
    with pytest.raises(ValidationError):
        Correction.model_validate(body)


@pytest.mark.parametrize(
    "body",
    [
        {"expected_version": "1", "action": "merge"},
        {"expected_version": "1", "action": "correct"},
        {"expected_version": "1", "action": "reject", "correction": {"amount_minor": 100}},
    ],
)
def test_invalid_decision_payloads_cannot_start_a_write(body):
    with pytest.raises(ValidationError):
        DecisionRequest.model_validate(body)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path",
    [
        "/transactions/page?scope=unresolved&status=confirmed",
        "/transactions/page?limit=201",
        "/transactions/page?offset=-1",
        "/transactions/page?dataset=demo",
        "/imports?limit=101",
        "/imports?offset=-1",
        "/money/obligations?status=unknown",
    ],
)
async def test_new_http_inputs_are_bounded_and_redacted(client, session, path):
    response = await client.get("/api/v1" + path)
    assert response.status_code == 422
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"
    session.scalar.assert_not_called()


@pytest.mark.anyio
async def test_task_failure_codes_and_database_errors_do_not_leak(client, monkeypatch):
    def conflict(*args, **kwargs):
        raise TaskError("version_conflict")

    monkeypatch.setattr("finboy.api.v1.transactions.transaction_page", conflict)
    result = await client.get("/api/v1/transactions/page")
    assert result.status_code == 409 and result.json()["error"]["code"] == "version_conflict"

    def unavailable(*args, **kwargs):
        raise OperationalError(
            "PRIVATE_SQL", {"private": "PRIVATE_INPUT"}, RuntimeError("PRIVATE_DATABASE")
        )

    monkeypatch.setattr("finboy.api.v1.transactions.transaction_page", unavailable)
    result = await client.get("/api/v1/transactions/page")
    assert result.status_code == 503 and "PRIVATE" not in result.text


@pytest.mark.anyio
async def test_public_demo_is_session_independent_and_old_mutation_has_no_writes(client, session):
    assert (await client.get("/api/v1/demo")).status_code == 200
    result = await client.post("/api/v1/imports/demo")
    assert result.status_code == 409 and result.json()["error"]["code"] == "demo_read_only"
    session.execute.assert_not_called()
    session.add.assert_not_called()


def test_literal_merchant_questions_cannot_silently_become_all_spending():
    parsed = rule_intent("How much did I spend at Sample Bookshop today?")
    assert parsed.intent == "merchant_lookup" and parsed.merchant == "sample bookshop"
    assert rule_intent("How much did I spend on food today?").category == "food_dining"
    combined = rule_intent("Amazon shopping spending this month")
    assert combined.merchant == "amazon" and combined.category == "shopping"
