"""The coach on WhatsApp (docs/advisor-round/contract.md, phase 3): the opt-in, "coach on/off",
and the timer's nudges: daytime only, at most one a day, never the same one twice, consent locked
through the send, the approved template outside the 24-hour window. SQLite unit doubles; the
claim table's constraints run on PostgreSQL in tests/advisor/test_postgres.py."""

from dataclasses import replace
from datetime import UTC, date, datetime
from unittest.mock import MagicMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from finboy.db.models import User
from finboy.db.models.advisor import AdvisorMessage, AdvisorNudge
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppCheckin
from finboy.services.advisor import coach as advisor
from finboy.services.mail.security import encrypt
from finboy.services.money.budgets import BudgetStatus
from finboy.services.money.engine import CommitmentView
from finboy.services.whatsapp import coach, hindi, malayalam
from finboy.services.whatsapp.meta import MetaUnavailable, SendUnknown
from finboy.services.whatsapp.statement import Statement
from sqlalchemy import select

from .conftest import Household

IST = ZoneInfo("Asia/Kolkata")
NOTHING = {"sent": 0, "failed": 0, "unknown": 0, "skipped": 0, "quiet": 0}
NUMBER = "919000000002"
NO_BOX = lambda *_: None  # noqa: E731 - detect is replaced in these tests


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=IST)


def near() -> advisor.Nudge:
    status = BudgetStatus("food_dining", 500000, 420000)
    detail = advisor.BudgetDetail(status, 13)
    return advisor.Nudge("budget_near", "2026-11:food_dining", "warning", detail)


def due_soon() -> advisor.Nudge:
    row = CommitmentView(
        id=uuid4(),
        kind="bill",
        label="Electricity bill",
        amount_minor=150000,
        due_date=date(2026, 11, 19),
        status="upcoming",
        confidence=0.9,
    )
    return advisor.Nudge("due_soon", str(row.id), "warning", advisor.DueDetail(row, 1))


@pytest.fixture
def coached(household: Household, settings, channel, monkeypatch):
    """An opted-in pilot household with the coach on, whose money calls for two nudges."""
    settings = settings.model_copy(update={"advisor_enabled": True, "coach_enabled": True})
    config = replace(channel, allowlist={**channel.allowlist, NUMBER: household.user_id})
    household.settings, household.channel = settings, config
    household.binding.sender_hash = config.digest("sender", NUMBER)
    household.binding.coach_opt_in_at = datetime.now(UTC)
    household.binding.last_inbound_at = at(18, 8)  # wrote to FinBoy this morning
    household.session.commit()
    nudges = [near(), due_soon()]
    monkeypatch.setattr(advisor, "detect", lambda _box, _today: list(nudges))
    return household, settings, config, nudges


def rows(household: Household) -> list[AdvisorNudge]:
    household.session.expire_all()
    return list(household.session.scalars(select(AdvisorNudge).order_by(AdvisorNudge.day)))


def chat(household: Household) -> list[str]:
    return [row.text for row in household.session.scalars(select(AdvisorMessage))]


def test_an_opted_in_household_hears_one_nudge_a_day(coached, pilot_factory) -> None:
    household, settings, config, nudges = coached
    client = MagicMock()
    client.send_buttons.return_value = "wamid.nudge1"
    counts = coach.send_nudges(pilot_factory, settings, config, client, at(18, 9), toolbox=NO_BOX)
    assert counts == {**NOTHING, "sent": 1}
    call = client.send_buttons.call_args
    # No model key here, so the code-written message goes, in the household's language.
    assert call.args == (NUMBER,) and call.kwargs["text"] == advisor.message(nudges[0], "hi")
    [(stop, title)] = call.kwargs["buttons"]
    assert stop.endswith(":nocoach") and title == hindi.COACH_NO
    [row] = rows(household)
    assert (row.kind, row.via, row.state, row.day) == (
        "budget_near",
        "message",
        "sent",
        date(2026, 11, 18),
    )
    assert row.outbound_message_id == "wamid.nudge1"
    assert len(row.period_key) == 64 and "food" not in row.period_key, "a keyed digest"
    assert chat(household) == [call.kwargs["text"]], "the nudge joins the household's chat"

    assert coach.send_nudges(
        pilot_factory, settings, config, client, at(18, 15), toolbox=NO_BOX
    ) == (NOTHING), "one a day"
    household.binding.last_inbound_at = at(19, 8)
    household.session.commit()
    client.send_buttons.return_value = "wamid.nudge2"
    counts = coach.send_nudges(pilot_factory, settings, config, client, at(19, 9), toolbox=NO_BOX)
    assert counts == {**NOTHING, "sent": 1}
    assert [row.kind for row in rows(household)] == ["budget_near", "due_soon"], "never twice"

    # "Stop coaching" under a nudge turns the coach off.
    household.session.expire_all()
    assert household.tap("nocoach", button=stop) is None
    assert household.binding.coach_opt_in_at is None
    assert household.texts()[-1] == hindi.COACH_OFF


def test_nothing_goes_out_without_the_coach_by_day_and_opt_in(coached, pilot_factory) -> None:
    household, settings, config, _ = coached
    client = MagicMock()

    def send(at_time: datetime, values=settings) -> dict[str, int]:
        return coach.send_nudges(pilot_factory, values, config, client, at_time, toolbox=NO_BOX)

    assert send(at(18, 9), settings.model_copy(update={"coach_enabled": False})) == NOTHING
    assert send(at(18, 9), settings.model_copy(update={"advisor_enabled": False})) == NOTHING
    assert send(at(18, 7, 59)) == NOTHING and send(at(18, 20)) == NOTHING
    household.binding.coach_opt_in_at = None
    household.session.commit()
    assert send(at(18, 9)) == NOTHING
    household.binding.coach_opt_in_at = datetime.now(UTC)
    household.binding.enabled = False  # STOP
    household.session.commit()
    assert send(at(18, 9)) == NOTHING
    assert client.send_buttons.call_count == client.send_template.call_count == 0
    assert rows(household) == []


def test_outside_the_window_only_the_approved_template(coached, pilot_factory) -> None:
    household, settings, config, nudges = coached
    household.binding.last_inbound_at = at(16, 9)  # two days ago
    household.session.commit()
    client = MagicMock()
    client.send_template.return_value = "wamid.template"
    counts = coach.send_nudges(pilot_factory, settings, config, client, at(18, 9), toolbox=NO_BOX)
    assert counts == {**NOTHING, "skipped": 1} and rows(household) == []
    templated = settings.model_copy(update={"whatsapp_coach_template": "finboy_coach_update"})
    counts = coach.send_nudges(pilot_factory, templated, config, client, at(18, 9), toolbox=NO_BOX)
    assert counts == {**NOTHING, "sent": 1}
    line = advisor.line(nudges[0], "hi")
    assert client.send_template.call_args.args == (NUMBER,)
    assert client.send_template.call_args.kwargs == {
        "name": "finboy_coach_update",
        "language": "hi",
        "parameters": [line],
        "quick_replies": [],
    }
    assert client.send_buttons.call_count == 0
    assert [row.via for row in rows(household)] == ["template"]
    assert chat(household) == [hindi.COACH_TEMPLATE.format(line=line)]


def test_a_check_in_today_is_the_days_message(coached, pilot_factory) -> None:
    household, settings, config, _ = coached
    household.session.add(
        WhatsAppCheckin(
            id=uuid4(),
            binding_id=household.binding.id,
            month=date(2026, 10, 1),
            state="sent",
            created_at=at(18, 8, 30),
        )
    )
    household.session.commit()
    client = MagicMock()
    assert coach.send_nudges(
        pilot_factory, settings, config, client, at(18, 9), toolbox=NO_BOX
    ) == (NOTHING)


def test_coach_off_before_the_send_stops_it(coached, pilot_factory, monkeypatch) -> None:
    household, settings, config, _ = coached
    binding_id = household.binding.id

    def compose(*_args, **_kwargs) -> advisor.Worded:
        with pilot_factory() as other:  # "coach off" commits while the nudge is being written
            other.get(WhatsAppBinding, binding_id).coach_opt_in_at = None
            other.commit()
        return advisor.Worded("🟡 written", "advisor")

    monkeypatch.setattr(advisor, "compose", compose)
    client = MagicMock()
    counts = coach.send_nudges(pilot_factory, settings, config, client, at(18, 9), toolbox=NO_BOX)
    assert counts == {**NOTHING, "failed": 1}
    assert client.send_buttons.call_count == 0 and chat(household) == []


def test_pilot_due_reminders_keep_the_dues(coached, pilot_factory) -> None:
    household, settings, config, nudges = coached
    nudges[:] = [due_soon(), near()]
    household.binding.reminders_opt_in_at = datetime.now(UTC)
    household.session.commit()
    client = MagicMock()
    client.send_buttons.return_value = "wamid.nudge"
    coach.send_nudges(pilot_factory, settings, config, client, at(18, 9), toolbox=NO_BOX)
    assert [row.kind for row in rows(household)] == ["budget_near"]


def test_a_failed_send_uses_the_day_and_an_unknown_one_is_kept(coached, pilot_factory) -> None:
    household, settings, config, _ = coached
    client = MagicMock()
    client.send_buttons.side_effect = MetaUnavailable
    counts = coach.send_nudges(pilot_factory, settings, config, client, at(18, 9), toolbox=NO_BOX)
    assert counts == {**NOTHING, "failed": 1} and chat(household) == []
    assert coach.send_nudges(
        pilot_factory, settings, config, client, at(18, 11), toolbox=NO_BOX
    ) == (NOTHING)
    household.binding.last_inbound_at = at(19, 8)
    household.session.commit()
    client.send_buttons.side_effect = SendUnknown
    counts = coach.send_nudges(pilot_factory, settings, config, client, at(19, 9), toolbox=NO_BOX)
    assert counts == {**NOTHING, "unknown": 1}
    assert [row.state for row in rows(household)] == ["failed", "unknown"]
    assert len(chat(household)) == 1, "it may have arrived, so the chat keeps it"


def test_a_quiet_household_hears_nothing(coached, pilot_factory) -> None:
    household, settings, config, nudges = coached
    nudges.clear()
    client = MagicMock()
    counts = coach.send_nudges(pilot_factory, settings, config, client, at(18, 9), toolbox=NO_BOX)
    assert counts == {**NOTHING, "quiet": 1} and rows(household) == []


def test_a_self_serve_household_hears_it_at_its_own_number(
    pilot_factory, settings, channel, monkeypatch
) -> None:
    settings = settings.model_copy(update={"advisor_enabled": True, "coach_enabled": True})
    number = "919000000077"
    key = settings.token_encryption_key.get_secret_value()
    with pilot_factory() as session:
        user = User(id=uuid4(), display_name="Household", joined_via="whatsapp")
        session.add(user)
        session.flush()
        session.add(
            WhatsAppBinding(
                id=uuid4(),
                user_id=user.id,
                sender_hash=channel.digest("sender", number),
                enabled=True,
                last_language="ml",
                consented_at=datetime.now(UTC),
                coach_opt_in_at=datetime.now(UTC),
                last_inbound_at=at(18, 8),
                encrypted_sender=encrypt(key, number),
            )
        )
        session.commit()
    monkeypatch.setattr(advisor, "detect", lambda _box, _today: [near()])
    client = MagicMock()
    client.send_buttons.return_value = "wamid.nudge"
    counts = coach.send_nudges(pilot_factory, settings, channel, client, at(18, 9), toolbox=NO_BOX)
    assert counts == {**NOTHING, "sent": 1}
    client.allow.assert_called_once_with(number)
    assert client.send_buttons.call_args.args == (number,)
    assert client.send_buttons.call_args.kwargs["text"] == advisor.message(near(), "ml")
    assert client.send_buttons.call_args.kwargs["buttons"][0][1] == malayalam.COACH_NO


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("coach on", True),
        ("Coach off.", False),
        ("कोच चालू करो", True),
        ("कोच बंद", False),
        ("കോച്ച് ഓൺ", True),
        ("കോച്ച് ഓഫ്", False),
        ("coach on karna hai kya", None),
    ],
)
def test_coach_commands_are_whole_messages(text: str, value: bool | None) -> None:
    found = coach.command(text)
    assert (found is not None) is (value is not None)


def test_coach_on_and_off_by_message(coached) -> None:
    household = coached[0]
    household.binding.coach_opt_in_at = None
    household.session.commit()
    assert household.say("coach on") is None
    assert household.binding.coach_opt_in_at is not None
    assert household.texts()[-1] == hindi.COACH_ON  # the chosen language
    assert household.say("कोच बंद") is None
    assert household.binding.coach_opt_in_at is None
    assert household.texts()[-1] == hindi.COACH_OFF


def test_without_the_coach_coach_on_is_an_ordinary_message(household, monkeypatch) -> None:
    monkeypatch.setattr(pilot_statement(), "read_statements", lambda *_args: [Statement("unclear")])
    household.say("coach on")
    assert household.binding.coach_opt_in_at is None


def pilot_statement():
    from finboy.services.whatsapp import pilot

    return pilot.statement


def test_this_week_offers_the_coach_and_its_buttons_switch_it(coached) -> None:
    household = coached[0]
    household.binding.coach_opt_in_at = None
    household.session.commit()
    household.record()  # something this week, so the week has a summary
    assert household.say("this week") is None
    assert household.texts()[-1].endswith(hindi.COACH_ASK)
    assert household.buttons()[0][1] == hindi.COACH_YES
    assert household.tap("coach") is None
    assert household.binding.coach_opt_in_at is not None
    assert household.texts()[-1] == hindi.COACH_ON
    household.say("this week")
    assert not household.texts()[-1].endswith(hindi.COACH_ASK)
    assert household.buttons()[0][1] == hindi.COACH_NO
    household.tap("nocoach")
    assert household.binding.coach_opt_in_at is None


def test_without_the_coach_this_week_offers_nothing(household) -> None:
    household.record()
    household.say("this week")
    assert not any(item.get("buttons") for item in household.sent)


def test_one_households_failure_never_stops_the_others(coached, pilot_factory, monkeypatch) -> None:
    household, settings, config, nudges = coached

    def detect(_box, _today):
        raise ValueError("synthetic engine failure")

    monkeypatch.setattr(advisor, "detect", detect)
    client = MagicMock()
    counts = coach.send_nudges(pilot_factory, settings, config, client, at(18, 9), toolbox=NO_BOX)
    assert counts == {**NOTHING, "skipped": 1} and rows(household) == []
    monkeypatch.setattr(advisor, "detect", lambda _box, _today: list(nudges))
    client.send_buttons.return_value = "wamid.nudge"
    counts = coach.send_nudges(pilot_factory, settings, config, client, at(18, 10), toolbox=NO_BOX)
    assert counts == {**NOTHING, "sent": 1}, "an hour later it is tried again"
