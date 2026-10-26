from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.services.ingestion.normalize import normalize
from finboy.services.ingestion.rules import extract_rules
from finboy.services.whatsapp import statement
from finboy.services.whatsapp.statement import Statement, StatementReading

TODAY = date(2026, 10, 26)


def reading(**overrides) -> StatementReading:
    values = {
        "type": "spent",
        "amount_phrase": "पाँच सौ",
        "counterparty": "दूधवाले",
        "mode": "cash",
        "day_phrase": None,
        "category": "groceries",
        "due_day": None,
        "due_label": None,
    }
    return StatementReading(**{**values, **overrides})


def test_phrases_count_only_when_they_are_really_in_the_message() -> None:
    text = "दूधवाले को पाँच सौ नकद दिए"
    grounded = statement._ground(reading(), text, TODAY)
    assert grounded == Statement("spent", 50000, "दूधवाले", "cash", TODAY, "groceries", None, None)
    invented = statement._ground(
        reading(amount_phrase="सात सौ", counterparty="राम"), "दूधवाले को पाँच सौ दिए", TODAY
    )
    # An invented phrase is dropped; the one amount actually said is used, the name is not.
    assert invented.amount_minor == 50000 and invented.counterparty is None


def test_no_amount_is_guessed() -> None:
    grounded = statement._ground(reading(amount_phrase=None), "दूधवाले को पैसे दिए", TODAY)
    assert grounded.amount_minor is None


def test_names_never_carry_amounts() -> None:
    grounded = statement._ground(reading(counterparty="500 दूधवाले"), "500 दूधवाले को दिए", TODAY)
    assert grounded.counterparty is None


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("आज", TODAY),
        ("कल", date(2026, 10, 25)),
        ("परसों", date(2026, 10, 24)),
        ("10 तारीख", date(2026, 10, 10)),
        ("28 तारीख", date(2026, 9, 28)),  # never in the future: last month
        (None, TODAY),
    ],
)
def test_when_money_moved(phrase: str | None, expected: date) -> None:
    text = f"दूधवाले को 500 दिए {phrase or ''}"
    grounded = statement._ground(reading(day_phrase=phrase, amount_phrase="500"), text, TODAY)
    assert grounded.day == expected


def test_dues_get_their_next_date_only_when_a_day_is_said() -> None:
    due = reading(
        type="due",
        amount_phrase="1200",
        counterparty=None,
        category="loan_emi",
        due_day=10,
        due_label="समूह की किस्त",
    )
    text = "समूह की किस्त 1200, हर महीने 10 तारीख"
    grounded = statement._ground(due, text, TODAY)
    assert grounded.kind == "due" and grounded.amount_minor == 120000
    assert grounded.due_date == date(2026, 11, 10) and grounded.label == "समूह की किस्त"
    unsaid = statement._ground(due.model_copy(update={"due_day": 31}), "समूह की किस्त 1200", TODAY)
    assert unsaid.due_date is None, "a model-supplied day that was never said is dropped"


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("इस हफ़्ते कितना खर्च हुआ?", "question"),
        ("कितना खर्च हुआ", "question"),
        ("दूधवाले को 500 दिए", "spent"),
        ("PM किसान के 2000 आए", "received"),
        ("समूह की किस्त 1200 देना है 10 तारीख", "due"),
        ("नमस्ते", "unclear"),
    ],
)
def test_rules_fallback_without_a_model(text: str, kind: str) -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        cors_origins=["http://localhost:3000"],
        environment="test",
    )
    assert statement.read_statement(text, settings, TODAY).kind == kind


def test_production_without_a_model_fails_closed() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        cors_origins=["http://localhost:3000"],
        environment="test",
    ).model_copy(update={"environment": "production"})
    with pytest.raises(ProviderUnavailable):
        statement.read_statement("दूधवाले को 500 दिए", settings, TODAY)


def test_the_model_only_classifies_and_copies(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    class Client:
        def __init__(self, **_kwargs):
            self.responses = SimpleNamespace(parse=self.parse)

        def parse(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(output_parsed=reading())

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(statement, "OpenAI", Client)
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        cors_origins=["http://localhost:3000"],
        environment="test",
        openai_api_key="synthetic-key",
        openai_assistant_model="synthetic-model",
    )
    result = statement.read_statement("दूधवाले को पाँच सौ नकद दिए", settings, TODAY)
    assert result.amount_minor == 50000 and result.counterparty == "दूधवाले"
    assert seen["store"] is False and seen["text_format"] is StatementReading
    assert "UNTRUSTED" in seen["input"][0]["content"]


def test_payment_lines_are_read_by_the_existing_rules_extractor() -> None:
    received = datetime(2026, 10, 26, 6, 15, tzinfo=UTC)  # 11:45 IST
    spent = Statement("spent", 50000, "दूधवाले", "cash", TODAY, "groceries")
    line = statement.payment_line(spent, received)
    assert line == "Rs. 500.00 paid to दूधवाले via cash on 26-10-26 11:45"
    event = extract_rules(normalize(statement.as_message(line, received), received)).events[0]
    assert (event.event_type, event.amount_minor, event.merchant) == ("debit", 50000, "दूधवाले")
    got = Statement("received", 200000, "PM किसान", "upi", date(2026, 10, 25), "govt_benefit")
    line = statement.payment_line(got, received)
    assert line == "Rs. 2000.00 credited from PM किसान via UPI on 25-10-26"
    event = extract_rules(normalize(statement.as_message(line, received), received)).events[0]
    assert (event.event_type, event.amount_minor, event.merchant) == ("credit", 200000, "PM किसान")
