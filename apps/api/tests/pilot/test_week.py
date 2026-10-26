import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from finboy.core.clock import today_ist
from finboy.core.config import LOCAL_USER_ID
from finboy.db.models import User
from finboy.db.models.ledger import (
    Commitment,
    EmailSource,
    ReviewDecision,
    Transaction,
)
from finboy.db.models.mail import ImportRun
from finboy.db.models.whatsapp import WhatsAppReceipt, WhatsAppReminder
from finboy.services.pilot import report
from finboy.services.speech.models import Transcript
from finboy.services.whatsapp import hindi, pilot
from sqlalchemy import select

from .conftest import Household

LABEL = "समूह की किस्त"


def confirm(home: Household, **values) -> Transaction:
    row = home.session.get(Transaction, home.record(**{"amount": 50000, **values}))
    row.status = "confirmed"
    home.session.commit()
    return row


def due(home: Household, days: int, amount: int = 120000) -> Commitment:
    row = Commitment(
        id=uuid4(),
        user_id=home.user_id,
        kind="loan",
        label=LABEL,
        amount_minor=amount,
        due_date=today_ist() + timedelta(days=days),
        status="upcoming",
        confidence=Decimal("1.000"),
        user_resolved=False,
    )
    home.session.add(row)
    home.session.commit()
    return row


@pytest.mark.parametrize("words", ["हिसाब", "हिसाब बताओ।", "Hisaab batao", "मेरा हिसाब"])
def test_hisaab_shows_this_weeks_money_in_text_and_voice(household, monkeypatch, words) -> None:
    monkeypatch.setattr(pilot.statement, "read_statement", MagicMock(side_effect=AssertionError))
    confirm(household)
    farm = confirm(household, amount=30000)
    farm.category = "farming"
    confirm(household, amount=200000, out=False)
    household.record()  # waiting for "हाँ": never counted
    due(household, 3)
    due(household, -2, amount=70000)
    household.session.commit()
    assert household.say(words) is None
    text = household.texts()[-1]
    assert text.startswith("📒 इस हफ़्ते का हिसाब")
    assert "💰 आए: ₹2,000" in text and "💸 गए: ₹800" in text
    assert "🏷️ सबसे ज़्यादा: राशन-किराना ₹500 · खेती ₹300" in text
    when = hindi.date_label(today_ist() + timedelta(days=3))
    assert f"📌 आगे देना है: ₹1,200 · {LABEL} · {when}" in text
    assert "अभी बाकी: ₹700" in text and "⏳ 1 बातें अभी नहीं जुड़ीं" in text
    assert household.spoke() == 1


def test_a_spoken_hisaab_works_even_while_an_amount_question_is_open(
    household, monkeypatch
) -> None:
    household.card(household.record())
    household.tap("change")
    monkeypatch.setattr(
        pilot.speech,
        "transcribe_audio",
        lambda **_: Transcript(transcript="हिसाब।", detected_language="hi"),
    )
    assert household.say("", kind="audio") is None
    assert household.texts()[-1].startswith("📒 इस हफ़्ते का हिसाब")
    assert household.decided == []


def test_an_empty_week_says_how_to_start(household) -> None:
    assert household.say("हिसाब") is None
    assert household.texts()[-1] == hindi.WEEK_EMPTY and household.spoke() == 1


def receipt(home: Household, kind: str, at: datetime, error: str | None = None) -> None:
    home.session.add(
        WhatsAppReceipt(
            id=uuid4(),
            binding_id=home.binding.id,
            inbound_message_id="wamid." + uuid4().hex,
            content_hash="c" * 64,
            kind=kind,
            state="completed",
            error_code=error,
            provider_at=at,
            received_at=at,
        )
    )


def captured(home: Household, source: str, at: datetime) -> None:
    run = ImportRun(id=uuid4(), user_id=home.user_id, mode=source, status="completed")
    home.session.add(run)
    home.session.flush()
    home.session.add(
        EmailSource(
            id=uuid4(),
            user_id=home.user_id,
            import_run_id=run.id,
            source=source,
            provider_message_id=uuid4().hex,
            content_sha256="a" * 64,
            sender_domain="whatsapp.invalid",
            subject_sha256="b" * 64,
            received_at=at,
            classification="unknown",
            processing_status="extracted",
        )
    )


def decision(home: Household, action: str, at: datetime, undone: bool = False) -> None:
    home.session.add(
        ReviewDecision(
            id=uuid4(),
            user_id=home.user_id,
            transaction_id=home.record(),
            action=action,
            before_state={},
            after_state={},
            result_version="synthetic",
            created_at=at,
            undone_at=at if undone else None,
        )
    )


def test_the_weekly_report_counts_without_amounts_names_or_content(household) -> None:
    today = today_ist()
    now = datetime.now(UTC)
    last_week = now - timedelta(days=7)
    yesterday_this_week = now - timedelta(days=1) if today.weekday() else now
    household.binding.reminders_opt_in_at = now
    for kind, at, error in [
        ("audio", now, None),
        ("audio", yesterday_this_week, "invalid_audio"),
        ("text", now, "amount_unclear"),
        ("button", now, None),
        ("image", now, None),
        ("audio", last_week, None),
    ]:
        receipt(household, kind, at, error)
    captured(household, "whatsapp_voice", now)
    captured(household, "whatsapp_image", now)
    decision(household, "confirm", now)
    decision(household, "correct", now)
    decision(household, "reject", now, undone=True)
    paid = confirm(household, amount=120000)
    instalment = due(household, 2)
    instalment.status, instalment.paid_transaction_id = "paid", paid.id
    household.session.add(
        WhatsAppReminder(
            id=uuid4(),
            binding_id=household.binding.id,
            commitment_id=instalment.id,
            kind="two_days",
            state="sent",
        )
    )
    household.session.commit()
    rows = report.weekly(household.session, today=today, weeks=2)
    assert [row["week"] for row in rows] == [
        (today - timedelta(days=today.weekday() + 7)).isoformat(),
        (today - timedelta(days=today.weekday())).isoformat(),
    ]
    before, this = rows
    assert before["messages"]["audio"] == 1 and before["decisions"]["confirm"] == 0
    assert this["household"] == "Pilot household 1"
    assert this["active_days"] == (2 if today.weekday() else 1)
    assert this["messages"] == {"audio": 2, "text": 1, "image": 1, "button": 1, "command": 0}
    assert this["records"] == {"voice_or_text": 1, "screenshot": 1}
    assert this["decisions"] == {"confirm": 1, "correct": 1, "reject": 1, "undone": 1}
    assert this["dues"] == {"spoken": 1, "paid": 1, "paid_by_due_date": 1, "reminded": 1}
    assert this["failures"] == {"amount_unclear": 1, "invalid_audio": 1}
    assert this["consented"] and this["reminders_opted_in"] and not this["stopped_now"]
    printed = json.dumps(rows, ensure_ascii=False)
    assert LABEL not in printed and "दूधवाला" not in printed and "120000" not in printed


def test_only_pilot_households_appear_and_the_owner_is_never_named(household) -> None:
    owner = household.session.get(User, LOCAL_USER_ID)
    assert [
        row["household"] for row in report.weekly(household.session, today=today_ist(), weeks=1)
    ] == ["Pilot household 1"]
    owner.pilot = True
    household.session.get(User, household.user_id).pilot = False  # erased households drop out
    household.session.commit()
    rows = report.weekly(household.session, today=today_ist(), weeks=1)
    assert [row["household"] for row in rows] == ["owner"]
    assert owner.display_name not in json.dumps(rows)
    assert household.session.scalars(select(User.id).where(User.pilot.is_(True))).all() == [
        LOCAL_USER_ID
    ]
