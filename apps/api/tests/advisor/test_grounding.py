"""Figures in a reply must be FinBoy's own numbers."""

from decimal import Decimal

from finboy.services.advisor import grounding


def test_indian_formats_scale_words_and_native_digits_are_the_same_figure() -> None:
    sources = grounding.allowed(['{"money_out":"₹1,20,000","share":"12.5%"}'])
    for reply in (
        "You spent ₹1,20,000.",
        "You spent 120000 rupees.",
        "You spent 1.2 lakh.",
        "आपने ₹१,२०,००० खर्च किए।",
        "That is 12.5% of it",
        "That is about 13%",
    ):
        assert grounding.unchecked([reply], sources) == [], reply


def test_an_invented_amount_or_percentage_is_caught() -> None:
    sources = grounding.allowed(["₹4,200"])
    assert grounding.unchecked(["You could save ₹1,500 a month."], sources) == ["1500"]
    assert grounding.unchecked(["That is 30% more."], sources) == ["30"]
    assert grounding.unchecked(["About ₹50 a day."], sources) == ["50"]


def test_small_plain_numbers_and_list_items_need_no_source() -> None:
    reply = "Three ideas:\n1. Cook at home 2 days a week\n2. Pause 1 subscription"
    assert grounding.unchecked([reply], set()) == []


def test_large_plain_numbers_are_checked_and_dates_come_from_sources() -> None:
    sources = grounding.allowed(["Today in India: 2026-11-07"])
    assert grounding.unchecked(["Since 2026-11-07, all good"], sources) == []
    assert grounding.unchecked(["You made 450 payments"], sources) == ["450"]


def test_figures_reads_values_and_money_hints() -> None:
    assert grounding.figures("₹4,215.50 and 3 items") == [
        (Decimal("4215.50"), True),
        (Decimal("3"), False),
    ]


def test_rupees_and_paise_said_out_loud_are_one_amount() -> None:
    """A spoken reply says ₹770.50 as "770 rupees and 50 paise": the 50 is not an amount."""
    sources = grounding.allowed(['{"total":"₹770.50"}'])
    for reply in (
        "You paid 770 rupees and 50 paise to Swiggy this month.",
        "You paid ₹770 and 50 paise.",
        "You paid Rs. 770, 50 paise.",
        "आपने स्विगी को 770 रुपये 50 पैसे दिए।",
        "आपने स्विगी को ७७० रुपये ५० पैसे दिए।",
        "സ്വിഗ്ഗിക്ക് 770 രൂപയും 50 പൈസയും നൽകി.",
        "Swiggy ko 770 rupaye aur 50 paise diye.",
    ):
        assert grounding.unchecked([reply], sources) == [], reply
    # The paise never let another amount through.
    assert grounding.unchecked(["About ₹50 a day."], sources) == ["50"]
    assert grounding.unchecked(["You paid 770 rupees and 60 paise."], sources) == ["770.60"]
    assert grounding.unchecked(["You paid 770 rupees and 5 paise."], sources) == ["770.05"]
