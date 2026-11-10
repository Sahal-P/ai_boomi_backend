"""Planning figures come from code, using only amounts the person gave or FinBoy showed."""

import json
from datetime import date

from finboy.services.advisor import grounding, tools

from .support import FixtureToolbox

TODAY = date(2026, 11, 7)
BLANK = {
    "calculation": None,
    "amount_rupees": None,
    "by_month": None,
    "months": None,
    "monthly_rupees": None,
    "annual_interest_percent": None,
}


def context(words: str, shown: str = "") -> tools.Context:
    numbers = {value for value, _ in grounding.figures(words)}
    return tools.Context(
        today=TODAY,
        said={int(value * 100) for value in numbers},
        stated=numbers,
        known=grounding.allowed([shown]),
    )


def plan(ctx: tools.Context, **values) -> dict:
    result = tools.run(FixtureToolbox(), "plan_numbers", json.dumps(BLANK | values), ctx)
    return json.loads(result.output)


def emi(principal: float, annual_percent: float, months: int) -> float:
    rate = annual_percent / 1200
    growth = (1 + rate) ** months
    return principal * rate * growth / (growth - 1)


def test_an_emi_comes_from_the_rate_they_gave() -> None:
    ctx = context("A loan of 1.5 lakh at 10.5% for 36 months")
    found = plan(
        ctx, calculation="emi", amount_rupees=150000, months=36, annual_interest_percent=10.5
    )
    assert round(emi(150000, 10.5, 36), 2) == 4875.37  # an independent float check
    assert found["emi"] == "₹4,876" and found["annual_rate"] == "10.5%"
    assert found["total_paid"] == "₹1,75,536" and found["total_interest"] == "₹25,536"


def test_a_rate_or_amount_nobody_gave_is_refused() -> None:
    ctx = context("A loan of 1.5 lakh for 36 months")
    no_rate = plan(ctx, calculation="emi", amount_rupees=150000, months=36)
    assert "ask the person for the rate" in no_rate["error"]
    guessed = plan(
        ctx, calculation="emi", amount_rupees=150000, months=36, annual_interest_percent=12
    )
    assert "interest rate the person gave" in guessed["error"]
    other = plan(
        ctx, calculation="emi", amount_rupees=200000, months=36, annual_interest_percent=12
    )
    assert "loan amount" in other["error"]
    long = plan(ctx, calculation="emi", amount_rupees=150000, months=600)
    assert "months" in long["error"]


def test_a_monthly_saving_for_a_target_by_a_month() -> None:
    ctx = context("I want ₹60,000 by March 2027")
    found = plan(ctx, calculation="save_per_month", amount_rupees=60000, by_month="2027-03")
    assert found == {
        "target": "₹60,000",
        "months_counted": 4,
        "from_month": "December 2026",
        "to_month": "March 2027",
        "save_each_month": "₹15,000",
    }
    past = plan(ctx, calculation="save_per_month", amount_rupees=60000, by_month="2026-11")
    assert "later month" in past["error"]
    for wrong in ("March", "2027-13", None):
        found = plan(ctx, calculation="save_per_month", amount_rupees=60000, by_month=wrong)
        assert "2027-03" in found["error"]


def test_months_to_a_goal_can_use_a_figure_finboy_showed() -> None:
    ctx = context("How long at 4,500 a month?", shown='{"goal":"₹50,000"}')
    found = plan(ctx, calculation="months_to_goal", amount_rupees=50000, monthly_rupees=4500)
    assert found == {"target": "₹50,000", "each_month": "₹4,500", "months_needed": 12}
    unknown = plan(ctx, calculation="months_to_goal", amount_rupees=80000, monthly_rupees=4500)
    assert "target" in unknown["error"]
