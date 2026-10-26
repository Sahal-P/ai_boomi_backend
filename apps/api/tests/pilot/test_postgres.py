"""A pilot household's whole conversation on PostgreSQL: real admission, processor, decisions,
import pipeline, obligations and engine. Only Meta, speech and the statement model are faked."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from finboy.core.clock import today_ist
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.core.errors import ProviderUnavailable
from finboy.db.models import User
from finboy.db.models.ledger import Commitment, EmailSource, ReviewDecision, Transaction
from finboy.db.models.whatsapp import (
    WhatsAppBinding,
    WhatsAppDelivery,
    WhatsAppPrompt,
    WhatsAppReceipt,
    WhatsAppReminder,
)
from finboy.db.session import build_engine
from finboy.services.money.engine import PeriodSpec, money_summary
from finboy.services.pilot import households, report
from finboy.services.whatsapp import hindi, pilot, processor
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion, Status
from finboy.services.whatsapp.receipts import admit
from finboy.services.whatsapp.statement import Statement
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration
NUMBER = "919000000077"  # synthetic; never a real recipient
LABEL = "समूह की किस्त"


@pytest.fixture
def pg() -> Iterator[sessionmaker[Session]]:
    settings = Settings()
    url = make_url(settings.database_url.get_secret_value())
    if (
        settings.environment == "production"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database not in {"finboy_pilot", "finboy_test"}
    ):
        pytest.fail("Pilot integration tests require the disposable local finboy_pilot database")
    engine = build_engine(settings)
    try:
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        engine.dispose()


class Meta:
    """Records what would reach WhatsApp; never sends."""

    log: list[dict] = []

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def send(self, recipient: str, *, text=None, media_id=None) -> str:
        self.log.append({"to": recipient, "text": text, "media_id": media_id})
        return "wamid.out." + uuid4().hex

    def send_buttons(self, recipient: str, *, text: str, buttons) -> str:
        self.log.append({"to": recipient, "text": text, "buttons": list(buttons)})
        return "wamid.out." + uuid4().hex

    def close(self) -> None:
        pass


class Phone:
    def __init__(self, pg, settings: Settings, config: ChannelConfig, user_id: UUID) -> None:
        self.pg, self.settings, self.config, self.user_id = pg, settings, config, user_id

    def send(self, question: InboundQuestion) -> list[dict]:
        before = len(Meta.log)
        with self.pg() as session:
            admitted = admit(session, self.config, [question], [])
        assert len(admitted) == 1
        processor.process_question(
            self.pg, self.settings, self.config, admitted[0].receipt_id, admitted[0].question
        )
        return Meta.log[before:]

    def say(self, text: str) -> list[dict]:
        return self.send(
            InboundQuestion("wamid." + uuid4().hex, NUMBER, datetime.now(UTC), "text", text)
        )

    def tap(self, replies: list[dict], choice: str) -> list[dict]:
        button = next(
            key
            for reply in reversed(replies)
            for key, _ in reply.get("buttons", [])
            if key.endswith(":" + choice)
        )
        return self.send(
            InboundQuestion(
                "wamid." + uuid4().hex, NUMBER, datetime.now(UTC), "button", button_id=button
            )
        )

    def receipt_errors(self) -> list[str | None]:
        with self.pg() as session:
            return list(
                session.scalars(
                    select(WhatsAppReceipt.error_code)
                    .join(WhatsAppBinding, WhatsAppBinding.id == WhatsAppReceipt.binding_id)
                    .where(WhatsAppBinding.user_id == self.user_id)
                    .order_by(WhatsAppReceipt.received_at)
                )
            )


@pytest.fixture
def phone(pg, channel: ChannelConfig, monkeypatch) -> Iterator[Phone]:
    settings = Settings()
    with pg() as session:
        user_id = households.enroll(session).id
    Meta.log = []
    monkeypatch.setattr(processor, "MetaClient", Meta)

    def silent(**_kwargs):
        raise ProviderUnavailable("synthetic")

    monkeypatch.setattr(pilot.speech, "synthesize_speech", silent)
    today = today_ist()
    said = {
        "दूधवाले को 500 नकद दिए": Statement("spent", 50000, "दूधवाले", "cash", today, "groceries"),
        "समूह की किस्त 1200, हर महीने": Statement(
            "due", 120000, category="loan_emi", due_date=today, label=LABEL
        ),
    }
    monkeypatch.setattr(pilot.statement, "read_statement", lambda text, *_args: said[text])
    try:
        yield Phone(pg, settings, replace(channel, allowlist={NUMBER: user_id}), user_id)
    finally:
        with pg() as session:
            households.erase(session, user_id)


def test_a_pilot_household_end_to_end(pg, phone: Phone) -> None:
    (consent,) = phone.say("नमस्ते")
    assert consent["text"] == hindi.CONSENT and consent["to"] == NUMBER
    assert phone.tap([consent], "agree")[0]["text"] == hindi.WELCOME

    # Spoken money lands in review through the real pipeline, then हाँ confirms it.
    (card,) = phone.say("दूधवाले को 500 नकद दिए")
    assert "₹500 दिए" in card["text"] and "👤 दूधवाले" in card["text"]
    with pg() as session:
        first = session.scalars(
            select(Transaction).where(Transaction.user_id == phone.user_id)
        ).one()
        source = session.scalars(
            select(EmailSource).where(EmailSource.user_id == phone.user_id)
        ).one()
    assert (first.status, first.category, first.direction) == ("needs_review", "groceries", "out")
    assert source.source == "whatsapp_voice"
    (done,) = phone.tap([card], "yes")
    assert done["text"].startswith("✅ जोड़ दिया: ₹500 दिए")

    # The same purchase again is a second record, never merged into the first.
    (again,) = phone.say("दूधवाले को 500 नकद दिए")
    (rejected,) = phone.tap([again], "no")
    assert rejected["text"] == hindi.REJECTED
    (undone,) = phone.tap([rejected], "undo")
    assert undone["text"].startswith(hindi.UNDONE)
    with pg() as session:
        rows = session.scalars(
            select(Transaction).where(Transaction.user_id == phone.user_id)
        ).all()
        assert sorted(row.status for row in rows) == ["confirmed", "needs_review"]
        assert all(row.merged_into_id is None for row in rows)
        undone_count = session.scalar(
            select(func.count())
            .select_from(ReviewDecision)
            .where(ReviewDecision.user_id == phone.user_id, ReviewDecision.undone_at.is_not(None))
        )
        assert undone_count == 1

    # A spoken due waits as pending, then counts after हाँ; reminders are opted into.
    (due_card,) = phone.say("समूह की किस्त 1200, हर महीने")
    with pg() as session:
        due = session.scalars(select(Commitment).where(Commitment.user_id == phone.user_id)).one()
        assert (due.status, due.kind) == ("pending", "loan")
        summary = money_summary(
            session,
            user_id=phone.user_id,
            period=PeriodSpec(kind="range", start_date=today_ist(), end_date=today_ist()),
        )
        assert summary.upcoming_commitments_minor == 0, "pending dues never count"
    (saved,) = phone.tap([due_card], "yes")
    assert hindi.REMIND_ASK in saved["text"]
    opted = phone.tap([saved], "remind")
    assert opted[0]["text"] == hindi.REMINDERS_ON
    # Without a template, the due today follows the very next reply as its own card, once.
    reminder = opted[-1]
    assert reminder["text"].startswith("📌 याद दिलाना") and "📅 आज, " in reminder["text"]
    assert [title for _, title in reminder["buttons"]] == [hindi.PAID, hindi.LATER]
    (week,) = phone.say("हिसाब")
    assert week["text"].startswith("📒 इस हफ़्ते का हिसाब") and "💸 गए: ₹500" in week["text"]
    assert "📌 आगे देना है: ₹1,200" in week["text"]

    # भर दिया records the instalment, confirms it and links it to the due.
    (paid,) = phone.tap([reminder], "paid")
    assert paid["text"] == hindi.paid_done(120000, LABEL) + "\n\n" + hindi.REPEAT_ASK
    with pg() as session:
        session.expire_all()
        due = session.get(Commitment, due.id)
        payment = session.get(Transaction, due.paid_transaction_id)
        assert (due.status, payment.status, payment.amount_minor) == ("paid", "confirmed", 120000)
        assert payment.category == "loan_emi"
        summary = money_summary(
            session,
            user_id=phone.user_id,
            period=PeriodSpec(kind="range", start_date=today_ist(), end_date=today_ist()),
        )
        assert summary.confirmed_outflows_minor == 170000
        assert summary.overdue_commitments_minor == summary.upcoming_commitments_minor == 0
    (following,) = phone.tap([paid], "again")
    assert following["text"].startswith("📌 याद रख लिया: ₹1,200")
    assert phone.tap([reminder], "paid")[0]["text"] == hindi.EXPIRED

    with pg() as session:
        kinds = session.scalars(
            select(WhatsAppDelivery.kind)
            .join(WhatsAppReceipt, WhatsAppReceipt.id == WhatsAppDelivery.receipt_id)
            .join(WhatsAppBinding, WhatsAppBinding.id == WhatsAppReceipt.binding_id)
            .where(WhatsAppBinding.user_id == phone.user_id)
        ).all()
        assert {"text", "interactive", "reminder"} <= set(kinds)
        (row,) = [
            row
            for row in report.weekly(session, today=today_ist(), weeks=1)
            if row["household"].startswith("Pilot household")
            and row["dues"]["paid"] == 1
            and row["decisions"]["undone"] == 1
        ]
        assert row["records"]["voice_or_text"] == 3 and row["messages"]["button"] >= 8
    assert phone.receipt_errors()[-1] == "prompt_expired"


def test_numbers_of_households_that_are_not_enrolled_are_ignored(
    pg, channel: ChannelConfig
) -> None:
    stranger = uuid4()
    unknown = replace(channel, allowlist={NUMBER: stranger})
    message = InboundQuestion("wamid." + uuid4().hex, NUMBER, datetime.now(UTC), "text", "500")
    with pg() as session:
        assert admit(session, unknown, [message], []) == []
        session.add(User(id=stranger, display_name="Not enrolled", pilot=False))
        session.commit()
        try:
            assert admit(session, unknown, [message], []) == []
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(WhatsAppBinding)
                    .where(WhatsAppBinding.user_id == stranger)
                )
                == 0
            )
        finally:
            session.delete(session.get(User, stranger))
            session.commit()


def test_template_statuses_reach_only_the_matching_households_reminder(
    pg, phone: Phone, channel: ChannelConfig
) -> None:
    (consent,) = phone.say("नमस्ते")
    phone.tap([consent], "agree")
    with pg() as session:
        binding = session.scalars(
            select(WhatsAppBinding).where(WhatsAppBinding.user_id == phone.user_id)
        ).one()
        due = Commitment(
            id=uuid4(),
            user_id=phone.user_id,
            kind="loan",
            label=LABEL,
            amount_minor=120000,
            due_date=today_ist(),
            status="upcoming",
            confidence=1,
            user_resolved=False,
        )
        session.add(due)
        session.flush()
        session.add(
            WhatsAppReminder(
                binding_id=binding.id,
                commitment_id=due.id,
                kind="due_day",
                state="sent",
                outbound_message_id="wamid.reminder.synthetic",
            )
        )
        session.commit()
        status = Status(id="wamid.reminder.synthetic", status="delivered", recipient_id=NUMBER)
        admit(
            session, phone.config, [], [status.model_copy(update={"recipient_id": "919000000099"})]
        )
        assert session.scalar(select(WhatsAppReminder.provider_status)) is None
        admit(session, phone.config, [], [status])
        admit(session, phone.config, [], [status.model_copy(update={"status": "sent"})])
        session.expire_all()
        assert session.scalar(select(WhatsAppReminder.provider_status)) == "delivered"
        prompts_open = session.scalar(
            select(func.count())
            .select_from(WhatsAppPrompt)
            .where(WhatsAppPrompt.user_id == phone.user_id, WhatsAppPrompt.state == "open")
        )
        assert prompts_open == 0


def test_erasure_leaves_nothing_of_the_household_and_never_touches_the_owner(
    pg, phone: Phone
) -> None:
    (consent,) = phone.say("नमस्ते")
    phone.tap([consent], "agree")
    phone.say("दूधवाले को 500 नकद दिए")
    with pg() as session:
        owner_records = session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.user_id == LOCAL_USER_ID)
        )
        households.erase(session, phone.user_id)
        for model in (Transaction, Commitment, EmailSource, ReviewDecision, WhatsAppBinding):
            assert (
                session.scalar(
                    select(func.count()).select_from(model).where(model.user_id == phone.user_id)
                )
                == 0
            )
        assert session.get(User, phone.user_id).pilot is False
        assert (
            session.scalar(
                select(func.count())
                .select_from(Transaction)
                .where(Transaction.user_id == LOCAL_USER_ID)
            )
            == owner_records
        )
