"""The advisor's tables on the real schema (migrations 0015_advisor, 0016_knowledge and
0017_coach)."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from finboy.core.clock import IST, today_ist
from finboy.core.config import Settings
from finboy.db.models import User
from finboy.db.models.advisor import (
    AdvisorMessage,
    AdvisorNudge,
    AdvisorThread,
    HouseholdMemory,
    KnowledgeEmbedding,
)
from finboy.db.models.ledger import Transaction
from finboy.db.models.money import Budget
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppCheckin
from finboy.db.session import build_engine
from finboy.services.accounts.households import remove_household_data
from finboy.services.advisor import coach, embeddings, history, knowledge, memory
from finboy.services.whatsapp import coach as whatsapp_coach
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import Status
from finboy.services.whatsapp.receipts import admit
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .support import ConceptEmbedder

pytestmark = pytest.mark.integration


@pytest.fixture
def session() -> Iterator[Session]:
    settings = Settings()
    url = make_url(settings.database_url.get_secret_value())
    if settings.environment == "production" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Integration tests require a local disposable database")
    engine = build_engine(settings)
    with engine.connect() as connection, connection.begin() as transaction:
        with Session(bind=connection, join_transaction_mode="create_savepoint") as value:
            yield value
        transaction.rollback()
    engine.dispose()


def household(session: Session) -> User:
    user = User(id=uuid4(), display_name="Synthetic advisor household")
    session.add(user)
    session.flush()
    return user


def test_memories_are_kept_once_and_capped(session: Session) -> None:
    user = household(session)
    assert user.memory_enabled is True or session.get(User, user.id).memory_enabled is True
    first = memory.remember(session, user.id, "goal", "Saving for a bike", "web", 2)
    again = memory.remember(session, user.id, "goal", "saving for a BIKE", "whatsapp", 2)
    memory.remember(session, user.id, "person", "Ramesh is the milkman", "web", 2)
    memory.remember(session, user.id, "note", "Worried about school fees", "web", 2)
    session.flush()
    assert first is not None and again is not None and first.id == again.id
    texts = [row.text for row in memory.listed(session, user.id)]
    assert len(texts) == 2 and "Worried about school fees" in texts


def test_the_schema_refuses_what_the_service_never_writes(session: Session) -> None:
    user = household(session)
    for row in (
        HouseholdMemory(user_id=user.id, kind="secret", text="x", text_key="x", source="web"),
        HouseholdMemory(
            user_id=user.id, kind="note", text="x" * 301, text_key="long", source="web"
        ),
    ):
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(row)
            session.flush()


def test_chats_keep_tool_names_and_go_with_the_household(session: Session) -> None:
    user = household(session)
    thread = history.save_turn(
        session,
        user_id=user.id,
        channel="whatsapp",
        thread=None,
        question="Food this month?",
        answer="Food this month is ₹4,200.",
        language="en",
        tool_names=["category_spending", "category_spending", "find_payments"],
        now=datetime.now(UTC),
    )
    memory.remember(session, user.id, "goal", "Saving for a bike", "whatsapp", 80)
    session.flush()
    saved = session.scalar(
        select(AdvisorMessage.tool_names).where(
            AdvisorMessage.thread_id == thread.id, AdvisorMessage.role == "assistant"
        )
    )
    assert saved == ["category_spending", "find_payments"]
    counts = remove_household_data(session, user.id)
    assert (counts["advisor_threads"], counts["household_memories"]) == (1, 1)
    remaining = session.scalar(
        select(func.count()).select_from(AdvisorThread).where(AdvisorThread.user_id == user.id)
    )
    assert remaining == 0


def embedding_settings() -> Settings:
    return Settings().model_copy(
        update={
            "openai_api_key": SecretStr("sk-synthetic-test-key"),
            "openai_embedding_model": "synthetic-embedding",
            "advisor_embedding_dimensions": 64,
            "advisor_memory_prompt": 12,
        }
    )


def test_memory_embeddings_round_trip_as_real_arrays(session: Session, monkeypatch) -> None:
    embedder = ConceptEmbedder({"bike": 0, "motorcycle": 0})
    monkeypatch.setattr(embeddings, "embed", embedder)
    user = household(session)
    memory.remember(session, user.id, "goal", "Saving for a bike by March", "web", 300)
    for number in range(20):
        memory.remember(session, user.id, "note", f"Fact number {number}", "web", 300)
    session.commit()  # releases the savepoint; the outer transaction is still rolled back
    chosen = memory.recall(session, user.id, "how is my motorcycle plan", embedding_settings())
    assert len(chosen) == 12 and "Saving for a bike by March" in [row.text for row in chosen]
    stored = session.scalar(
        select(HouseholdMemory.embedding).where(
            HouseholdMemory.user_id == user.id, HouseholdMemory.kind == "goal"
        )
    )
    assert stored is not None and len(stored) == 64 and stored[0] == pytest.approx(1.0)
    memory.recall(session, user.id, "anything else", embedding_settings())
    assert embedder.calls[1] == ["anything else"]


def test_guide_embeddings_are_cached_once_per_model_and_size(session: Session, monkeypatch):
    embedder = ConceptEmbedder({"emergency": 0, "loan": 1})
    monkeypatch.setattr(embeddings, "embed", embedder)
    guides = knowledge.library()
    first = knowledge.vectors(guides, session, embedding_settings())
    again = knowledge.vectors(guides, session, embedding_settings())
    assert len(embedder.calls) == 1 and set(first) == set(again) == {g.id for g in guides}
    assert again["emergency-fund"] == pytest.approx(first["emergency-fund"], abs=1e-6)
    rows = session.scalar(
        select(func.count())
        .select_from(KnowledgeEmbedding)
        .where(KnowledgeEmbedding.model == "synthetic-embedding")
    )
    assert rows == len(guides)


def test_past_chats_are_searched_within_the_household(session: Session) -> None:
    user, other = household(session), household(session)

    def chat(owner: User, question: str) -> AdvisorThread:
        return history.save_turn(
            session,
            user_id=owner.id,
            channel="web",
            thread=None,
            question=question,
            answer="Compare the rate first",
            language="en",
            tool_names=[],
            now=datetime.now(UTC),
        )

    gold = chat(user, "Is a gold loan wise for the wedding?")
    chat(user, "How much did I spend on food?")
    chat(other, "gold loan for my shop")
    session.flush()
    hits = history.search(session, user.id, "that gold loan")
    assert [hit.thread_id for hit in hits] == [gold.id]


COACH_CONFIG = ChannelConfig(
    "synthetic-app-secret",
    "synthetic-verify",
    "synthetic-access",
    "12345678",
    "87654321",
    "v26.0",
    b"synthetic-hash-key",
    {},
)
COACH_NUMBER = "919000000123"


def coached_binding(session: Session) -> WhatsAppBinding:
    now = datetime.now(UTC)
    user = User(id=uuid4(), display_name="Synthetic coached household", joined_via="whatsapp")
    session.add(user)
    session.flush()
    binding = WhatsAppBinding(
        id=uuid4(),
        user_id=user.id,
        sender_hash=COACH_CONFIG.digest("sender", COACH_NUMBER),
        enabled=True,
        consented_at=now,
        coach_opt_in_at=now,
        last_inbound_at=now,
    )
    session.add(binding)
    session.flush()
    return binding


def nudge(kind: str, key: str) -> coach.Nudge:
    return coach.Nudge(kind, key, "warning", coach.GoalDetail(500000, 0, 7))  # type: ignore[arg-type]


def test_coach_nudges_go_once_per_period_and_once_a_day(session: Session) -> None:
    binding = coached_binding(session)
    today = today_ist()

    def due_today(day: date = today) -> bool:
        return binding.id in [row.id for row, _ in whatsapp_coach.due(session, day)]

    assert due_today()
    first = whatsapp_coach.claim(
        session, COACH_CONFIG, binding, nudge("budget_near", "x:food"), today, "message"
    )
    assert first is not None and not due_today(), "one a day"
    assert (
        whatsapp_coach.claim(
            session, COACH_CONFIG, binding, nudge("due_soon", "y"), today, "message"
        )
        is None
    )
    tomorrow = today + timedelta(days=1)
    assert due_today(tomorrow)
    assert (
        whatsapp_coach.claim(
            session, COACH_CONFIG, binding, nudge("budget_near", "x:food"), tomorrow, "message"
        )
        is None
    ), "never the same nudge twice"
    second = whatsapp_coach.claim(
        session, COACH_CONFIG, binding, nudge("due_soon", "y"), tomorrow, "template"
    )
    assert second is not None and len(second.period_key) == 64
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            AdvisorNudge(
                binding_id=binding.id,
                user_id=binding.user_id,
                kind="promotion",
                period_key="z" * 64,
                day=today + timedelta(days=2),
                via="message",
                state="sending",
            )
        )
        session.flush()


def test_a_check_in_today_counts_as_the_days_message(session: Session) -> None:
    binding = coached_binding(session)
    session.add(
        WhatsAppCheckin(binding_id=binding.id, month=today_ist().replace(day=1), state="sent")
    )
    session.flush()
    assert binding.id not in [row.id for row, _ in whatsapp_coach.due(session, today_ist())]


def test_delivery_status_reaches_the_nudge_and_erasure_removes_it(session: Session) -> None:
    binding = coached_binding(session)
    row = whatsapp_coach.claim(
        session, COACH_CONFIG, binding, nudge("income_in", "2026-11"), today_ist(), "template"
    )
    assert row is not None
    row.state, row.outbound_message_id = "sent", "wamid.coach.synthetic"
    session.commit()
    status = Status(id="wamid.coach.synthetic", status="read", recipient_id=COACH_NUMBER)
    admit(session, COACH_CONFIG, [], [status.model_copy(update={"recipient_id": "919000000099"})])
    session.expire_all()
    assert session.get(AdvisorNudge, row.id).provider_status is None, "only its own number"
    admit(session, COACH_CONFIG, [], [status])
    session.expire_all()
    assert session.get(AdvisorNudge, row.id).provider_status == "read"
    counts = remove_household_data(session, binding.user_id)
    assert counts["advisor_nudges"] == 1
    assert session.scalar(select(func.count()).select_from(AdvisorNudge)) == 0


def test_the_timer_nudges_a_household_from_its_real_records(session: Session) -> None:
    """The whole job on PostgreSQL: the real engine reads, the claim, the chat. Only Meta is
    faked, and there is no model key, so the code-written message goes."""
    today = today_ist()
    now = datetime.combine(today, time(9), IST)
    user = User(id=uuid4(), display_name="Synthetic pilot household", pilot=True)
    session.add(user)
    session.flush()
    binding = WhatsAppBinding(
        id=uuid4(),
        user_id=user.id,
        sender_hash=COACH_CONFIG.digest("sender", COACH_NUMBER),
        enabled=True,
        language="en",
        consented_at=now,
        coach_opt_in_at=now,
        last_inbound_at=now - timedelta(hours=1),
    )
    session.add_all([binding, Budget(user_id=user.id, category="food_dining", limit_minor=300000)])
    for amount in (160000, 100000):
        session.add(
            Transaction(
                id=uuid4(),
                user_id=user.id,
                direction="out",
                kind="purchase",
                amount_minor=amount,
                merchant="Synthetic canteen",
                category="food_dining",
                occurred_at=datetime.combine(today.replace(day=1), time(13), IST),
                confidence=Decimal("0.950"),
                confidence_factors={},
                status="confirmed",
                fingerprint=uuid4().hex,
                user_locked_fields=[],
            )
        )
    session.commit()
    settings = Settings().model_copy(
        update={"advisor_enabled": True, "coach_enabled": True, "openai_api_key": None}
    )
    config = replace(COACH_CONFIG, allowlist={COACH_NUMBER: user.id})
    factory = sessionmaker(
        bind=session.connection(), join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    client = MagicMock()
    client.send_buttons.return_value = "wamid.coach.engine"
    counts = whatsapp_coach.send_nudges(factory, settings, config, client, now)
    assert counts["sent"] == 1, counts
    text = client.send_buttons.call_args.kwargs["text"]
    assert text.startswith("🟡 Food & dining: ₹2,600 of your ₹3,000 budget spent, ₹400 left")
    session.expire_all()
    row = session.scalar(select(AdvisorNudge).where(AdvisorNudge.user_id == user.id))
    assert row is not None and (row.kind, row.state) == ("budget_near", "sent")
    said = session.scalars(select(AdvisorMessage.text).where(AdvisorMessage.user_id == user.id))
    assert list(said) == [text]
    assert whatsapp_coach.send_nudges(factory, settings, config, client, now) == {
        "sent": 0,
        "failed": 0,
        "unknown": 0,
        "skipped": 0,
        "quiet": 0,
    }, "one a day"
