"""The money manager on WhatsApp (docs/money-manager-round/contract.md): entries saved at once,
several items per message, Undo / Put back / Amount / Category, budgets, the savings goal and the
opt-in monthly check-in. SQLite unit doubles; the versioned paths run on PostgreSQL in
tests/pilot/test_postgres.py."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from finboy.core.clock import today_ist
from finboy.db.models import User
from finboy.db.models.ledger import EmailSource, Transaction
from finboy.db.models.money import Budget
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppCheckin
from finboy.services.mail.security import encrypt
from finboy.services.money.budgets import BudgetStatus
from finboy.services.whatsapp import categories, cfo, checkin, english, hindi, pilot
from finboy.services.whatsapp.capture import Capture
from finboy.services.whatsapp.meta import BUTTON_PATTERN
from finboy.services.whatsapp.statement import Statement
from sqlalchemy import select

from .conftest import Household, make_ledger

IST = ZoneInfo("Asia/Kolkata")
NOTHING = {"sent": 0, "failed": 0, "unknown": 0, "skipped": 0}


def said(monkeypatch, *statements: Statement) -> None:
    monkeypatch.setattr(pilot.statement, "read_statements", lambda *_args: list(statements))


def spent(amount: int, payee: str, category: str = "other") -> Statement:
    return Statement("spent", amount, payee, "unknown", today_ist(), category)  # type: ignore[arg-type]


def captured(household: Household, monkeypatch, amounts: list[int]) -> list[UUID]:
    """Each line through the pipeline becomes its own record waiting for review."""
    records = [household.record(amount=amount) for amount in amounts]
    calls = iter(records)
    monkeypatch.setattr(
        pilot.capture,
        "record_voice",
        lambda *_args, **kwargs: Capture("saved", 0, None, next(calls)),
    )
    return records


def listing(household: Household) -> list[tuple[str, str]]:
    return next(item["listing"] for item in reversed(household.sent) if item.get("listing")).rows


def test_several_items_are_saved_at_once_and_undone_together(household, monkeypatch) -> None:
    said(monkeypatch, spent(2000, "चाय"), spent(5000, "ऑटो"), spent(12000, "खाना"))
    records = captured(household, monkeypatch, [2000, 5000, 12000])
    assert household.say("चाय 20, ऑटो 50, खाना 120") is None
    assert [request.action for request in household.decided] == ["confirm"] * 3
    assert all(household.session.get(Transaction, r).status == "confirmed" for r in records)
    text = household.texts()[-1]
    assert text.startswith("✅ 3 बातें जोड़ दीं · ₹190") and "• ₹50" in text
    assert [title for _, title in household.buttons()] == [hindi.UNDO_ALL, hindi.FIX_ONE]
    assert household.tap("undoall") is None
    assert [request.action for request in household.decided][3:] == ["reject"] * 3
    assert all(household.session.get(Transaction, r).status == "rejected" for r in records)
    assert household.texts()[-1] == hindi.removed_many(3, 19000)


def test_fix_one_lists_the_items_and_opens_one(household, monkeypatch) -> None:
    said(monkeypatch, spent(2000, "चाय"), spent(5000, "ऑटो"))
    first, _ = captured(household, monkeypatch, [2000, 5000])
    household.say("चाय 20, ऑटो 50")
    assert household.tap("fixone") is None
    rows = listing(household)
    assert len(rows) == 2 and all(BUTTON_PATTERN.fullmatch(key) for key, _ in rows)
    assert rows[0][1].startswith("₹20 · ") and household.texts()[-1] == hindi.FIX_ASK
    assert household.tap("fix", button=rows[0][0]) is None
    assert household.texts()[-1].startswith("✅ जोड़ दिया: ₹20 दिए")
    assert household.tap("undo") is None
    assert household.session.get(Transaction, first).status == "rejected"


def test_unsure_items_in_a_message_wait_and_are_checked_through_fix_one(
    household, monkeypatch
) -> None:
    said(monkeypatch, spent(2000, "चाय"), spent(6_000_000, "सुनार"))
    tea, gold = captured(household, monkeypatch, [2000, 6_000_000])
    household.say("चाय 20, सुनार 60000")
    assert household.session.get(Transaction, tea).status == "confirmed"
    assert household.session.get(Transaction, gold).status == "needs_review"
    text = household.texts()[-1]
    assert "⚠️" in text and "₹60,000" in text
    household.tap("fixone")
    gold_row = next(key for key, title in listing(household) if "60,000" in title)
    assert household.tap("fix", button=gold_row) is None
    assert "सही है?" in household.texts()[-1]
    assert household.tap("yes") is None
    assert household.session.get(Transaction, gold).status == "confirmed"


def test_a_possible_duplicate_is_asked_about_first(household, monkeypatch) -> None:
    said(monkeypatch, spent(50000, "दूधवाला"))
    (record,) = captured(household, monkeypatch, [50000])
    household.session.get(Transaction, record).review_reason = "possible_duplicate"
    household.session.commit()
    household.say("दूधवाले को 500 दिए")
    assert household.decided == []
    assert household.texts()[-1].startswith(hindi.ASK_SAME)


def test_a_spoken_entry_matching_a_screenshot_is_asked_about_first(household, monkeypatch) -> None:
    ids = make_ledger(household.session, household.user_id)
    screenshot = household.session.get(Transaction, ids["transaction"])
    screenshot.status = "confirmed"
    source = household.session.scalars(
        select(EmailSource).where(EmailSource.user_id == household.user_id)
    ).one()
    source.source = "whatsapp_image"
    household.session.commit()
    said(monkeypatch, spent(50000, "दूधवाला"))
    captured(household, monkeypatch, [50000])
    household.say("दूधवाले को 500 दिए")
    assert household.decided == [] and household.texts()[-1].startswith(hindi.ASK_SAME)


def test_the_category_list_changes_a_saved_entry_and_remembers_the_payee(
    household, monkeypatch
) -> None:
    said(monkeypatch, spent(50000, "दूधवाला", "other"))
    (record,) = captured(household, monkeypatch, [50000])
    household.say("दूधवाले को 500 दिए")
    assert household.tap("category") is None
    rows = listing(household)
    assert 1 <= len(rows) <= 10 and rows[-1][1] == hindi.CATEGORY["other"]
    assert all(len(title) <= 24 for _, title in rows)
    food = next(key for key, _ in rows if key.endswith(":food_dining"))
    assert household.tap("food_dining", button=food) is None
    change = household.decided[-1]
    assert change.action == "correct" and change.correction.category == "food_dining"
    assert household.session.get(Transaction, record).category == "food_dining"
    assert household.texts()[-1].startswith(hindi.category_changed("food_dining", "दूधवाला"))


def test_a_typed_category_answers_the_open_list(household, monkeypatch) -> None:
    said(monkeypatch, spent(50000, "दूधवाला", "other"))
    (record,) = captured(household, monkeypatch, [50000])
    household.say("दूधवाले को 500 दिए")
    household.tap("category")
    monkeypatch.setattr(pilot.statement, "read_statements", MagicMock(side_effect=AssertionError))
    assert household.say("राशन") is None
    assert household.session.get(Transaction, record).category == "groceries"


def test_amount_on_a_saved_entry_corrects_it_and_shows_it_again(household, monkeypatch) -> None:
    said(monkeypatch, spent(50000, "दूधवाला"))
    (record,) = captured(household, monkeypatch, [50000])
    household.say("दूधवाले को 500 दिए")
    assert household.tap("amount") is None and household.texts()[-1] == hindi.CHANGE_ASK
    assert household.say("450") is None
    assert household.session.get(Transaction, record).amount_minor == 45000
    assert household.texts()[-1].startswith(hindi.AMOUNT_CHANGED)
    assert "₹450 दिए" in household.texts()[-1]


def test_a_remembered_payee_is_saved_in_its_category(household, monkeypatch) -> None:
    monkeypatch.setattr(pilot.merchants, "remembered", lambda *_args: "groceries")
    said(monkeypatch, spent(50000, "दूधवाला", "other"))
    captured(household, monkeypatch, [50000])
    household.session.query(Transaction).update({"category": "other"})
    household.session.commit()
    household.say("दूधवाले को 500 दिए")
    (confirm,) = household.decided
    assert confirm.action == "confirm" and confirm.correction.category == "groceries"


def test_typed_and_spoken_category_names_in_three_languages() -> None:
    assert categories.exact("Groceries") == "groceries"
    assert categories.exact("  राशन ") == "groceries"
    assert categories.exact("ഭക്ഷണം") == "food_dining"
    assert categories.exact("food dining") == "food_dining"
    assert categories.exact("chai 20") is None
    assert categories.named("खाने का बजट 5000") == "food_dining"
    assert categories.named("my phone recharge budget") == "phone_recharge"
    assert categories.named("budget 5000") is None


def test_budgets_and_the_goal_are_set_by_message_and_shown_on_saves(household, monkeypatch) -> None:
    said(monkeypatch, Statement("budget", 100000, category="groceries"))
    assert household.say("राशन का बजट 1000") is None
    assert household.session.scalars(select(Budget.limit_minor)).one() == 100000
    assert household.texts()[-1].startswith("🎯 बजट रख दिया: राशन-किराना ₹1,000")
    said(monkeypatch, Statement("goal", 500000))
    assert household.say("हर महीने 5000 बचाना है") is None
    assert household.session.get(User, household.user_id).monthly_savings_goal_minor == 500000
    said(monkeypatch, spent(90000, "दूधवाला", "groceries"))
    captured(household, monkeypatch, [90000])
    household.say("दूधवाले को 900 दिए")
    assert "🟡 राशन-किराना: ₹900 / ₹1,000" in household.texts()[-1]


def test_this_month_shows_budgets_and_offers_the_check_in(household, monkeypatch) -> None:
    household.settings = household.settings.model_copy(
        update={"whatsapp_checkin_template": "finboy_monthly_checkin"}
    )
    household.session.add(Budget(user_id=household.user_id, category="total", limit_minor=1000))
    household.session.commit()
    monkeypatch.setattr(pilot.statement, "read_statements", MagicMock(side_effect=AssertionError))
    assert household.say("इस महीने") is None
    text = household.texts()[-1]
    assert text.startswith("📒") and "कुल खर्च" in text and hindi.CHECKIN_ASK in text
    assert [title for _, title in household.buttons()] == [hindi.CHECKIN_YES]
    assert household.tap("checkin") is None
    assert household.binding.checkin_opt_in_at is not None
    assert household.texts()[-1] == hindi.CHECKIN_ON
    household.say("this month")
    assert [title for _, title in household.buttons()] == [hindi.CHECKIN_NO]
    household.tap("nocheckin")
    assert household.binding.checkin_opt_in_at is None


def test_without_a_template_no_check_in_is_offered(household, monkeypatch) -> None:
    household.say("summary")
    household.say("today")
    household.say("this month")
    assert not any(item.get("buttons") for item in household.sent)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("today", "today"),
        ("आज का हिसाब", "today"),
        ("ഇന്നത്തെ കണക്ക്", "today"),
        ("this week", "week"),
        ("हिसाब", "week"),
        ("കണക്ക്", "week"),
        ("this month", "month"),
        ("इस महीने का हिसाब", "month"),
        ("ഈ മാസം", "month"),
        ("budget", "month"),
        ("chai 20", None),
        ("today chai 20", None),
    ],
)
def test_check_ups_are_whole_messages(text: str, expected: str | None) -> None:
    reply = cfo.asked(text)
    assert (reply.__name__ if reply else None) == expected


@pytest.mark.parametrize(
    ("spent", "level", "line"),
    [
        (79_000, "ok", "🟢 Groceries: ₹790 of ₹1,000 this month"),
        (80_000, "near", "🟡 Groceries: ₹800 of ₹1,000 — ₹200 left this month"),
        (100_000, "near", "🟡 Groceries: ₹1,000 of ₹1,000 — ₹0 left this month"),
        (100_100, "over", "🔴 Groceries: ₹1,001 of ₹1,000 — ₹1 over this month"),
    ],
)
def test_budget_warnings_start_at_80_percent(spent: int, level: str, line: str) -> None:
    status = BudgetStatus("groceries", 100_000, spent)
    assert status.level == level and english.budget_line(status) == line


@pytest.mark.parametrize(
    ("saved", "income", "line"),
    [
        (0, 0, "add your income"),
        (600_000, 3_000_000, "goal is reached ✅"),
        (200_000, 3_000_000, "₹3,000 to go"),
        (-100_000, 3_000_000, "more went out than came in"),
    ],
)
def test_the_savings_goal_line(saved: int, income: int, line: str) -> None:
    assert line in english.goal_line(500_000, saved, income)


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=IST)


def opted_in(household: Household, config, number: str) -> None:
    household.binding.sender_hash = config.digest("sender", number)
    household.binding.checkin_opt_in_at = datetime.now(UTC)
    household.session.commit()


def test_a_check_in_goes_out_once_a_month_in_daytime_to_opted_in_households(
    household, pilot_factory, settings, channel
) -> None:
    templated = settings.model_copy(update={"whatsapp_checkin_template": "finboy_monthly_checkin"})
    number = "919000000002"
    config = replace(channel, allowlist={**channel.allowlist, number: household.user_id})
    client = MagicMock()
    client.send_template.return_value = "wamid.checkin"
    assert checkin.send_checkins(pilot_factory, templated, config, client, at(1, 12)) == NOTHING
    opted_in(household, config, number)
    assert checkin.send_checkins(pilot_factory, settings, config, client, at(1, 12)) == NOTHING
    assert checkin.send_checkins(pilot_factory, templated, config, client, at(1, 7, 59)) == NOTHING
    assert checkin.send_checkins(pilot_factory, templated, config, client, at(1, 20)) == NOTHING
    assert checkin.send_checkins(pilot_factory, templated, config, client, at(4, 12)) == NOTHING
    assert client.send_template.call_count == 0
    counts = checkin.send_checkins(pilot_factory, templated, config, client, at(2, 9))
    assert counts == {**NOTHING, "sent": 1}
    call = client.send_template.call_args
    assert call.args == (number,) and call.kwargs["name"] == "finboy_monthly_checkin"
    assert call.kwargs["language"] == "hi" and call.kwargs["quick_replies"] == []
    assert call.kwargs["parameters"] == ["अक्टूबर", "₹0", "₹0", "—"]
    assert checkin.send_checkins(pilot_factory, templated, config, client, at(3, 9)) == NOTHING
    assert client.send_template.call_count == 1, "never twice for the same month"
    household.session.expire_all()
    row = household.session.scalars(select(WhatsAppCheckin)).one()
    assert (row.state, row.outbound_message_id, str(row.month)) == (
        "sent",
        "wamid.checkin",
        "2026-10-01",
    )


def test_stop_ends_check_ins(household, pilot_factory, settings, channel) -> None:
    templated = settings.model_copy(update={"whatsapp_checkin_template": "finboy_monthly_checkin"})
    number = "919000000002"
    config = replace(channel, allowlist={**channel.allowlist, number: household.user_id})
    opted_in(household, config, number)
    household.binding.enabled = False
    household.session.commit()
    client = MagicMock()
    assert checkin.send_checkins(pilot_factory, templated, config, client, at(1, 9)) == NOTHING
    assert client.send_template.call_count == 0


def test_a_self_serve_household_gets_its_check_in_at_its_own_number(
    pilot_factory, settings, channel
) -> None:
    templated = settings.model_copy(update={"whatsapp_checkin_template": "finboy_monthly_checkin"})
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
                checkin_opt_in_at=datetime.now(UTC),
                last_inbound_at=datetime.now(UTC),
                encrypted_sender=encrypt(key, number),
            )
        )
        session.commit()
    client = MagicMock()
    client.send_template.return_value = "wamid.checkin"
    counts = checkin.send_checkins(pilot_factory, templated, channel, client, at(1, 9))
    assert counts == {**NOTHING, "sent": 1}
    client.allow.assert_called_once_with(number)
    assert client.send_template.call_args.args == (number,)
    assert client.send_template.call_args.kwargs["language"] == "ml"
