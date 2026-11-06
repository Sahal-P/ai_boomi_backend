"""Chats and memories leave with the household's data and come with its export."""

from datetime import UTC, datetime

from finboy.core.config import LOCAL_USER_ID
from finboy.services.accounts.households import remove_household_data
from finboy.services.advisor import history, memory
from finboy.services.ux.privacy import export_records

from .support import OTHER_USER


def keep(session, user_id) -> None:
    history.save_turn(
        session,
        user_id=user_id,
        channel="whatsapp",
        thread=None,
        question="Food this month?",
        answer="Food this month is ₹4,200.",
        language="en",
        tool_names=["category_spending"],
        now=datetime.now(UTC),
    )
    memory.remember(session, user_id, "goal", "Saving for a bike", "whatsapp", 80)
    session.commit()


def test_erasure_removes_chats_and_memories_of_that_household_only(session) -> None:
    keep(session, LOCAL_USER_ID)
    keep(session, OTHER_USER)
    counts = remove_household_data(session, LOCAL_USER_ID)
    session.commit()
    assert (counts["advisor_messages"], counts["advisor_threads"]) == (2, 1)
    assert counts["household_memories"] == 1
    assert history.threads(session, LOCAL_USER_ID) == []
    assert len(history.threads(session, OTHER_USER)) == 1
    assert [row.text for row in memory.listed(session, OTHER_USER)] == ["Saving for a bike"]


def test_the_export_carries_the_households_chats_and_memories(session) -> None:
    keep(session, LOCAL_USER_ID)
    keep(session, OTHER_USER)
    exported = export_records(session, user_id=LOCAL_USER_ID)
    assert [item["text"] for item in exported["memories"]] == ["Saving for a bike"]
    assert len(exported["chats"]) == 1
    assert [row["role"] for row in exported["chats"][0]["messages"]] == ["user", "assistant"]
