"""Dates, corrections and typed replies to cards (docs/whatsapp.md, "Dates and card replies").

The first test replays the 22 November 2026 conversation that went wrong: "264.51 to pay later on
january 1" came back as 1 December, Change asked only for the amount, No said the button no
longer worked, and the questions that followed were read as amounts for ten minutes.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from finboy.core.clock import today_ist
from finboy.db.models.ledger import Commitment, Transaction
from finboy.db.models.whatsapp import WhatsAppPrompt
from finboy.services.ingestion import dates
from finboy.services.whatsapp import english, hindi, malayalam, pilot
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.statement import Statement, StatementReading, _ground_all
from sqlalchemy import select

INCIDENT = "264.51 to pay later on january 1"


def reads(monkeypatch, table: dict[str, list[Statement]]) -> None:
    """The diary reader as a table: each message's statements, else "unclear"."""
    monkeypatch.setattr(
        pilot.statement,
        "read_statements",
        lambda text, *_args: table.get(text, [Statement("unclear")]),
    )


def incident_reading() -> list[Statement]:
    """What the model copies from the incident message, grounded by the real code."""
    reading = StatementReading(
        type="due",
        amount_phrase="264.51",
        counterparty=None,
        mode="unknown",
        day_phrase="on january 1",
        category=None,
        due_day=1,
        due_label=None,
    )
    return _ground_all(reading, INCIDENT, today_ist())


def january_first():
    return dates.read_date("january 1", today_ist(), "future").day


def english_household(household):
    household.binding.language = "en"
    household.session.commit()
    return household


def due_rows(household) -> list[Commitment]:
    return list(household.session.scalars(select(Commitment).order_by(Commitment.created_at)))


def answered_questions(monkeypatch) -> list[str]:
    asked: list[str] = []

    def answer(conversation, text):
        asked.append(text)
        return conversation.done(conversation.send("ANSWER"))

    monkeypatch.setattr(pilot, "_answer", answer)
    return asked


def test_the_incident_reads_january_and_never_traps_the_household(household, monkeypatch):
    english_household(household)
    reads(monkeypatch, {INCIDENT: incident_reading()})
    asked = answered_questions(monkeypatch)
    assert household.say(INCIDENT) is None
    (due,) = due_rows(household)
    assert due.due_date == january_first() and due.amount_minor == 26451
    assert f"📅 {english.date_label(january_first())}" in household.texts()[-1]
    assert due.label == english.DUE_LABEL == "Payment"
    card = household.buttons()
    assert [title for _, title in card] == [english.YES, "✏️ Change", english.NO]
    # Change asks for the amount, date or name, and the card keeps working.
    assert household.tap("change", button=card[1][0]) is None
    assert household.texts()[-1] == english.FIX_DUE_ASK
    # A question during the correction is answered, not read as an amount.
    reads(
        monkeypatch,
        {INCIDENT: incident_reading(), "Any payment for jan": [Statement("question")]},
    )
    assert household.say("Any payment for jan") is None
    assert asked == ["Any payment for jan"]
    assert english.CARD_WAITING in household.texts()[-1]
    # No on the same card still works and drops the due.
    assert household.tap("no", button=card[2][0]) is None
    assert household.session.get(Commitment, due.id).status == "dismissed"
    open_changes = household.session.scalars(
        select(WhatsAppPrompt).where(
            WhatsAppPrompt.purpose == "change_amount", WhatsAppPrompt.state == "open"
        )
    ).all()
    assert open_changes == []


def test_a_typed_date_or_amount_corrects_the_newest_card(household, monkeypatch):
    english_household(household)
    reads(monkeypatch, {INCIDENT: incident_reading()})
    household.say(INCIDENT)
    (due,) = due_rows(household)
    # The date alone, the way people answer a wrong date.
    assert household.say("no it's jan 5") is None
    assert due.due_date == dates.read_date("jan 5", today_ist(), "future").day
    assert "5 January" in household.texts()[-1]
    # A month alone keeps the card's day.
    assert household.say("february") is None
    assert (due.due_date.month, due.due_date.day) == (2, 5)
    # The amount alone.
    assert household.say("300") is None
    assert due.amount_minor == 30000 and due.status == "pending"
    # Old buttons were replaced by the newest card, and say so.
    assert len(due_rows(household)) == 1


def test_change_then_the_date_is_fixed_not_turned_into_an_amount(household, monkeypatch):
    english_household(household)
    reads(monkeypatch, {INCIDENT: incident_reading()})
    household.say(INCIDENT)
    (due,) = due_rows(household)
    household.tap("change")
    assert household.say("the date is january 1") is None  # was ₹1 before this round
    assert due.amount_minor == 26451 and due.due_date == january_first()


def test_typed_yes_and_no_act_on_the_card(household, monkeypatch):
    reads(monkeypatch, {INCIDENT: incident_reading()})
    household.say(INCIDENT)
    (due,) = due_rows(household)
    assert household.say("galat") is None
    assert household.texts()[-1] == hindi.WHAT_WRONG
    assert household.say("cancel") is None
    assert household.texts()[-1] == hindi.FIX_CANCELLED and due.status == "pending"
    assert household.say("haan sahi hai") is None
    assert household.session.get(Commitment, due.id).status == "upcoming"


def test_a_new_entry_during_a_correction_is_its_own_entry(household, monkeypatch):
    record = household.record()
    household.card(record)
    household.tap("change")
    saved: list[list[Statement]] = []
    monkeypatch.setattr(pilot, "_save", lambda _conversation, readings: saved.append(readings))
    reads(monkeypatch, {"lunch 150": [Statement("spent", 15000, category="food_dining")]})
    household.say("lunch 150")
    assert saved and saved[0][0].amount_minor == 15000
    assert household.decided == []  # the record on the card was not touched
    assert household.session.get(Transaction, record).amount_minor == 50000


def test_a_resent_due_replaces_the_unconfirmed_one(household, monkeypatch):
    english_household(household)
    wrong = Statement("due", 26451, category="loan_emi", due_date=today_ist() + timedelta(days=9))
    reads(monkeypatch, {"264.51 to pay on 1st": [wrong], INCIDENT: incident_reading()})
    household.say("264.51 to pay on 1st")
    household.say(INCIDENT)
    (due,) = due_rows(household)
    assert due.due_date == january_first()
    assert household.texts()[-1].startswith(english.DUE_REPLACED)
    # The first card was replaced: its buttons say so instead of "doesn't work any more".
    first_yes = next(item["buttons"] for item in household.sent if item.get("buttons"))[0][0]
    assert household.tap("yes", button=first_yes) == "prompt_replaced"
    assert household.texts()[-1] == english.TAP_REPLACED


def test_a_confirmed_duplicate_is_flagged(household, monkeypatch):
    english_household(household)
    reads(monkeypatch, {INCIDENT: incident_reading()})
    household.say(INCIDENT)
    household.tap("yes")
    household.say(INCIDENT)
    assert household.texts()[-1].startswith("⚠️ You already saved ₹264.51")
    assert len(due_rows(household)) == 2


def test_a_due_without_a_month_day_asks_for_the_day(household, monkeypatch):
    january = Statement(
        "due", 500000, category="rent", label="किराया", date_problem="month_only", date_month=1
    )
    reads(monkeypatch, {"जनवरी में किराया 5000": [january]})
    assert household.say("जनवरी में किराया 5000") == "date_unclear"
    assert household.texts()[-1] == hindi.DUE_DAY_ASK.format(month="जनवरी")
    assert household.say("5") is None
    (due,) = due_rows(household)
    assert (due.due_date.month, due.due_date.day, due.label) == (1, 5, "किराया")


def test_several_dues_take_the_first_and_say_so(household, monkeypatch):
    first = Statement("due", 500000, category="rent", due_date=today_ist() + timedelta(days=9))
    second = Statement(
        "due", 200000, category="education", due_date=today_ist() + timedelta(days=18)
    )
    reads(monkeypatch, {"rent and fees": [first, second]})
    household.say("rent and fees")
    (due,) = due_rows(household)
    assert due.amount_minor == 500000
    assert hindi.DUES_ONE_AT_A_TIME in household.texts()[-1]


def test_a_pending_due_without_a_working_card_is_offered_again(household, monkeypatch):
    reads(monkeypatch, {INCIDENT: incident_reading()})
    household.say(INCIDENT)
    (due,) = due_rows(household)
    # The old Change answered the card and its correction expired: nothing was left to tap.
    for prompt in household.session.scalars(select(WhatsAppPrompt)):
        prompt.state = "answered"
    due.created_at = datetime.now(UTC) - timedelta(hours=1)
    household.session.commit()
    household.say("hello")
    assert household.texts()[-1].startswith(hindi.DUE_PENDING)
    household.say("haan")
    assert household.session.get(Commitment, due.id).status == "upcoming"


def test_a_swipe_reply_corrects_the_card_it_quotes(household, monkeypatch):
    english_household(household)
    later = Statement("due", 99900, category="utilities", due_date=today_ist() + timedelta(days=5))
    reads(monkeypatch, {INCIDENT: incident_reading(), "999 power bill": [later]})
    household.say(INCIDENT)
    first_card = household.session.scalars(
        select(WhatsAppPrompt).where(WhatsAppPrompt.purpose == "confirm")
    ).one()
    first_card.outbound_message_id = "wamid.first-card"
    household.session.commit()
    household.say("999 power bill")
    question = InboundQuestion(
        "wamid." + uuid4().hex,
        "919000000002",
        datetime.now(UTC),
        "text",
        "feb 3",
        context_id="wamid.first-card",
    )
    assert household.run(question) is None
    rent, bill = due_rows(household)
    assert (rent.due_date.month, rent.due_date.day) == (2, 3)
    assert bill.due_date == later.due_date


def test_a_saved_due_date_can_be_corrected_by_typing(household, monkeypatch):
    english_household(household)
    reads(monkeypatch, {INCIDENT: incident_reading()})
    corrected: list = []

    def correct_obligation(session, *, user_id, obligation_id, request):
        corrected.append(request.due_date)
        session.get(Commitment, obligation_id).due_date = request.due_date
        session.commit()
        return SimpleNamespace()

    monkeypatch.setattr(pilot, "correct_obligation", correct_obligation)
    household.say(INCIDENT)
    household.tap("yes")
    assert household.say("jan 10") is None
    assert corrected == [dates.read_date("jan 10", today_ist(), "future").day]
    assert household.texts()[-1].startswith(english.DATE_CHANGED)


def test_malayalam_reply_words_work(household, monkeypatch):
    household.binding.language = "ml"
    household.session.commit()
    reads(monkeypatch, {INCIDENT: incident_reading()})
    household.say(INCIDENT)
    (due,) = due_rows(household)
    assert household.say("ജനുവരി 3") is None and due.due_date.day == 3
    assert household.say("ശരി") is None
    assert household.session.get(Commitment, due.id).status == "upcoming"
    assert malayalam.DUE_LABEL in due.label
