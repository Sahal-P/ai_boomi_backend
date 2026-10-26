from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from finboy.core.clock import now_ist
from finboy.core.config import LOCAL_USER_ID
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
