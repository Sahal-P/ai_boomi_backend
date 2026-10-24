from datetime import date, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from finboy.core.clock import IST
from finboy.services.money.engine import (
    CommitmentView,
    PeriodSpec,
    TransactionView,
    calculate_simulation,
    calculate_summary,
    find_transactions,
    period_dates,
    simulate_monthly_commitment,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

TODAY = date(2026, 10, 28)


def transaction(**changes: object) -> TransactionView:
    values = dict(
        id=uuid4(),
        direction="out",
        kind="purchase",
        amount_minor=10000,
        merchant="Synthetic shop",
        category="shopping",
        occurred_at=datetime(2026, 10, 5, 12, tzinfo=IST),
        status="confirmed",
        confidence=0.99,
    )
    return TransactionView.model_validate(values | changes)


def commitment(**changes: object) -> CommitmentView:
    return CommitmentView.model_validate(
        dict(
            id=uuid4(),
            kind="bill",
            label="Synthetic bill",
            amount_minor=10000,
            due_date=TODAY,
            status="upcoming",
            confidence=0.99,
        )
        | changes
    )


def summary(records=(), commitments=(), **kwargs):
    return calculate_summary(records, commitments, period=PeriodSpec(), today=TODAY, **kwargs)


def test_income_net_refunds_reversals_evidence_and_counts():
    salary = transaction(direction="in", kind="salary", category="salary", amount_minor=100000)
    other = transaction(direction="in", kind="income_other", category="other_income")
    purchase = transaction()
    refund = transaction(direction="in", kind="refund", linked_transaction_id=purchase.id)
    debit = transaction(category="food_dining", amount_minor=700)
    reversal = transaction(
        direction="in", kind="reversal", amount_minor=700, linked_transaction_id=debit.id
    )
    remaining = transaction(category="food_dining", amount_minor=3000)
    records = [salary, other, purchase, refund, debit, reversal, remaining]
    result = summary(records, [commitment()])
    assert result.tracked_income_minor == 110000
    assert result.confirmed_outflows_minor == 3000
    assert result.upcoming_commitments_minor == 10000
    assert result.estimated_unallocated_minor == 97000
    assert result.income_transaction_count == 2 and result.outflow_transaction_count == 5
    assert set(result.evidence_transaction_ids) == {row.id for row in records}
    assert {row.category: row.amount_minor for row in result.categories} == {
        "shopping": 0,
        "food_dining": 3000,
    }


@pytest.mark.parametrize("status", ["needs_review", "rejected", "merged", "failed"])
@pytest.mark.parametrize(
    "direction,kind", [("out", "purchase"), ("in", "salary"), ("in", "refund")]
)
def test_unconfirmed_statuses_never_count(status, direction, kind):
    result = summary([transaction(status=status, direction=direction, kind=kind)])
    assert result.tracked_income_minor == result.confirmed_outflows_minor == 0
    assert result.evidence_transaction_ids == [] and result.categories == []
    assert result.pending_review_count == (1 if status == "needs_review" else 0)


@pytest.mark.parametrize("direction", ["in", "out"])
def test_transfers_excluded(direction):
    result = summary([transaction(kind="transfer", direction=direction)])
    assert result.estimated_unallocated_minor == 0
    assert result.evidence_transaction_ids == []


def test_month_uses_ist_boundaries_including_microseconds():
    stamps = [
        "2026-09-30T18:29:59.999999+00:00",
        "2026-09-30T18:30:00+00:00",
        "2026-10-31T18:29:59.999999+00:00",
        "2026-10-31T18:30:00+00:00",
    ]
    rows = [transaction(occurred_at=datetime.fromisoformat(stamp)) for stamp in stamps]
    result = summary(rows)
    assert result.period_start == date(2026, 10, 1) and result.period_end == date(2026, 10, 31)
    assert result.as_of == TODAY
    assert set(result.evidence_transaction_ids) == {rows[1].id, rows[2].id}
    assert result.confirmed_outflows_minor == 20000
    assert period_dates(PeriodSpec(kind="month", year=2024, month=2), TODAY)[1].day == 29
    assert period_dates(PeriodSpec(kind="month", year=9999, month=12), TODAY)[1] == date(
        9999, 12, 31
    )


def test_upcoming_dates_and_statuses_are_inclusive_and_month_bounded():
    items = [
        commitment(due_date=date(2026, 10, 27)),
        commitment(due_date=TODAY),
        commitment(due_date=date(2026, 10, 31)),
        commitment(due_date=date(2026, 11, 1)),
        commitment(status="paid"),
        commitment(status="dismissed"),
    ]
    result = summary(commitments=items)
    assert result.commitment_count == 3 and result.upcoming_commitments_minor == 20000
    assert result.overdue_commitments_minor == 10000
    assert result.unresolved_commitments_minor == 30000
    past = calculate_summary(
        [], items, period=PeriodSpec(kind="month", year=2026, month=9), today=TODAY
    )
    assert past.upcoming_commitments_minor == 0
    future = calculate_summary(
        [], items, period=PeriodSpec(kind="month", year=2026, month=11), today=TODAY
    )
    assert future.commitment_count == 4


def test_refund_uses_original_corrected_category_across_periods_and_can_be_negative():
    original_id = uuid4()
    refund = transaction(direction="in", kind="refund", linked_transaction_id=original_id)
    result = summary([refund], linked_categories={original_id: "food_dining"})
    assert result.categories[0].category == "food_dining"
    assert result.confirmed_outflows_minor == -10000
    assert result.estimated_unallocated_minor == 10000
    assert result.tracked_income_minor == 0


def test_empty_ledger_and_simulation_disclaimer():
    result = summary()
    assert result.estimated_unallocated_minor == 0 and result.pending_review_minor == 0
    assert result.categories == [] and result.commitment_count == 0
    simulation = calculate_simulation(result, 500000)
    assert simulation.remaining_after_proposal_minor == -500000
    assert simulation.warnings == ["negative_remaining", "incomplete_coverage"]
    assert simulation.disclaimer_key == "cash_flow_model_not_investment_advice"
    assert [line.sign for line in simulation.lines] == ["+", "-", "-", "-", "-"]


def test_review_negative_and_low_buffer_warning_boundaries():
    result = summary(
        [
            transaction(direction="in", kind="salary", amount_minor=100000),
            transaction(amount_minor=80000),
            transaction(status="needs_review"),
        ]
    )
    assert "pending_review_items" in calculate_simulation(result, 10000).warnings
    assert "low_buffer" not in calculate_simulation(result, 10000).warnings
    assert "low_buffer" in calculate_simulation(result, 10001).warnings
    negative = calculate_simulation(result, 20001)
    assert negative.remaining_after_proposal_minor == -1
    assert negative.warnings == [
        "pending_review_items",
        "negative_remaining",
        "low_buffer",
        "incomplete_coverage",
    ]


@pytest.mark.parametrize("amount", [0, -1, True, 5.5, "500", 10**14 + 1])
def test_simulation_rejects_nonpositive_or_noninteger_paise(amount):
    with pytest.raises(ValueError):
        calculate_simulation(summary(), amount)
    with pytest.raises(ValueError):
        simulate_monthly_commitment(
            MagicMock(spec=Session), user_id=uuid4(), monthly_amount_minor=amount, label="SIP"
        )


def test_filtered_query_is_scoped_parameterized_stable_and_escapes_wildcards(monkeypatch):
    from finboy.services.money import engine

    monkeypatch.setattr(engine, "today_ist", lambda: TODAY)
    session = MagicMock(spec=Session)
    session.scalars.return_value = []
    user = uuid4()
    assert (
        find_transactions(
            session,
            user_id=user,
            period=PeriodSpec(),
            merchant="%_shop",
            category="food_dining",
            status="confirmed",
            limit=12,
        )
        == []
    )
    compiled = session.scalars.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "transactions.user_id =" in str(compiled)
    assert "ORDER BY transactions.occurred_at DESC, transactions.id" in str(compiled)
    assert user in compiled.params.values() and "/%/_shop" in compiled.params.values()
    assert "food_dining" not in str(compiled)


@pytest.mark.parametrize(
    "filters",
    [
        {"limit": 0},
        {"limit": 201},
        {"limit": True},
        {"category": "bogus"},
        {"status": "bogus"},
        {"merchant": " "},
        {"merchant": "x" * 161},
    ],
)
def test_service_rejects_invalid_filters_before_querying(filters):
    session = MagicMock(spec=Session)
    with pytest.raises(ValueError):
        find_transactions(session, user_id=uuid4(), period=PeriodSpec(), **filters)
    session.scalars.assert_not_called()
