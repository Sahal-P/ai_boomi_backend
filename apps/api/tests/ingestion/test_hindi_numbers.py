import pytest
from finboy.services.ingestion.hindi_numbers import find_amounts, only_amount, parse_amount


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
        # Malayalam digits: Sarvam writes "₹500", people type 500 or ൫൦൦.
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
    ("spoken", "rupees"),
    [
        # What OpenAI speech-to-text wrote for a spoken "700 OpenAI credits" (20 Nov 2026).
        ("ഏഴുനൂറ് ഓപ്പണെയായി ക്രെഡിറ്റ്സ്.", 700),
        ("എഴുന്നൂറ് ഓപ്പണെയായി ക്രെഡിറ്റ്സ്.", 700),
        ("പാൽക്കാരന് അഞ്ഞൂറ് രൂപ കൊടുത്തു", 500),
        ("എഴുനൂറു രൂപ", 700),  # a final ു for ്
        ("അൻപത് രൂപ", 50),  # chillu spellings
        ("എൺപത് രൂപ", 80),
        ("നാൽപ്പത് രൂപ", 40),
        ("ഇരുപത്തഞ്ച് രൂപ", 25),  # tens and ones fused
        ("ഇരുപത്തിയഞ്ച് രൂപ", 25),
        ("ഇരുപത്തി അഞ്ച് രൂപ", 25),  # or said as two words
        ("നൂറ്റമ്പത്", 150),  # hundreds and the rest fused
        ("നൂറ്റിയമ്പത്", 150),
        ("നൂറ്റി അമ്പത്", 150),
        ("നൂറ്റിപ്പത്ത്", 110),
        ("നൂറ്റിരുപത്", 120),
        ("നൂറ്റിയിരുപത്തഞ്ച്", 125),
        ("എഴുന്നൂറ്റമ്പത്", 750),
        ("തൊള്ളായിരത്തി അമ്പത്", 950),
        ("ആയിരം", 1000),
        ("രണ്ട് ആയിരം", 2000),
        ("രണ്ടായിരം", 2000),
        ("മൂവായിരം", 3000),
        ("അയ്യായിരം", 5000),
        ("എണ്ണായിരം", 8000),
        ("ഒമ്പതിനായിരം", 9000),
        ("പതിനായിരം", 10000),
        ("പതിനയ്യായിരം", 15000),
        ("ഇരുപതിനായിരം", 20000),
        ("ഇരുപത്തയ്യായിരം", 25000),
        ("തൊണ്ണൂറായിരം", 90000),
        ("ആയിരത്തഞ്ഞൂറ്", 1500),
        ("ആയിരത്തി അഞ്ഞൂറ്", 1500),
        ("രണ്ടായിരത്തഞ്ഞൂറ്", 2500),
        ("ആയിരത്തിയൊന്ന്", 1001),
        ("ഒരു ലക്ഷം", 100000),
        ("ഒന്നര ലക്ഷം", 150000),
        ("രണ്ടര ലക്ഷം", 250000),
        ("ഒരു ലക്ഷത്തി ഇരുപത്തയ്യായിരം", 125000),
        ("എഴുനൂറിന് പെട്രോൾ അടിച്ചു", 700),  # case endings
        ("ആയിരത്തിന്റെ ബിൽ", 1000),
        ("നൂറോളം", 100),
    ],
)
def test_malayalam_number_words(spoken: str, rupees: int) -> None:
    assert parse_amount(spoken) == rupees * 100


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
        "അഞ്ച് പേർ വന്നു",  # a lone small number with no rupees named
        "ഒന്ന് നോക്കൂ",
        "അഞ്ഞൂറോ അറുനൂറോ",  # "500 or 600"
        "ആയിരിക്കും",  # "will be": starts like ആയിരം but is not a number
        "നൂറ്റാണ്ട്",  # "century"
        "ആറ്റിൽ",  # "in the river"
    ],
)
def test_ambiguous_or_absent_amounts_are_never_guessed(spoken: str) -> None:
    assert parse_amount(spoken) is None


def test_an_article_next_to_a_real_amount_is_ignored() -> None:
    assert find_amounts("एक दुकान पर 500 रुपये दिए") == [50000]
    assert find_amounts("ഒരു ചായ 20") == [2000]


@pytest.mark.parametrize(
    ("reply", "rupees"),
    [
        ("700", 700),
        ("₹700", 700),
        ("Rs. 700/-", 700),
        ("700 only", 700),
        ("seven hundred", 700),
        ("सिर्फ़ 700", 700),
        ("पचास", 50),  # a lone number word answers "how many rupees?"
        ("എഴുനൂറ്", 700),
        ("അമ്പത്", 50),
        ("അഞ്ഞൂറ് രൂപ മാത്രം", 500),
        ("700 for petrol", None),  # more than an amount: read as a new message
        ("OpenAI credits", None),
        ("500 600", None),
        ("डेढ़", None),
        ("ഒന്നര", None),
        ("", None),
    ],
)
def test_only_an_amount_answers_how_many_rupees(reply: str, rupees: int | None) -> None:
    assert only_amount(reply) == (rupees * 100 if rupees else None)
