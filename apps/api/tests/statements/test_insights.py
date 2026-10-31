"""Reports beyond categories, computed from confirmed records alone."""

from datetime import date, datetime
from uuid import uuid4

from finboy.core.clock import IST
from finboy.services.money.insights import (
    Entry,
    insights,
    months_between,
    next_month,
    people,
    regular_payments,
)


def entry(
    name: str,
    rupees: float,
    day: date,
    *,
    direction: str = "out",
    kind: str | None = None,
    category: str = "other",
) -> Entry:
    return Entry(
        id=uuid4(),
        direction=direction,
        kind=kind or ("purchase" if direction == "out" else "income_other"),
        name=name,
        category=category,
        amount_minor=round(rupees * 100),
        occurred_at=datetime(day.year, day.month, day.day, 12, tzinfo=IST),
    )


def test_month_arithmetic() -> None:
    assert months_between(date(2026, 4, 1), date(2026, 9, 30)) == 6
    assert months_between(date(2025, 11, 1), date(2026, 2, 28)) == 4
    assert next_month(date(2026, 1, 31)) == date(2026, 2, 28)
    assert next_month(date(2026, 12, 15)) == date(2027, 1, 15)


def test_steady_bills_are_regular_and_daily_shops_are_not() -> None:
    broadband = [
        entry("Sample Broadband", 749.50, date(2026, month, 5), category="utilities")
        for month in (6, 7, 8, 9)
    ]
    # A card bill varies a little from month to month.
    card = [
        entry("Sample Card", amount, date(2026, month, 20))
        for month, amount in ((5, 4810), (7, 4830), (8, 4865))
    ]
    tea = [
        entry("Corner Tea", 12, date(2026, month, day))
        for month in (4, 5, 6, 7, 8, 9)
        for day in (2, 9, 16, 23)
    ]
    rare = [entry("Rare Shop", 300, date(2026, month, 1)) for month in (8, 9)]
    found = regular_payments([*broadband, *card, *tea, *rare], end=date(2026, 9, 30))
    assert [(item.name, item.usual_minor, item.months) for item in found] == [
        ("Sample Card", 483000, 3),
        ("Sample Broadband", 74950, 4),
    ]
    assert found[1].last_paid == date(2026, 9, 5) and found[1].next_expected == date(2026, 10, 5)
    assert found[1].category == "utilities"


def test_regular_payments_only_look_at_the_six_months_ending_with_the_period() -> None:
    old = [entry("Old Gym", 999, date(2026, month, 3)) for month in (1, 2, 3)]
    assert regular_payments(old, end=date(2026, 9, 30)) == []
    assert [item.name for item in regular_payments(old, end=date(2026, 4, 30))] == ["Old Gym"]


def test_a_regular_payment_that_stopped_is_left_out() -> None:
    gym = [entry("Sample Gym", 999, date(2026, month, 3)) for month in (4, 5, 6)]
    phone = [entry("Sample Telecom", 399, date(2026, month, 25)) for month in (6, 7, 8, 9)]
    # Records go on into September; the gym's July payment never came.
    assert [item.name for item in regular_payments([*gym, *phone], end=date(2026, 9, 30))] == [
        "Sample Telecom"
    ]
    # With nothing recorded after June yet, the gym is not judged to have stopped.
    assert [item.name for item in regular_payments(gym, end=date(2026, 9, 30))] == ["Sample Gym"]
    # Ten days' grace: paid June to August, the next is due 25 September.
    on_time = entry("Corner Tea", 12, date(2026, 10, 4))
    late = entry("Corner Tea", 12, date(2026, 10, 6))
    october = date(2026, 10, 31)
    assert [item.name for item in regular_payments([*phone[:3], on_time], end=october)] == [
        "Sample Telecom"
    ]
    assert regular_payments([*phone[:3], late], end=october) == []


def test_money_with_people_groups_names_and_shows_the_balance() -> None:
    entries = [
        entry("Ravi Kumar", 12400, date(2026, 5, 1)),
        entry("RAVI  KUMAR", 12320, date(2026, 5, 9), direction="in"),
        entry("Asha Stores", 500, date(2026, 5, 2)),
        entry("Salary Co", 50000, date(2026, 5, 1), direction="in", kind="salary"),
    ]
    found = people(entries)
    assert len(found) == 1
    assert (found[0].sent_minor, found[0].received_minor, found[0].balance_minor) == (
        1240000,
        1232000,
        -8000,
    )
    assert found[0].count == 2 and found[0].last_on == date(2026, 5, 9)


def test_names_printed_with_and_without_spaces_are_one_payee() -> None:
    entries = [
        entry("Ravi K M", 500, date(2026, 5, 1)),
        entry("RaviKM", 300, date(2026, 5, 9), direction="in"),
        entry("RaviKM", 200, date(2026, 6, 9), direction="in"),
    ]
    (person,) = people(entries)
    # Shown in its most common spelling.
    assert (person.name, person.sent_minor, person.received_minor) == ("RaviKM", 50000, 50000)


def test_the_period_summary_counts_spending_shares_and_small_payments() -> None:
    entries = [
        entry("Asha Stores", 150, date(2026, 4, 3)),
        entry("Asha Stores", 50, date(2026, 5, 3)),
        entry("ASHA STORES", 80, date(2026, 6, 3)),
        entry("Big Electronics", 9720, date(2026, 6, 9), category="shopping"),
        entry("Ravi Kumar", 2000, date(2026, 5, 4), direction="in"),
        entry("Own Account", 5000, date(2026, 5, 5), kind="transfer"),
    ]
    result = insights(entries, entries, start=date(2026, 4, 1), end=date(2026, 6, 30))
    assert (result.months, result.payment_count, result.money_out_minor, result.money_in_minor) == (
        3,
        4,
        1000000,
        200000,
    )
    assert [(item.name, item.count, item.share) for item in result.top_payees] == [
        ("Big Electronics", 1, 0.972),
        ("Asha Stores", 3, 0.028),
    ]
    assert [item.name for item in result.biggest] == [
        "Big Electronics",
        "Asha Stores",
        "ASHA STORES",
        "Asha Stores",
    ]
    small = result.small
    assert (small.count, small.amount_minor, small.per_month_minor) == (3, 28000, 9333)
    assert (small.count_share, small.amount_share) == (0.75, 0.028)
    assert [(place.name, place.count) for place in small.places] == [("Asha Stores", 3)]
    assert result.top_senders[0].name == "Ravi Kumar" and result.people == []


def test_an_empty_period_has_empty_sections() -> None:
    result = insights([], [], start=date(2026, 10, 1), end=date(2026, 10, 31))
    assert result.top_payees == [] and result.regular == [] and result.people == []
    assert (result.small.count, result.small.count_share, result.regular_monthly_minor) == (
        0,
        0.0,
        0,
    )
