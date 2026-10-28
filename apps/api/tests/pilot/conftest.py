import json
from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from finboy.core.clock import now_ist, today_ist
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.db.base import Base
from finboy.db.models import User
from finboy.db.models.ledger import (
    Commitment,
    EmailSource,
    ExtractionCache,
    ReviewDecision,
    SourceEvent,
    Transaction,
    TransactionRevision,
)
from finboy.db.models.mail import ImportRun
from finboy.db.models.whatsapp import (
    WhatsAppBinding,
    WhatsAppDelivery,
    WhatsAppPrompt,
    WhatsAppReceipt,
)
from finboy.services.speech.models import SynthesizedAudio
from finboy.services.ux.state import TaskError, data_version
from finboy.services.whatsapp import pilot
from finboy.services.whatsapp.config import ChannelConfig, channel_config
from finboy.services.whatsapp.events import InboundQuestion
from sqlalchemy import JSON, MetaData, create_engine, event
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def pilot_factory() -> Iterator[sessionmaker[Session]]:
    """SQLite is a unit-test double only; PostgreSQL remains the sole runtime store."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if (
                isinstance(column.type, ARRAY | JSONB)
                and "sqlite" not in column.type._variant_mapping
            ):
                column.type = column.type.with_variant(JSON(), "sqlite")
        copy = table.to_metadata(metadata)
        for column in copy.columns:
            if column.server_default and "::" in str(column.server_default.arg):
                column.server_default = None
    metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(User(id=LOCAL_USER_ID, display_name="Synthetic owner"))
    yield factory
    engine.dispose()


def make_household(session: Session, *, name: str = "Pilot household 1") -> UUID:
    user = User(id=uuid4(), display_name=name, pilot=True)
    session.add(user)
    session.flush()
    return user.id


def make_ledger(session: Session, user_id: UUID) -> dict[str, UUID]:
    """One synthetic record with every dependent row a household can accumulate."""
    transaction = Transaction(
        id=uuid4(),
        user_id=user_id,
        direction="out",
        kind="purchase",
        amount_minor=50000,
        currency="INR",
        merchant="Synthetic milk seller",
        category="groceries",
        occurred_at=now_ist(),
        confidence=Decimal("0.700"),
        confidence_factors={},
        status="needs_review",
        review_reason="low_confidence",
        fingerprint=uuid4().hex,
        user_locked_fields=[],
    )
    session.add(transaction)
    session.flush()
    run = ImportRun(id=uuid4(), user_id=user_id, mode="whatsapp_voice", status="completed")
    session.add(run)
    session.flush()
    source = EmailSource(
        id=uuid4(),
        user_id=user_id,
        import_run_id=run.id,
        source="whatsapp_voice",
        provider_message_id=uuid4().hex,
        content_sha256="a" * 64,
        sender_domain="whatsapp.invalid",
        subject_sha256="b" * 64,
        received_at=now_ist(),
        classification="unknown",
        processing_status="extracted",
    )
    session.add(source)
    session.flush()
    source_event = SourceEvent(
        id=uuid4(),
        user_id=user_id,
        email_source_id=source.id,
        transaction_id=transaction.id,
        event_type="debit",
        amount_minor=50000,
        currency="INR",
        extraction_method="rule",
        extractor_id="test",
        evidence={},
        field_confidence={},
    )
    commitment = Commitment(
        id=uuid4(),
        user_id=user_id,
        kind="loan",
        label="Synthetic group instalment",
        amount_minor=120000,
        due_date=(now_ist() + timedelta(days=5)).date(),
        status="pending",
        confidence=Decimal("1.000"),
    )
    decision = ReviewDecision(
        id=uuid4(),
        user_id=user_id,
        transaction_id=transaction.id,
        action="confirm",
        before_state={},
        after_state={},
        result_version="1:2026-10-26",
    )
    revision = TransactionRevision(
        id=uuid4(),
        transaction_id=transaction.id,
        field="status",
        old_value="needs_review",
        new_value="confirmed",
        changed_by="user",
        reason="test",
    )
    session.add_all([source_event, commitment, decision, revision])
    session.flush()
    binding = WhatsAppBinding(
        id=uuid4(),
        user_id=user_id,
        sender_hash=uuid4().hex,
        enabled=True,
        language="hi",
        last_inbound_at=datetime.now(UTC),
    )
    session.add(binding)
    session.flush()
    receipt = WhatsAppReceipt(
        id=uuid4(),
        binding_id=binding.id,
        inbound_message_id="wamid." + uuid4().hex,
        content_hash="c" * 64,
        kind="audio",
        state="completed",
        provider_at=datetime.now(UTC),
    )
    session.add(receipt)
    session.flush()
    session.add_all(
        [
            WhatsAppDelivery(id=uuid4(), receipt_id=receipt.id, kind="interactive", state="sent"),
            WhatsAppPrompt(
                id=uuid4(),
                binding_id=binding.id,
                user_id=user_id,
                purpose="confirm",
                transaction_id=transaction.id,
                fingerprint="d" * 64,
                state="open",
                expires_at=datetime.now(UTC) + timedelta(days=7),
            ),
            ExtractionCache(id=uuid4(), cache_key="household:" + uuid4().hex, result={}),
        ]
    )
    session.flush()
    return {"transaction": transaction.id, "binding": binding.id, "commitment": commitment.id}


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
        self.obligation_error: TaskError | None = None
        self.self_serve = False  # True: a household that joined by itself
        self.client = MagicMock()
        self.client.upload_audio.return_value = "4321"
        monkeypatch.setattr(
            pilot.speech, "synthesize_speech", lambda **_: SynthesizedAudio(b"synthetic mp3")
        )
        monkeypatch.setattr(pilot.decisions, "decide", self.decide)
        monkeypatch.setattr(pilot.decisions, "undo_decision", self.undo)
        # The real versioned paths take PostgreSQL advisory locks: tests/pilot/test_postgres.py.
        monkeypatch.setattr(pilot, "correct_obligation", self.correct_obligation)

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

    def correct_obligation(self, session, *, user_id, obligation_id, request):
        assert user_id == self.user_id
        assert request.expected_version == data_version(session, user_id)
        if self.obligation_error:
            session.rollback()
            raise self.obligation_error
        payment = session.get(Transaction, request.paid_transaction_id)
        row = session.get(Commitment, obligation_id)
        assert request.status == "paid" and payment.status == "confirmed"
        assert (payment.direction, payment.amount_minor) == ("out", row.amount_minor)
        row.status, row.paid_transaction_id = "paid", payment.id
        session.commit()

    def undo(self, session, *, user_id, transaction_id, decision_id, expected_version):
        if self.undo_error:
            session.rollback()
            raise self.undo_error
        session.get(Transaction, transaction_id).status = "needs_review"
        session.commit()

    def record(self, *, amount: int = 50000, out: bool = True) -> UUID:
        # SQLite drops timezone information; noon UTC stays on the fixture's business day
        # under both the UTC CI runner and the IST development host, including demo dates.
        occurred_at = datetime.combine(today_ist(), time(12), UTC)
        row = Transaction(
            id=uuid4(),
            user_id=self.user_id,
            direction="out" if out else "in",
            kind="purchase" if out else "income_other",
            amount_minor=amount,
            currency="INR",
            merchant="दूधवाला",
            category="groceries" if out else "govt_benefit",
            occurred_at=occurred_at,
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
            self_serve=self.self_serve,
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
