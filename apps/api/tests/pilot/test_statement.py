import threading
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.services.ingestion.normalize import normalize
from finboy.services.ingestion.rules import extract_rules
from finboy.services.triage.service import Sorted
from finboy.services.whatsapp import statement
from finboy.services.whatsapp.statement import Statement, StatementReading
from triage.support import choice, held, noul, triaged

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


@pytest.mark.parametrize(
    ("text", "kind", "amount", "day", "due"),
    [
        ("ഈ ആഴ്ച എത്ര ചെലവായി", "question", None, None, None),
        ("എത്ര രൂപ ബാക്കിയുണ്ട്", "question", None, None, None),
        ("എന്താണ് എന്റെ ചെലവ്?", "question", None, None, None),
        ("പാൽക്കാരന് 500 കൊടുത്തു", "spent", 50000, TODAY, None),
        ("ഇന്നലെ കറന്റ് ബില്ല് ൮൦൦ അടച്ചു", "spent", 80000, date(2026, 10, 25), None),
        ("ശമ്പളം ₹25,000 കിട്ടി.", "received", 2500000, TODAY, None),
        ("10-ാം തീയതി 1200 തവണ അടയ്ക്കണം", "due", 120000, None, date(2026, 11, 10)),
        ("10 तारीख को 1200 की किस्त देना है", "due", 120000, None, date(2026, 11, 10)),
        ("പാൽക്കാരന് അഞ്ഞൂറ് രൂപ കൊടുത്തു", "spent", None, TODAY, None),  # words: asked again
        ("നമസ്കാരം", "unclear", None, None, None),
    ],
)
def test_malayalam_rules_fallback_without_a_model(text, kind, amount, day, due) -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        cors_origins=["http://localhost:3000"],
        environment="test",
    )
    result = statement.read_statement(text, settings, TODAY)
    assert (result.kind, result.amount_minor, result.day, result.due_date) == (
        kind,
        amount,
        day,
        due,
    )


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("ഇന്ന്", TODAY),
        ("ഇന്നലെ", date(2026, 10, 25)),
        ("മിനിഞ്ഞാന്ന്", date(2026, 10, 24)),
        ("10-ാം തീയതി", date(2026, 10, 10)),
        ("28 തീയതി", date(2026, 9, 28)),  # never in the future: last month
    ],
)
def test_when_money_moved_in_malayalam(phrase: str, expected: date) -> None:
    text = f"പാൽക്കാരന് ₹500 കാശായി കൊടുത്തു, {phrase}"
    model = reading(amount_phrase="₹500", counterparty="പാൽക്കാരന്", day_phrase=phrase)
    grounded = statement._ground(model, text, TODAY)
    assert grounded == Statement("spent", 50000, "പാൽക്കാരന്", "cash", expected, "groceries")


def test_malayalam_names_and_dues_are_grounded() -> None:
    named = reading(amount_phrase="500", counterparty="500 രൂപ")
    assert statement._ground(named, "പാൽക്കാരന് 500 രൂപ കൊടുത്തു", TODAY).counterparty is None
    due = reading(
        type="due",
        amount_phrase="1200",
        counterparty=None,
        category="loan_emi",
        due_day=10,
        due_label="ലോൺ തവണ",
    )
    said = statement._ground(due, "ലോൺ തവണ 1200, എല്ലാ മാസവും പത്താം തീയതി", TODAY)
    assert (said.amount_minor, said.due_date, said.label) == (120000, date(2026, 11, 10), "ലോൺ തവണ")
    unsaid = statement._ground(due, "ലോൺ തവണ 1200 അടയ്ക്കണം", TODAY)
    assert unsaid.due_date is None, "a model-supplied day that was never said is dropped"
    assert "Malayalam" in statement.PROMPT and "കൊടുത്തു" in statement.PROMPT


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


def rules_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        cors_origins=["http://localhost:3000"],
        environment="test",
    )


def item(**overrides) -> dict:
    return {
        "type": "spent",
        "amount_phrase": None,
        "counterparty": None,
        "day_phrase": None,
        "category": None,
        **overrides,
    }


def test_several_payments_in_one_message_each_need_their_own_amount() -> None:
    text = "chai 20, auto 50, lunch 120, samosa"
    several = reading(
        amount_phrase="20",
        counterparty="chai",
        mode="unknown",
        category="food_dining",
        more=[
            item(amount_phrase="50", counterparty="auto", category="transport"),
            item(amount_phrase="120", counterparty="lunch", category="food_dining"),
            item(amount_phrase="30", counterparty="samosa"),  # never said: left out
        ],
    )
    result = statement._ground_all(several, text, TODAY)
    assert [(s.kind, s.amount_minor, s.counterparty, s.category) for s in result] == [
        ("spent", 2000, "chai", "food_dining"),
        ("spent", 5000, "auto", "transport"),
        ("spent", 12000, "lunch", "food_dining"),
    ]
    # With several items there is no whole-message fallback for an unsaid amount.
    nothing = reading(amount_phrase="99", more=[item(amount_phrase="88")])
    assert statement._ground_all(nothing, text, TODAY) == [Statement("spent")]
    # One payment still falls back to the one amount the message holds.
    (one,) = statement._ground_all(reading(amount_phrase="सात सौ"), "दूध 500", TODAY)
    assert one.amount_minor == 50000


def test_a_further_item_keeps_the_messages_day_unless_it_says_its_own() -> None:
    text = "कल चाय 20, परसों ऑटो 50"
    several = reading(
        amount_phrase="20",
        counterparty="चाय",
        day_phrase="कल",
        more=[
            item(amount_phrase="50", counterparty="ऑटो", day_phrase="परसों"),
            item(amount_phrase="20"),
        ],
    )
    days = [s.day for s in statement._ground_all(several, text, TODAY)]
    assert days == [date(2026, 10, 25), date(2026, 10, 24), date(2026, 10, 25)]


def test_bank_sms_numbers_are_masked_before_the_model_and_dates_are_read() -> None:
    sms = (
        "Rs.500.00 debited from A/c XX1234 on 25-10-26 to VPA 9876543210@ybl "
        "UPI Ref 412345678901. Not you? Call 18002586161"
    )
    masked = statement.mask(sms)
    for secret in ("1234", "9876543210", "412345678901", "18002586161"):
        assert secret not in masked
    assert "Rs.500.00" in masked and "25-10-26" in masked
    assert statement._past_day("25-10-26", masked, TODAY) == date(2026, 10, 25)
    assert statement._past_day("on 3 Oct", "paid on 3 Oct", TODAY) == date(2026, 10, 3)
    assert statement._past_day("28-10-26", "28-10-26", TODAY) == TODAY, "never in the future"


def test_a_bank_sms_question_mark_is_not_a_question() -> None:
    sms = "Rs.500.00 debited from A/c XX1234 on 25-10-26. Not you? Call 18002586161"
    (result,) = statement.read_statements(sms, rules_settings(), TODAY)
    assert (result.kind, result.amount_minor, result.day) == ("spent", 50000, date(2026, 10, 25))
    question = statement.read_statements("कितना खर्च हुआ?", rules_settings(), TODAY)
    assert question == [Statement("question")]


@pytest.mark.parametrize(
    ("text", "kind", "amount", "category", "overall"),
    [
        ("food budget 5000", "budget", 500000, "food_dining", False),
        ("खाने का बजट 5000", "budget", 500000, "food_dining", False),
        ("ഭക്ഷണം ബജറ്റ് 5000", "budget", 500000, "food_dining", False),
        ("monthly budget 20000", "budget", 2000000, "other", True),
        ("salary budget 9000", "budget", 900000, "other", True),  # income has no budget
        ("save 5000 a month", "goal", 500000, "other", False),
        ("हर महीने 5000 बचाना है", "goal", 500000, "other", False),
        ("മാസം 5000 സമ്പാദിക്കണം", "goal", 500000, "other", False),
    ],
)
def test_budgets_and_the_savings_goal_without_a_model(text, kind, amount, category, overall):
    (result,) = statement.read_statements(text, rules_settings(), TODAY)
    assert (result.kind, result.amount_minor, result.category, result.overall) == (
        kind,
        amount,
        category,
        overall,
    )


def test_a_model_budget_is_grounded_like_any_amount() -> None:
    budget = reading(type="budget", amount_phrase="5000", category="food_dining")
    assert statement._ground(budget, "food budget 5000", TODAY) == Statement(
        "budget", 500000, category="food_dining"
    )
    overall = reading(type="budget", amount_phrase="20000", category=None)
    assert statement._ground(overall, "budget 20000", TODAY).overall is True
    goal = reading(type="goal", amount_phrase="9000", category=None)
    assert statement._ground(goal, "save 5000 a month", TODAY).amount_minor == 500000


# d1-ultra in front of the statement model (docs/triage-round/contract.md).


def sure_message(**overrides) -> Sorted:
    """A single UPI tea payment, every answer sure, unless overridden."""
    answers = {
        "kind": choice("spent"),
        "several": noul(0.02),
        "payee": noul(0.03),
        "category": choice("food_dining"),
        "mode": choice("upi"),
    }
    return Sorted(answers | overrides)


def test_a_sure_single_entry_is_read_without_the_model() -> None:
    assert statement._fast(sure_message(), "chai 20 gpay se diye", TODAY) == [
        Statement("spent", 2000, None, "upi", TODAY, "food_dining")
    ]
    received = sure_message(
        kind=choice("received"), category=choice("salary"), mode=choice("unknown")
    )
    assert statement._fast(received, "kal salary 30000 aayi", TODAY) == [
        Statement("received", 3000000, None, "unknown", date(2026, 10, 25), "salary")
    ]
    nothing_named = sure_message(category=choice("none"))
    assert statement._fast(nothing_named, "500 diye", TODAY)[0].category == "other"


@pytest.mark.parametrize(
    ("text", "overrides"),
    [
        ("doodhwale ko 500 diye", {"payee": noul(0.97)}),  # a payee's name needs the model
        ("chai 20", {"payee": noul(0.5)}),  # not clear whether it names one
        ("chai 20, auto 50", {"several": noul(0.95)}),
        ("chai 20 auto 50", {}),  # two amounts, even when d1-ultra misses them
        ("Rs 500 debited from a/c [account] to VPA [number]", {}),  # a pasted bank SMS
        ("chai 20", {"category": choice("food_dining", 0.6)}),
        ("chai 20", {"kind": choice("spent", 0.6)}),
        ("samooh ki kist 1200", {"kind": choice("due")}),  # dues keep the model
        ("paise diye", {}),  # no amount
    ],
)
def test_the_model_reads_what_d1_ultra_is_not_sure_of(text: str, overrides: dict) -> None:
    assert statement._fast(sure_message(**overrides), text, TODAY) is None


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("today", Statement("question", checkup="today")),
        ("week", Statement("question", checkup="week")),
        ("month", Statement("question", checkup="month")),
        ("question", Statement("question")),
        ("other", Statement("unclear")),
    ],
)
def test_sure_check_ups_questions_and_greetings(kind: str, expected: Statement) -> None:
    assert statement._fast(sure_message(kind=choice(kind)), "aaj ka hisaab batao", TODAY) == [
        expected
    ]


def test_sure_budgets_and_goals_are_read_like_the_rules() -> None:
    budget = sure_message(kind=choice("budget"), category=choice("food_dining"))
    assert statement._fast(budget, "khane ka budget 5000", TODAY) == [
        Statement("budget", 500000, category="food_dining")
    ]
    overall = sure_message(kind=choice("budget"), category=choice("none"))
    assert statement._fast(overall, "budget 20000", TODAY) == [
        Statement("budget", 2000000, category="other", overall=True)
    ]
    unsure = sure_message(kind=choice("budget"), category=choice("other"))
    assert statement._fast(unsure, "budget 20000", TODAY) is None
    goal = sure_message(kind=choice("goal"), category=choice("none"))
    assert statement._fast(goal, "save 5000 a month", TODAY) == [Statement("goal", 500000)]


def test_a_sure_entry_does_not_wait_for_the_statement_model(monkeypatch) -> None:
    release = threading.Event()

    class Client:
        def __init__(self, **_kwargs):
            self.responses = SimpleNamespace(
                parse=held(SimpleNamespace(output_parsed=reading()), release)
            )

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(statement, "OpenAI", Client)
    seen: list[tuple[str, str]] = []

    def sort_message(text: str, language: str, settings: Settings) -> Sorted:
        seen.append((text, language))
        return sure_message()

    monkeypatch.setattr(statement.triage, "sort_message", sort_message)
    settings = triaged(
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
            environment="test",
            openai_api_key="synthetic-key",
            openai_assistant_model="synthetic-model",
        )
    )
    try:
        result = statement.read_statements("चाय 20 दिए", settings, TODAY)
    finally:
        release.set()
    assert result == [Statement("spent", 2000, None, "upi", TODAY, "food_dining")]
    assert seen == [("चाय 20 दिए", "hi")]
