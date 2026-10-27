"""Login codes, browser labels and English amounts: pure functions, no database."""

import re

import pytest
from finboy.services.accounts.login import ALPHABET, device_label, new_code, read_code
from finboy.services.ingestion.hindi_numbers import parse_amount


def test_codes_are_eight_unambiguous_characters() -> None:
    codes = {new_code() for _ in range(200)}
    assert len(codes) == 200
    assert all(re.fullmatch(rf"[{ALPHABET}]{{4}}-[{ALPHABET}]{{4}}", code) for code in codes)
    assert not set("01IO") & set(ALPHABET)


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("FinBoy login code K7Q2-9FXM", "K7Q2-9FXM"),
        ("finboy login code k7q2-9fxm", "K7Q2-9FXM"),
        ("K7Q2 9FXM", "K7Q2-9FXM"),
        ("K7Q29FXM", "K7Q2-9FXM"),
        ("Code: K7Q2-9FXM.", "K7Q2-9FXM"),
        ("FinBoy लॉगिन कोड K7Q2-9FXM", "K7Q2-9FXM"),
        ("Paid the milkman 500", None),
        ("K7Q2-9FX", None),  # too short
        ("K7Q0-9FXM", None),  # 0 is never used
        ("please send K7Q2-9FXM to my friend", None),  # a code inside a sentence is not a login
        ("", None),
        (None, None),
    ],
)
def test_only_a_whole_login_message_is_read_as_a_code(text, code) -> None:
    assert read_code(text) == code


def test_browser_labels_are_coarse_and_short() -> None:
    android = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/141.0 Mobile Safari/537.36"
    iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Version/18.0 Mobile Safari/604"
    assert device_label(android) == "Chrome · Android"
    assert device_label(iphone) == "Safari · iPhone"
    assert device_label("") == "a browser"
    assert len(device_label("x" * 5000)) <= 40


@pytest.mark.parametrize(
    ("text", "paise"),
    [
        ("Paid the milkman five hundred", 50_000),
        ("got two thousand five hundred from work", 250_000),
        ("two thousand and five hundred for rent", 250_000),
        ("spent twenty-five on tea", 2_500),
        ("twenty five rupees", 2_500),
        ("school fees 2.5k", 250_000),
        ("₹1,250 for medicine", 125_000),
        ("one lakh twenty thousand", 12_000_000),
        ("paanch sau diye", 50_000),  # Hinglish still works
        ("ढाई हज़ार", 250_000),  # and Hindi
        ("ok thanks", None),
        ("k", None),  # a stray letter is not ₹1,000
        ("500 and 300", None),  # two amounts: ask, never guess
        ("I gave one book", None),  # a lone small word is not money
    ],
)
def test_english_amounts_are_read_deterministically(text, paise) -> None:
    assert parse_amount(text) == paise
