"""The advisor's tables on the real schema (migration 0015_advisor)."""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from finboy.core.config import Settings
from finboy.db.models import User
from finboy.db.models.advisor import AdvisorMessage, AdvisorThread, HouseholdMemory
from finboy.db.session import build_engine
from finboy.services.accounts.households import remove_household_data
from finboy.services.advisor import history, memory
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
