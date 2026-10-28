from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from finboy.db.models.ledger import Transaction
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppPrompt
from finboy.services.assistant.models import AssistantAnswer
from finboy.services.speech.models import Transcript
from finboy.services.ux.state import TaskError
from finboy.services.whatsapp import hindi, pilot, prompts
from finboy.services.whatsapp.capture import Capture
from sqlalchemy import select

from .conftest import Household, make_household


def test_nothing_is_recorded_or_answered_before_consent(
    pilot_factory, settings, channel, monkeypatch
) -> None:
    home = Household(pilot_factory, settings, channel, monkeypatch, consented=False)
    monkeypatch.setattr(pilot.assistant, "answer_question", MagicMock(side_effect=AssertionError))
    assert home.say("दूधवाले को 500 दिए") is None
    assert home.texts() == [hindi.CONSENT] and home.spoke() == 1
    assert [title for _, title in home.buttons()] == [hindi.AGREE, hindi.DECLINE]
    assert home.tap("decline") is None
    assert home.binding.consented_at is None and home.texts()[-1] == hindi.DECLINED
    home.say("नमस्ते")
    assert home.tap("agree") is None
    assert home.binding.consented_at is not None and home.texts()[-1] == hindi.WELCOME


def test_yes_confirms_through_the_versioned_decision_and_offers_undo(household) -> None:
    record = household.record()
    assert household.card(record) is None
    text = household.texts()[-1]
    assert "₹500 दिए" in text and "📅 आज" in text and "राशन-किराना" in text
    assert [title for _, title in household.buttons()] == [hindi.YES, hindi.CHANGE, hindi.NO]
    assert household.tap("yes") is None
    assert [request.action for request in household.decided] == ["confirm"]
    assert household.session.get(Transaction, record).status == "confirmed"
    assert household.texts()[-1].startswith("✅ जोड़ दिया: ₹500 दिए")
    assert [title for _, title in household.buttons()] == [hindi.UNDO]


def test_no_rejects_and_undo_brings_the_card_back(household) -> None:
    record = household.record()
    household.card(record)
    assert household.tap("no") is None
    assert household.session.get(Transaction, record).status == "rejected"
    assert household.tap("undo") is None
    assert household.session.get(Transaction, record).status == "needs_review"
    assert household.texts()[-1].startswith(hindi.UNDONE) and "सही है?" in household.texts()[-1]


def test_undo_after_something_else_changed_is_refused(household) -> None:
    household.card(household.record())
    household.tap("yes")
    household.undo_error = TaskError("decision_conflict")
    assert household.tap("undo") == "record_changed"
    assert household.texts()[-1] == hindi.UNDO_REFUSED


def test_a_tap_never_acts_on_a_record_that_changed_since_the_card(household) -> None:
    record = household.record()
    household.card(record)
    household.session.get(Transaction, record).amount_minor = 90000
    household.session.commit()
    assert household.tap("yes") == "record_changed"
    assert household.decided == [] and household.texts()[-1] == hindi.CHANGED


def test_old_answered_expired_and_foreign_buttons_do_nothing(household) -> None:
    record = household.record()
    household.card(record)
    yes = next(key for key, _ in household.buttons() if key.endswith(":yes"))
    unknown = "fb1:" + uuid4().hex + ":yes"
    assert household.tap("yes", button=unknown) == "prompt_expired"
    # A second household's binding in the same database cannot use this household's card.
    neighbour = WhatsAppBinding(
        id=uuid4(),
        user_id=make_household(household.session, name="Pilot household 2"),
        sender_hash=uuid4().hex,
        enabled=True,
        language="hi",
        consented_at=datetime.now(UTC),
        last_inbound_at=datetime.now(UTC),
    )
    household.session.add(neighbour)
    household.session.commit()
    assert household.tap("yes", button=yes, binding=neighbour) == "prompt_expired"
    assert household.decided == []
    assert household.tap("yes", button=yes) is None
    assert household.tap("yes", button=yes) == "prompt_expired", "a second tap does nothing"
    household.card(household.record())
    late = next(key for key, _ in household.buttons() if key.endswith(":yes"))
    prompt = household.session.get(WhatsAppPrompt, UUID(hex=late.split(":")[1]))
    prompt.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    household.session.commit()
    assert household.tap("yes", button=late) == "prompt_expired"
    assert household.session.get(WhatsAppPrompt, prompt.id).state == "expired"


def test_change_reads_only_an_amount_then_shows_the_card_again(household) -> None:
    record = household.record()
    household.card(record)
    assert household.tap("change") is None
    assert household.texts()[-1] == hindi.CHANGE_ASK
    assert household.say("पता नहीं") == "amount_unclear"
    assert household.texts()[-1] == hindi.AMOUNT_UNCLEAR and household.decided == []
    assert household.say("चार सौ") is None
    assert [(r.action, r.correction.amount_minor) for r in household.decided] == [
        ("correct", 40000)
    ]
    assert "₹400 दिए" in household.texts()[-1] and "सही है?" in household.texts()[-1]
    assert household.session.get(Transaction, record).status == "needs_review"


def test_a_saved_screenshot_gets_a_card_and_other_outcomes_get_plain_hindi(
    household, monkeypatch
) -> None:
    record = household.record()
    result = Capture("saved", 50000, "दूधवाला", record)
    monkeypatch.setattr(pilot.capture, "capture_screenshot", lambda *_args: result)
    assert household.say("", kind="image") is None
    assert "सही है?" in household.texts()[-1]
    monkeypatch.setattr(pilot.capture, "capture_screenshot", lambda *_args: Capture("no_payment"))
    assert household.say("", kind="image") is None
    assert household.texts()[-1].startswith("इस तस्वीर में")


def test_questions_use_the_shared_assistant_in_hindi_with_voice(household, monkeypatch) -> None:
    ask = MagicMock(
        return_value=AssistantAnswer(
            intent="spend",
            policy="answer",
            display_text="इस हफ़्ते का खर्च",
            speech_text="इस हफ़्ते का खर्च",
            speech_language="hi",
            facts=[],
            simulation=None,
            evidence_transactions=[],
            warnings=[],
        )
    )
    monkeypatch.setattr(pilot.assistant, "answer_question", ask)
    transcribe = MagicMock(
        return_value=Transcript(transcript="कितना खर्च हुआ?", detected_language="hi")
    )
    monkeypatch.setattr(pilot.speech, "transcribe_audio", transcribe)
    assert household.say("", kind="audio") is None
    assert transcribe.call_args.kwargs["language_hint"] == "hi"
    assert ask.call_args.kwargs["display_style"] == "hi"
    assert ask.call_args.kwargs["user_id"] == household.user_id
    assert household.texts()[-1] == "इस हफ़्ते का खर्च" and household.spoke() == 1


def test_prompt_ids_round_trip_and_fingerprints_follow_the_record(household, channel) -> None:
    row = household.session.get(Transaction, household.record())
    fingerprint = prompts.record_fingerprint(channel, row)
    row.status = "confirmed"
    assert prompts.record_fingerprint(channel, row) != fingerprint
    prompt = household.session.scalars(select(WhatsAppPrompt)).first() or WhatsAppPrompt(id=uuid4())
    assert prompts.parse(prompts.button(prompt, "yes")) == (prompt.id, "yes")
    assert prompts.parse("fb1:" + uuid4().hex + ":delete") is None


def test_spoken_money_goes_through_review_and_comes_back_as_a_card(household, monkeypatch) -> None:
    from finboy.core.clock import today_ist
    from finboy.services.whatsapp.statement import Statement

    spoken = Statement("spent", 50000, "दूधवाले", "cash", today_ist(), "groceries")
    monkeypatch.setattr(pilot.statement, "read_statement", lambda *_args: spoken)
    recorded: dict = {}

    def record_voice(_engine, _settings, **kwargs):
        recorded.update(kwargs)
        return Capture("saved", 50000, "दूधवाले", household.record())

    monkeypatch.setattr(pilot.capture, "record_voice", record_voice)
    assert household.say("दूधवाले को पाँच सौ नकद दिए") is None
    assert recorded["user_id"] == household.user_id and recorded["category"] == "groceries"
    assert recorded["line"].startswith("Rs. 500.00 paid to दूधवाले via cash on ")
    assert "सही है?" in household.texts()[-1]
    assert [title for _, title in household.buttons()] == [hindi.YES, hindi.CHANGE, hindi.NO]


def test_unclear_messages_and_missing_amounts_are_explained_not_guessed(
    household, monkeypatch
) -> None:
    from finboy.services.whatsapp.statement import Statement

    monkeypatch.setattr(pilot.capture, "record_voice", MagicMock(side_effect=AssertionError))
    monkeypatch.setattr(pilot.statement, "read_statement", lambda *_args: Statement("unclear"))
    assert household.say("नमस्ते") is None and household.texts()[-1] == hindi.UNCLEAR
    monkeypatch.setattr(pilot.statement, "read_statement", lambda *_args: Statement("spent"))
    assert household.say("दूधवाले को पैसे दिए") == "amount_unclear"
    assert household.texts()[-1] == hindi.AMOUNT_MISSING


def test_an_already_confirmed_payment_is_not_offered_again(household, monkeypatch) -> None:
    from finboy.core.clock import today_ist
    from finboy.services.whatsapp.statement import Statement

    record = household.record()
    household.session.get(Transaction, record).status = "confirmed"
    household.session.commit()
    spoken = Statement("spent", 50000, "दूधवाले", "unknown", today_ist(), "groceries")
    monkeypatch.setattr(pilot.statement, "read_statement", lambda *_args: spoken)
    monkeypatch.setattr(
        pilot.capture,
        "record_voice",
        lambda *_args, **_kwargs: Capture("already_recorded", 50000, "दूधवाले", record),
    )
    assert household.say("दूधवाले को 500 दिए") is None
    assert household.texts()[-1] == hindi.ALREADY


def spoken_due(monkeypatch, due_date=None):
    """A due far enough ahead that no reminder card follows the reply on any test date."""
    from finboy.core.clock import today_ist
    from finboy.services.whatsapp.statement import Statement

    due = Statement(
        "due",
        120000,
        category="loan_emi",
        due_date=due_date or today_ist() + timedelta(days=15),
        label="समूह की किस्त",
    )
    monkeypatch.setattr(pilot.statement, "read_statement", lambda *_args: due)
    return due


def test_a_spoken_due_waits_as_pending_then_asks_once_about_reminders(
    household, monkeypatch
) -> None:
    from finboy.db.models.ledger import Commitment

    said = spoken_due(monkeypatch)
    assert household.say("समूह की किस्त 1200, हर महीने 10 तारीख") is None
    due = household.session.scalars(select(Commitment)).one()
    assert (due.status, due.kind, due.amount_minor) == ("pending", "loan", 120000)
    assert "📌 ₹1,200 देना है" in household.texts()[-1]
    assert hindi.date_label(said.due_date) in household.texts()[-1]
    assert household.tap("yes") is None
    assert household.session.get(Commitment, due.id).status == "upcoming"
    assert hindi.REMIND_ASK in household.texts()[-1]
    assert [title for _, title in household.buttons()] == [hindi.REMIND, hindi.UNDO]
    assert household.tap("remind") is None
    assert household.binding.reminders_opt_in_at is not None
    assert household.texts()[-1] == hindi.REMINDERS_ON
    spoken_due(monkeypatch)
    household.say("समूह की किस्त 1200, हर महीने 10 तारीख")
    household.tap("yes")
    assert hindi.REMIND_ASK not in household.texts()[-1], "reminders are only asked once"


def test_self_serve_households_are_never_promised_reminders(household, monkeypatch) -> None:
    # Reminders reach pilot households only so far (docs/signup-round/contract.md).
    household.self_serve = True
    spoken_due(monkeypatch)
    household.say("समूह की किस्त 1200, हर महीने 10 तारीख")
    household.tap("yes")
    assert hindi.REMIND_ASK not in household.texts()[-1]
    assert [title for _, title in household.buttons()] == [hindi.UNDO]
    assert household.binding.reminders_opt_in_at is None


def test_a_due_can_be_rejected_undone_and_its_amount_changed(household, monkeypatch) -> None:
    from finboy.db.models.ledger import Commitment

    spoken_due(monkeypatch)
    household.say("समूह की किस्त 1200, हर महीने 10 तारीख")
    due_id = household.session.scalars(select(Commitment.id)).one()
    assert household.tap("no") is None
    assert household.session.get(Commitment, due_id).status == "dismissed"
    assert household.tap("undo") is None
    assert household.session.get(Commitment, due_id).status == "pending"
    assert household.texts()[-1].startswith(hindi.UNDONE)
    assert household.tap("change") is None and household.texts()[-1] == hindi.CHANGE_ASK
    assert household.say("पंद्रह सौ") is None
    assert household.session.get(Commitment, due_id).amount_minor == 150000
    assert "₹1,500 देना है" in household.texts()[-1]


def test_a_due_without_a_day_asks_for_it(household, monkeypatch) -> None:
    from finboy.db.models.ledger import Commitment
    from finboy.services.whatsapp.statement import Statement

    monkeypatch.setattr(
        pilot.statement,
        "read_statement",
        lambda *_args: Statement("due", 120000, category="loan_emi", label="किस्त"),
    )
    assert household.say("किस्त 1200 देनी है") is None
    assert household.texts()[-1] == hindi.DUE_DAY_MISSING
    assert household.session.scalars(select(Commitment)).all() == []
