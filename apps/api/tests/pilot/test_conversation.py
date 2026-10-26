import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from finboy.core.clock import now_ist
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.db.models.ledger import ReviewDecision, Transaction
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppPrompt, WhatsAppReceipt
from finboy.services.assistant.models import AssistantAnswer
from finboy.services.speech.models import SynthesizedAudio, Transcript
from finboy.services.ux.state import TaskError, data_version
from finboy.services.whatsapp import hindi, pilot, prompts
from finboy.services.whatsapp.capture import Capture
from finboy.services.whatsapp.config import ChannelConfig, channel_config
from finboy.services.whatsapp.events import InboundQuestion
from sqlalchemy import select

from .conftest import make_household


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        cors_origins=["http://localhost:3000"],
        environment="test",
        whatsapp_enabled=True,
        whatsapp_app_id="953180210789448",
        whatsapp_graph_api_version="v26.0",
        whatsapp_app_secret="synthetic-app-secret",
        whatsapp_verify_token="synthetic-verify",
        whatsapp_access_token="synthetic-access",
        whatsapp_phone_number_id="12345678",
        whatsapp_business_account_id="87654321",
        token_encryption_key="eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg=",
        whatsapp_sender_allowlist_json=json.dumps({"919000000001": str(LOCAL_USER_ID)}),
    )


@pytest.fixture
def channel(settings: Settings) -> ChannelConfig:
    return channel_config(settings)


class Household:
    """One pilot household's conversation with recording fakes for Meta, speech and decisions."""

    def __init__(self, factory, settings, channel, monkeypatch, *, consented: bool = True):
        self.session = factory()
        self.settings, self.channel = settings, channel
        self.user_id = make_household(self.session)
        self.binding = WhatsAppBinding(
            id=uuid4(),
            user_id=self.user_id,
            sender_hash=uuid4().hex,
            enabled=True,
            language="hi",
            consented_at=datetime.now(UTC) if consented else None,
            last_inbound_at=datetime.now(UTC),
        )
        self.session.add(self.binding)
        self.session.commit()
        self.sent: list[dict] = []
        self.decided: list = []
        self.undo_error: TaskError | None = None
        self.client = MagicMock()
        self.client.upload_audio.return_value = "4321"
        monkeypatch.setattr(
            pilot.speech, "synthesize_speech", lambda **_: SynthesizedAudio(b"synthetic mp3")
        )
        monkeypatch.setattr(pilot.decisions, "decide", self.decide)
        monkeypatch.setattr(pilot.decisions, "undo_decision", self.undo)

    def reply(self, _session, _config, _client, _receipt, _question, **kwargs) -> bool:
        self.sent.append(kwargs)
        return True

    def decide(self, session, *, user_id, transaction_id, request):
        assert user_id == self.user_id
        assert request.expected_version == data_version(session, user_id)
        self.decided.append(request)
        row = session.get(Transaction, transaction_id)
        if request.action in {"confirm", "reject"}:
            row.status = "confirmed" if request.action == "confirm" else "rejected"
        if request.correction is not None:
            row.amount_minor = request.correction.amount_minor
        decision = ReviewDecision(
            id=uuid4(),
            user_id=user_id,
            transaction_id=transaction_id,
            action=request.action,
            before_state={},
            after_state={},
            result_version="synthetic",
        )
        session.add(decision)
        session.commit()
        return SimpleNamespace(decision_id=decision.id)

    def undo(self, session, *, user_id, transaction_id, decision_id, expected_version):
        if self.undo_error:
            session.rollback()
            raise self.undo_error
        session.get(Transaction, transaction_id).status = "needs_review"
        session.commit()

    def record(self, *, amount: int = 50000, out: bool = True) -> UUID:
        row = Transaction(
            id=uuid4(),
            user_id=self.user_id,
            direction="out" if out else "in",
            kind="purchase" if out else "income_other",
            amount_minor=amount,
            currency="INR",
            merchant="दूधवाला",
            category="groceries" if out else "govt_benefit",
            occurred_at=now_ist(),
            confidence=Decimal("0.700"),
            confidence_factors={},
            status="needs_review",
            review_reason="low_confidence",
            fingerprint=uuid4().hex,
            user_locked_fields=[],
        )
        self.session.add(row)
        self.session.commit()
        return row.id

    def run(self, question: InboundQuestion, *, binding: WhatsAppBinding | None = None):
        receipt = WhatsAppReceipt(id=uuid4(), binding_id=self.binding.id, state="processing")
        conversation = pilot.Conversation(
            self.session,
            self.settings,
            self.channel,
            self.client,
            receipt,
            question,
            binding or self.binding,
            self.reply,
        )
        return pilot.handle(conversation)

    def say(self, text: str, kind: str = "text"):
        return self.run(
            InboundQuestion(
                "wamid." + uuid4().hex,
                "919000000002",
                datetime.now(UTC),
                kind,
                text=text,
                media_id="1234",
                mime_type="audio/ogg",
            )
        )

    def card(self, transaction_id: UUID):
        receipt = WhatsAppReceipt(id=uuid4(), binding_id=self.binding.id, state="processing")
        question = InboundQuestion("wamid.card", "919000000002", datetime.now(UTC), "image")
        conversation = pilot.Conversation(
            self.session,
            self.settings,
            self.channel,
            self.client,
            receipt,
            question,
            self.binding,
            self.reply,
        )
        return pilot.offer_card(conversation, transaction_id)

    def buttons(self) -> list[tuple[str, str]]:
        return next(item["buttons"] for item in reversed(self.sent) if item.get("buttons"))

    def tap(
        self, choice: str, *, binding: WhatsAppBinding | None = None, button: str | None = None
    ):
        if button is None:
            button = next(key for key, _ in self.buttons() if key.endswith(":" + choice))
        return self.run(
            InboundQuestion(
                "wamid." + uuid4().hex,
                "919000000002",
                datetime.now(UTC),
                "button",
                button_id=button,
            ),
            binding=binding,
        )

    def texts(self) -> list[str]:
        return [item["text"] for item in self.sent if item.get("text")]

    def spoke(self) -> int:
        return sum(1 for item in self.sent if item.get("media_id"))


@pytest.fixture
def household(pilot_factory, settings, channel, monkeypatch) -> Household:
    return Household(pilot_factory, settings, channel, monkeypatch)


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
