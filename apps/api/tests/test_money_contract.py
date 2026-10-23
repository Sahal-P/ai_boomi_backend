import pytest
from finboy.services.money.engine import PeriodSpec
from pydantic import ValidationError


def test_period_contract_defaults_to_current_month() -> None:
    assert PeriodSpec().kind == "current_month"
    assert PeriodSpec(kind="month", year=2026, month=10).month == 10


@pytest.mark.parametrize(
    "values",
    [
        {"kind": "month"},
        {"kind": "month", "year": 2026, "month": 13},
        {"kind": "current_month", "month": 10},
        {"kind": "month", "year": 0, "month": 1},
    ],
)
def test_period_contract_rejects_incomplete_or_invalid_month(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PeriodSpec.model_validate(values)
