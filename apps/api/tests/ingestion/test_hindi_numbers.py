import pytest
from finboy.services.ingestion.hindi_numbers import find_amounts, parse_amount


@pytest.mark.parametrize(
    ("spoken", "rupees"),
    [
        ("500", 500),
        ("₹500", 500),
        ("Rs. 1,200", 1200),
        ("1,25,000 रुपये", 125000),
        ("५००", 500),
        ("500रुपये", 500),
        ("500.50", 500.50),
        ("पाँच सौ", 500),
        ("पांच सौ", 500),
        ("बारह सौ", 1200),
        ("डेढ़ सौ", 150),
        ("डेढ सौ", 150),
        ("ढाई हज़ार", 2500),
        ("ढाई हजार", 2500),
        ("सवा लाख", 125000),
        ("सवा सौ", 125),
        ("साढ़े तीन सौ", 350),
        ("पौने दो सौ", 175),
        ("दो हज़ार पाँच सौ", 2500),
        ("दो सौ पचास", 250),
        ("एक लाख बीस हज़ार", 120000),
        ("1 लाख 20 हज़ार", 120000),
        ("1.5 लाख", 150000),
        ("5 हज़ार", 5000),
        ("बीस रुपये", 20),
        ("निन्यानवे रुपये", 99),
        ("paanch sau", 500),
        ("teen hazar", 3000),
        ("dedh sau", 150),
        ("sawa lakh", 125000),
        ("दूधवाले को पाँच सौ दिए", 500),
        ("PM किसान के 2000 आए", 2000),
        # Malayalam arrives as digits: Sarvam writes "₹500", people type 500 or ൫൦൦.
        ("പാൽക്കാരന് ₹500 കൊടുത്തു.", 500),
        ("ശമ്പളം ₹25000 കിട്ടി", 25000),
        ("൫൦൦ രൂപ", 500),
        ("1,200 രൂപയ്ക്ക്", 1200),
        ("നമസ്കാരം ₹7860.", 7860),
    ],
)
def test_spoken_amounts(spoken: str, rupees: float) -> None:
    assert parse_amount(spoken) == round(rupees * 100)


@pytest.mark.parametrize(
    "spoken",
    [
        "",
        "कुछ पैसे दिए",
        "डेढ़",  # a bare fraction is not an amount
        "साढ़े तीन",
        "500 600",  # two numbers side by side
        "500 या 600 रुपये",  # two separate amounts
        "एक दुकान से सामान लिया",  # "एक" as an article, no rupees named
        "दो करोड़ करोड़",
        "बीस करोड़",  # above the one-crore ceiling: treated as misheard
        "0",
        "പാൽക്കാരന് അഞ്ഞൂറ് രൂപ കൊടുത്തു",  # Malayalam number words are not read this round
    ],
)
def test_ambiguous_or_absent_amounts_are_never_guessed(spoken: str) -> None:
    assert parse_amount(spoken) is None


def test_an_article_next_to_a_real_amount_is_ignored() -> None:
    assert find_amounts("एक दुकान पर 500 रुपये दिए") == [50000]
