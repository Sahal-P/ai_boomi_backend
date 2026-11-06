"""Advisor tools: periods worked out in code, engine figures only, fixable errors."""

import json
from datetime import date

import pytest
from finboy.services.advisor import tools
from finboy.services.advisor.tools import ToolError, ToolPeriod, to_spec
from finboy.services.money.engine import PeriodSpec

from .support import FixtureToolbox

TODAY = date(2026, 11, 7)  # a Saturday


def period(kind: str, **values) -> ToolPeriod:
    fields = {"year": None, "month": None, "start_date": None, "end_date": None, "months": None}
    return ToolPeriod(kind=kind, **(fields | values))


def run(name: str, arguments: dict, said: set[int] | None = None) -> dict:
    result = tools.run(FixtureToolbox(), name, json.dumps(arguments), TODAY, said or set())
    return json.loads(result.output)


def whole(kind: str, **values) -> dict:
    return period(kind, **values).model_dump()


@pytest.mark.parametrize(
    ("kind", "values", "expected"),
    [
        ("today", {}, PeriodSpec(kind="range", start_date=TODAY, end_date=TODAY)),
        (
            "yesterday",
            {},
            PeriodSpec(kind="range", start_date=date(2026, 11, 6), end_date=date(2026, 11, 6)),
        ),
        (
            "this_week",
            {},
            PeriodSpec(kind="range", start_date=date(2026, 11, 2), end_date=TODAY),
        ),
        (
            "last_week",
            {},
            PeriodSpec(kind="range", start_date=date(2026, 10, 26), end_date=date(2026, 11, 1)),
        ),
        ("this_month", {}, PeriodSpec()),
        ("last_month", {}, PeriodSpec(kind="month", year=2026, month=10)),
        ("month", {"year": 2026, "month": 11}, PeriodSpec()),
        ("month", {"year": 2025, "month": 12}, PeriodSpec(kind="month", year=2025, month=12)),
        (
            "last_n_months",
            {"months": 3},
            PeriodSpec(kind="range", start_date=date(2026, 9, 1), end_date=TODAY),
        ),
        (
            "range",
            {"start_date": "2026-01-01", "end_date": "2026-03-31"},
            PeriodSpec(kind="range", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)),
        ),
    ],
)
def test_code_works_out_the_dates(kind, values, expected) -> None:
    assert to_spec(period(kind, **values), TODAY) == expected


@pytest.mark.parametrize(
    ("kind", "values"),
    [
        ("month", {"year": 2026, "month": 12}),
        ("month", {"year": None, "month": 3}),
        ("range", {"start_date": "2026-03-01", "end_date": "2026-01-01"}),
        ("range", {"start_date": "yesterday", "end_date": "2026-01-01"}),
        ("last_n_months", {"months": 1}),
        ("last_n_months", {"months": 24}),
    ],
)
def test_a_period_the_engine_cannot_read_is_an_error_the_model_can_fix(kind, values) -> None:
    with pytest.raises(ToolError):
        to_spec(period(kind, **values), TODAY)


def test_summary_quotes_formatted_engine_figures() -> None:
    found = run("money_summary", {"period": whole("this_month")})
    assert found["money_out"] == "₹18,420.50"
    assert found["entries_waiting_for_review"] == 1
    assert found["spending_by_category"][0] == {
        "category": "food_dining",
        "amount": "₹4,200",
        "payments": 6,
    }


def test_payments_to_a_payee_are_listed_and_totalled_by_code() -> None:
    result = tools.run(
        FixtureToolbox(),
        "find_payments",
        json.dumps(
            {
                "period": whole("this_month"),
                "payee": "swiggy",
                "category": None,
                "direction": "out",
                "limit": 1,
            }
        ),
        TODAY,
        set(),
    )
    found = json.loads(result.output)
    assert (found["payments_found"], found["total_paid"]) == (2, "₹770.50")
    assert len(found["listed"]) == 1 and len(result.evidence) == 1


def test_a_change_between_periods_is_computed_by_code() -> None:
    found = run(
        "compare",
        {
            "metric": "category",
            "category": "food_dining",
            "first": whole("last_month"),
            "second": whole("this_month"),
        },
    )
    assert (found["first_amount"], found["second_amount"]) == ("₹3,000", "₹4,200")
    assert (found["change"], found["percent_change"]) == ("up ₹1,200", "40.0%")


def test_an_unknown_category_or_tool_or_argument_comes_back_as_an_error() -> None:
    assert "error" in run("category_spending", {"period": whole("today"), "category": "pizza"})
    assert "error" in run("make_payment", {})
    assert "error" in run("money_summary", {"period": {"kind": "fortnight"}})


def test_affordability_uses_only_an_amount_the_person_said() -> None:
    guessed = run("afford_monthly", {"monthly_rupees": 5000})
    assert "error" in guessed
    said = run("afford_monthly", {"monthly_rupees": 5000}, said={500000})
    assert said["proposed_monthly"] == "₹5,000"
    assert "left_after_proposal" in said


def test_budgets_show_what_is_left() -> None:
    found = run("budgets_and_goal", {"period": None})
    assert found["budgets"][0]["left"] == "₹800" and found["budgets"][0]["level"] == "near"
    assert found["savings_goal_per_month"] == "₹5,000"


def test_every_tool_has_a_strict_schema() -> None:
    definitions = tools.definitions()
    assert [item["function"]["name"] for item in definitions] == [t.name for t in tools.TOOLS]
    for item in definitions:
        assert item["function"]["strict"] is True
        assert item["function"]["parameters"]["additionalProperties"] is False
