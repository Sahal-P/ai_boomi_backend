"""The date reader: how people write dates in English, Hindi and Malayalam (docs/whatsapp.md)."""

from datetime import date

import pytest
from finboy.services.ingestion.dates import read_date, strip
from finboy.services.ingestion.hindi_numbers import parse_amount

TODAY = date(2026, 11, 22)  # a Sunday


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # The incident: the month was dropped and the next 1st (1 December) was used.
        ("264.51 to pay later on january 1", date(2027, 1, 1)),
        ("jan 1st", date(2027, 1, 1)),
        ("1st of Jan", date(2027, 1, 1)),
        ("Jan 1, 2027", date(2027, 1, 1)),
        ("january the 1st", date(2027, 1, 1)),
        ("first of january", date(2027, 1, 1)),
        ("janurary 5", date(2027, 1, 5)),  # a one-letter typo
        ("01/01", date(2027, 1, 1)),
        ("1/1/27", date(2027, 1, 1)),
        ("1-1-2027", date(2027, 1, 1)),
        ("1.1.2027", date(2027, 1, 1)),
        ("2027-01-01", date(2027, 1, 1)),
        ("1 जनवरी को 500 देना है", date(2027, 1, 1)),
        ("जनवरी 1 को", date(2027, 1, 1)),
        ("1 janvari", date(2027, 1, 1)),
        ("१ जनवरी", date(2027, 1, 1)),
        ("ജനുവരി 1ന് 500 അടയ്ക്കണം", date(2027, 1, 1)),
        ("ജനുവരി ഒന്നിന്", date(2027, 1, 1)),
        ("rent 5000 due 10 jan 2027", date(2027, 1, 10)),
        ("pay on 5 march", date(2027, 3, 5)),
        # A day of the month alone keeps the village rule: the next one.
        ("on the 20th", date(2026, 12, 20)),
        ("10 तारीख 1200 किस्त", date(2026, 12, 10)),
        ("हर महीने 10 तारीख", date(2026, 12, 10)),
        ("पहली तारीख", date(2026, 12, 1)),
        ("ഒന്നാം തീയതി", date(2026, 12, 1)),
        ("pay 500 on 5th", date(2026, 12, 5)),
        ("on the 22nd", TODAY),
        # Relative words look forward for a due: Hindi कल is tomorrow here.
        ("tomorrow", date(2026, 11, 23)),
        ("कल 500 देना है", date(2026, 11, 23)),
        ("kal 300 dena", date(2026, 11, 23)),
        ("parso", date(2026, 11, 24)),
        ("നാളെ", date(2026, 11, 23)),
        ("today", TODAY),
        ("in 10 days", date(2026, 12, 2)),
        ("next friday", date(2026, 11, 27)),
        ("on friday", date(2026, 11, 27)),
        ("month end", date(2026, 11, 30)),
        ("next month 5th", date(2026, 12, 5)),
        ("अगले महीने 5 तारीख", date(2026, 12, 5)),
        # A named date that passed this month is overdue, not next year.
        ("20 Nov", date(2026, 11, 20)),
        ("20 Oct", date(2027, 10, 20)),
    ],
)
def test_due_dates(text: str, expected: date) -> None:
    assert read_date(text, TODAY, "future").day == expected


@pytest.mark.parametrize(
    ("text", "problem", "month"),
    [
        ("in January", "month_only", 1),
        ("next month", "month_only", 12),
        ("any payment for jan 2027", "month_only", 1),
        ("31 Feb", "invalid", 2),
        ("30/02", "invalid", 2),  # day first, as in India: 30 February doesn't exist
        ("5 jan or 10 jan", "ambiguous", None),
        ("next week", "ambiguous", None),
        ("1 jan 2029", "out_of_range", None),
    ],
)
def test_due_dates_that_need_asking(text: str, problem: str | None, month: int | None) -> None:
    said = read_date(text, TODAY, "future")
    assert said.day is None and said.problem == problem and said.month == month


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("paid 500 on january 1", date(2026, 1, 1)),
        ("1st jan", date(2026, 1, 1)),
        ("1 जनवरी", date(2026, 1, 1)),
        ("ജനുവരി 1", date(2026, 1, 1)),
        ("01/01", date(2026, 1, 1)),
        ("28-10-26", date(2026, 10, 28)),
        ("yesterday", date(2026, 11, 21)),
        ("कल", date(2026, 11, 21)),
        ("ഇന്നലെ 200", date(2026, 11, 21)),
        ("parso", date(2026, 11, 20)),
        ("last monday", date(2026, 11, 16)),
        ("3 days ago", date(2026, 11, 19)),
        ("on the 15th", date(2026, 11, 15)),
        ("25 nov", date(2025, 11, 25)),
        ("paid 300 today", TODAY),
    ],
)
def test_payment_dates_look_back(text: str, expected: date) -> None:
    assert read_date(text, TODAY, "past").day == expected


@pytest.mark.parametrize(
    "text",
    ["may I pay 500", "jan dhan 500", "march on", "chai 20", "500 later", "12.10", "ചായ 20ന്"],
)
def test_everyday_words_and_prices_are_not_dates(text: str) -> None:
    assert not read_date(text, TODAY, "future").said


@pytest.mark.parametrize(
    ("text", "amount"),
    [
        ("264.51 to pay later on january 1", 26451),
        ("the date is january 1", None),  # was ₹1
        ("Any payment for jan 2027", None),  # was ₹2,027
        ("1 jan", None),
        ("pay 500 on 5th", 50000),  # was no amount: two numbers
        ("1 जनवरी को 500 देना है", 50000),
        ("ജനുവരി 1ന് 500 അടയ്ക്കണം", 50000),
        ("10 तारीख 1200 किस्त", 120000),
        ("ചായ 20ന്", 2000),
    ],
)
def test_an_amount_is_never_read_from_a_date(text: str, amount: int | None) -> None:
    for direction in ("future", "past"):
        said = read_date(text, TODAY, direction)
        assert parse_amount(strip(text, said.spans)) == amount


@pytest.mark.parametrize(
    ("today", "text", "expected"),
    [
        (date(2027, 1, 31), "28 feb", date(2027, 2, 28)),
        (date(2027, 1, 31), "on the 31st", date(2027, 1, 31)),
        (date(2027, 2, 1), "on the 30th", date(2027, 3, 30)),
        (date(2026, 12, 31), "jan 1", date(2027, 1, 1)),
        (date(2026, 12, 31), "tomorrow", date(2027, 1, 1)),
        (date(2028, 2, 29), "29 feb", date(2028, 2, 29)),
        (date(2027, 3, 1), "29 feb", date(2028, 2, 29)),
    ],
)
def test_month_and_year_edges(today: date, text: str, expected: date) -> None:
    assert read_date(text, today, "future").day == expected
