from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from finboy.core.clock import today_ist
from finboy.db.models import User
from finboy.db.models.ledger import Commitment, Transaction
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppPrompt, WhatsAppReminder
from finboy.services.pilot import cli
from finboy.services.ux.state import TaskError
from finboy.services.whatsapp import hindi, pilot, reminders
from finboy.services.whatsapp.capture import Capture
from finboy.services.whatsapp.config import ChannelUnavailable
from finboy.services.whatsapp.meta import BUTTON_PATTERN, MetaUnavailable, SendUnknown
from finboy.services.whatsapp.statement import Statement
from sqlalchemy import select

from .conftest import Household

IST = ZoneInfo("Asia/Kolkata")
LABEL = "समूह की किस्त"
NOTHING = {"sent": 0, "failed": 0, "unknown": 0, "skipped": 0}


@pytest.fixture
def home(household: Household) -> Household:
    household.binding.reminders_opt_in_at = datetime.now(UTC)
    household.session.commit()
    return household


def add_due(
    session, user_id: UUID, days: int, *, status: str = "upcoming", amount: int = 120000
) -> UUID:
    row = Commitment(
        id=uuid4(),
        user_id=user_id,
        kind="loan",
        label=LABEL,
        amount_minor=amount,
        due_date=today_ist() + timedelta(days=days),
        status=status,
        confidence=Decimal("1.000"),
        user_resolved=False,
    )
    session.add(row)
    session.commit()
    return row.id


def neighbour(session, *, pilot_user=True, opted_in=True, enabled=True, consented=True) -> UUID:
    user = User(id=uuid4(), display_name="Pilot household 2", pilot=pilot_user)
    session.add(user)
    session.flush()
    session.add(
        WhatsAppBinding(
            id=uuid4(),
            user_id=user.id,
            sender_hash=uuid4().hex,
            enabled=enabled,
            language="hi",
            consented_at=datetime.now(UTC) if consented else None,
            reminders_opt_in_at=datetime.now(UTC) if opted_in else None,
            last_inbound_at=datetime.now(UTC),
        )
    )
    session.commit()
    return user.id


def unclear(monkeypatch) -> None:
    monkeypatch.setattr(pilot.statement, "read_statement", lambda *_args: Statement("unclear"))


def reminder_cards(home: Household) -> list[dict]:
    return [item for item in home.sent if item.get("reminder")]


def test_only_opted_in_consented_pilot_dues_within_two_days_are_due(home) -> None:
    session, today = home.session, today_ist()
    soon, on_day = add_due(session, home.user_id, 2), add_due(session, home.user_id, 0)
    add_due(session, home.user_id, 5)
    add_due(session, home.user_id, 1, status="pending")
    overdue = add_due(session, home.user_id, -3)
    for kwargs in ({"opted_in": False}, {"enabled": False}, {"pilot_user": False}):
        add_due(session, neighbour(session, **kwargs), 0)
    picked = {(due.commitment.id, due.kind) for due in reminders.due_now(session, today)}
    assert picked == {(soon, "two_days"), (on_day, "due_day")}
    late = reminders.due_now(session, today, overdue=reminders.OVERDUE)
    assert (overdue, "due_day") in {(due.commitment.id, due.kind) for due in late}


def test_a_due_is_claimed_once_per_kind(home) -> None:
    add_due(home.session, home.user_id, 0)
    due = reminders.due_now(home.session, today_ist())[0]
    assert reminders.claim(home.session, due, "sending") is not None
    home.session.commit()
    assert reminders.claim(home.session, due, "sending") is None
    home.session.rollback()
    assert reminders.due_now(home.session, today_ist()) == []


def at(hour: int, minute: int = 0) -> datetime:
    return datetime.combine(today_ist(), time(hour, minute), IST)


def test_template_reminders_go_out_in_daytime_once_with_paid_and_later(
    home, pilot_factory, settings, channel
) -> None:
    templated = settings.model_copy(update={"whatsapp_reminder_template": "finboy_due_reminder"})
    number = "919000000002"
    config = replace(channel, allowlist={**channel.allowlist, number: home.user_id})
    home.binding.sender_hash = config.digest("sender", number)
    home.session.commit()
    add_due(home.session, home.user_id, 2)
    client = MagicMock()
    client.send_template.return_value = "wamid.reminder"
    assert reminders.send_reminders(pilot_factory, templated, config, client, at(7, 59)) == NOTHING
    assert reminders.send_reminders(pilot_factory, templated, config, client, at(20)) == NOTHING
    assert reminders.send_reminders(pilot_factory, settings, config, client, at(12)) == NOTHING
    assert client.send_template.call_count == 0
    counts = reminders.send_reminders(pilot_factory, templated, config, client, at(12))
    assert counts == {**NOTHING, "sent": 1}
    call = client.send_template.call_args
    assert call.args == (number,)
    assert (call.kwargs["name"], call.kwargs["language"]) == ("finboy_due_reminder", "hi")
    due_date = today_ist() + timedelta(days=2)
    assert call.kwargs["parameters"] == [LABEL, "₹1,200", hindi.date_label(due_date)]
    paid, later = call.kwargs["quick_replies"]
    assert BUTTON_PATTERN.fullmatch(paid) and paid.endswith(":paid") and later.endswith(":later")
    home.session.expire_all()
    reminder = home.session.scalars(select(WhatsAppReminder)).one()
    assert (reminder.kind, reminder.state) == ("two_days", "sent")
    assert reminder.outbound_message_id == "wamid.reminder"
    assert reminders.send_reminders(pilot_factory, templated, config, client, at(12, 30)) == NOTHING
    assert client.send_template.call_count == 1, "never sent twice"


@pytest.mark.parametrize(
    ("error", "state"), [(SendUnknown(), "unknown"), (MetaUnavailable(), "failed")]
)
def test_uncertain_and_failed_template_sends_are_recorded_and_not_retried(
    home, pilot_factory, settings, channel, error, state
) -> None:
    templated = settings.model_copy(update={"whatsapp_reminder_template": "finboy_due_reminder"})
    config = replace(channel, allowlist={**channel.allowlist, "919000000002": home.user_id})
    home.binding.sender_hash = config.digest("sender", "919000000002")
    home.session.commit()
    add_due(home.session, home.user_id, 0)
    client = MagicMock()
    client.send_template.side_effect = error
    counts = reminders.send_reminders(pilot_factory, templated, config, client, at(9))
    assert counts == {**NOTHING, state: 1}
    assert reminders.send_reminders(pilot_factory, templated, config, client, at(10)) == NOTHING
    home.session.expire_all()
    assert home.session.scalars(select(WhatsAppReminder.state)).one() == state


def test_a_household_without_an_approved_number_is_skipped(
    home, pilot_factory, settings, channel
) -> None:
    templated = settings.model_copy(update={"whatsapp_reminder_template": "finboy_due_reminder"})
    add_due(home.session, home.user_id, 0)
    client = MagicMock()
    counts = reminders.send_reminders(pilot_factory, templated, channel, client, at(9))
    assert counts == {**NOTHING, "skipped": 1} and client.send_template.call_count == 0
    home.session.expire_all()
    assert home.session.scalars(select(WhatsAppReminder)).all() == []


def test_without_a_template_a_due_follows_the_reply_once_as_its_own_card(home, monkeypatch) -> None:
    unclear(monkeypatch)
    add_due(home.session, home.user_id, 1)
    assert home.say("नमस्ते") is None
    assert home.texts()[0] == hindi.UNCLEAR, "the household's own reply comes first"
    (card,) = reminder_cards(home)
    assert card is home.sent[-1]
    assert card["text"].startswith("📌 याद दिलाना") and f"₹1,200 · {LABEL}" in card["text"]
    assert "📅 कल, " in card["text"]
    assert [title for _, title in card["buttons"]] == [hindi.PAID, hindi.LATER]
    home.say("नमस्ते")
    assert len(reminder_cards(home)) == 1, "once per due and kind"


def test_overdue_dues_are_mentioned_and_nothing_goes_to_households_that_did_not_opt_in(
    household, monkeypatch, settings
) -> None:
    unclear(monkeypatch)
    add_due(household.session, household.user_id, -3)
    household.say("नमस्ते")
    assert reminder_cards(household) == []
    household.binding.reminders_opt_in_at = datetime.now(UTC)
    household.session.commit()
    household.settings = settings.model_copy(
        update={"whatsapp_reminder_template": "finboy_due_reminder"}
    )
    household.say("नमस्ते")
    assert reminder_cards(household) == [], "the template job owns reminders when it exists"
    household.settings = settings
    household.say("नमस्ते")
    (card,) = reminder_cards(household)
    assert "को देना था" in card["text"]


def paying(home: Household, monkeypatch, outcome: str = "saved") -> dict:
    recorded: dict = {}

    def record_voice(_engine, _settings, **kwargs):
        recorded.update(kwargs)
        if outcome != "saved":
            return Capture(outcome)
        return Capture("saved", 120000, LABEL, home.record(amount=120000))

    monkeypatch.setattr(pilot.capture, "record_voice", record_voice)
    return recorded


def test_paid_records_a_confirmed_payment_and_marks_the_due_paid(home, monkeypatch) -> None:
    unclear(monkeypatch)
    due_id = add_due(home.session, home.user_id, 0)
    home.say("नमस्ते")
    paid_button = next(key for key, _ in home.buttons() if key.endswith(":paid"))
    recorded = paying(home, monkeypatch)
    assert home.tap("paid") is None
    row = home.session.get(Commitment, due_id)
    payment = home.session.get(Transaction, row.paid_transaction_id)
    assert (row.status, payment.status, payment.amount_minor) == ("paid", "confirmed", 120000)
    assert [request.action for request in home.decided] == ["confirm"]
    assert recorded["user_id"] == home.user_id and recorded["category"] == "loan_emi"
    assert recorded["line"].startswith(f"Rs. 1200.00 paid to {LABEL} on ")
    assert home.texts()[-1] == hindi.paid_done(120000, LABEL) + "\n\n" + hindi.REPEAT_ASK
    assert [title for _, title in home.buttons()] == [hindi.AGAIN, hindi.NO]
    assert home.tap("paid", button=paid_button) == "prompt_expired", "never paid twice"
    assert len(home.decided) == 1


def test_next_month_is_saved_on_request_and_can_be_undone(home, monkeypatch) -> None:
    unclear(monkeypatch)
    due_id = add_due(home.session, home.user_id, 0)
    home.say("नमस्ते")
    paying(home, monkeypatch)
    home.tap("paid")
    assert home.tap("again") is None
    following = home.session.scalars(select(Commitment).where(Commitment.id != due_id)).one()
    assert (following.status, following.label, following.amount_minor) == (
        "upcoming",
        LABEL,
        120000,
    )
    assert following.due_date == pilot._next_month(today_ist())
    assert home.texts()[-1] == hindi.due_saved(120000, LABEL, following.due_date)
    assert home.tap("undo") is None
    assert home.session.get(Commitment, following.id).status == "pending"
    assert home.texts()[-1].startswith(hindi.UNDONE)


def test_skip_saves_nothing_more(home, monkeypatch) -> None:
    unclear(monkeypatch)
    add_due(home.session, home.user_id, 0)
    home.say("नमस्ते")
    paying(home, monkeypatch)
    home.tap("paid")
    assert home.tap("skip") is None and home.texts()[-1] == hindi.OK
    assert len(home.session.scalars(select(Commitment)).all()) == 1


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 10, 26), date(2026, 11, 26)),
        (date(2026, 12, 15), date(2027, 1, 15)),
        (date(2027, 1, 31), date(2027, 2, 28)),
        (date(2028, 1, 31), date(2028, 2, 29)),
    ],
)
def test_next_month_keeps_the_day_where_the_month_has_it(day: date, expected: date) -> None:
    assert pilot._next_month(day) == expected


def test_later_keeps_the_paid_button_working(home, monkeypatch) -> None:
    unclear(monkeypatch)
    due_id = add_due(home.session, home.user_id, 0)
    home.say("नमस्ते")
    assert home.tap("later") is None and home.texts()[-1] == hindi.LATER_OK
    paying(home, monkeypatch)
    assert home.tap("paid") is None
    assert home.session.get(Commitment, due_id).status == "paid"


def test_a_busy_capture_records_nothing_and_the_button_can_be_tapped_again(
    home, monkeypatch
) -> None:
    unclear(monkeypatch)
    due_id = add_due(home.session, home.user_id, 0)
    home.say("नमस्ते")
    paying(home, monkeypatch, outcome="busy")
    assert home.tap("paid") == "capture_busy" and home.texts()[-1] == hindi.BUSY
    assert home.session.get(Commitment, due_id).status == "upcoming" and home.decided == []
    paying(home, monkeypatch)
    assert home.tap("paid") is None
    assert home.session.get(Commitment, due_id).status == "paid"


def test_a_due_already_paid_is_not_paid_again(home, monkeypatch) -> None:
    unclear(monkeypatch)
    due_id = add_due(home.session, home.user_id, 0)
    home.say("नमस्ते")
    home.session.get(Commitment, due_id).status = "paid"
    home.session.commit()
    monkeypatch.setattr(pilot.capture, "record_voice", MagicMock(side_effect=AssertionError))
    assert home.tap("paid") is None and home.texts()[-1] == hindi.ALREADY_PAID


def test_a_due_that_changed_since_the_reminder_is_left_alone(home, monkeypatch) -> None:
    unclear(monkeypatch)
    due_id = add_due(home.session, home.user_id, 0)
    home.say("नमस्ते")
    home.session.get(Commitment, due_id).amount_minor = 150000
    home.session.commit()
    monkeypatch.setattr(pilot.capture, "record_voice", MagicMock(side_effect=AssertionError))
    assert home.tap("paid") == "record_changed" and home.texts()[-1] == hindi.CHANGED


def test_a_link_conflict_keeps_the_payment_and_says_so(home, monkeypatch) -> None:
    unclear(monkeypatch)
    due_id = add_due(home.session, home.user_id, 0)
    home.say("नमस्ते")
    paying(home, monkeypatch)
    home.obligation_error = TaskError("version_conflict")
    assert home.tap("paid") == "record_changed"
    assert home.session.get(Commitment, due_id).status == "upcoming"
    prompt = home.session.scalars(
        select(WhatsAppPrompt).where(WhatsAppPrompt.purpose == "due_paid")
    ).one()
    assert prompt.state == "expired"


@pytest.mark.parametrize(
    ("days", "expected"),
    [(0, "📅 आज, "), (1, "📅 कल, "), (2, "📅 परसों, "), (-2, "को देना था")],
)
def test_reminder_wording(days: int, expected: str) -> None:
    today = date(2026, 10, 26)
    text = hindi.due_notice(120000, LABEL, today + timedelta(days=days), today)
    assert expected in text and "₹1,200" in text and text.endswith("भर दिया हो तो ✅ दबाइए।")


def test_remind_command_prints_counts_only(monkeypatch, capsys) -> None:
    engine = MagicMock()
    monkeypatch.setattr(cli, "Settings", lambda: object())
    monkeypatch.setattr(cli, "build_engine", lambda _settings: engine)
    monkeypatch.setattr(cli, "channel_config", lambda _settings: "config")
    monkeypatch.setattr(cli, "MetaClient", lambda _config: MagicMock())
    send = MagicMock(return_value={**NOTHING, "sent": 2})
    monkeypatch.setattr(cli.reminders, "send_reminders", send)
    assert cli.main(["remind"]) == 0
    assert capsys.readouterr().out == "Reminders: sent 2, failed 0, unknown 0, skipped 0\n"
    assert send.call_args.args[2] == "config" and engine.dispose.call_count == 1

    def unavailable(_settings):
        raise ChannelUnavailable

    monkeypatch.setattr(cli, "channel_config", unavailable)
    assert cli.main(["remind"]) == 2
    assert capsys.readouterr().out == "Refused: WhatsApp is not configured.\n"


def test_spoken_dues_are_valid_engine_commitments(home) -> None:
    from finboy.services.money.engine import commitment_view

    row = home.session.get(Commitment, add_due(home.session, home.user_id, -1))
    view = commitment_view(row, today=today_ist())
    assert (view.kind, view.liability_state, view.amount_minor) == ("loan", "overdue", 120000)
