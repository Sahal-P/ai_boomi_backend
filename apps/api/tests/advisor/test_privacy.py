"""Chats and memories leave with the household's data and come with its export."""

from datetime import UTC, date, datetime
from uuid import uuid4

from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.advisor import AdvisorNudge
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.services.accounts.households import remove_household_data
from finboy.services.advisor import history, memory
from finboy.services.ux.privacy import export_records
from sqlalchemy import select

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


def test_erasure_removes_the_coachs_nudges_and_the_export_keeps_their_words(session) -> None:
    """Phase 3: the claim rows go with the household; a sent nudge's words are in its chat."""
    for user_id in (LOCAL_USER_ID, OTHER_USER):
        binding = WhatsAppBinding(
            id=uuid4(),
            user_id=user_id,
            sender_hash=uuid4().hex,
            enabled=True,
            last_inbound_at=datetime.now(UTC),
        )
        session.add(binding)
        session.flush()
        session.add(
            AdvisorNudge(
                id=uuid4(),
                binding_id=binding.id,
                user_id=user_id,
                kind="budget_near",
                period_key="0" * 64,
                day=date(2026, 11, 18),
                via="message",
                state="sent",
            )
        )
        history.save_nudge(
            session,
            user_id=user_id,
            text="🟡 Food & dining: ₹4,200 of your ₹5,000 budget spent.",
            language="en",
            now=datetime.now(UTC),
        )
    session.commit()
    exported = export_records(session, user_id=LOCAL_USER_ID)
    [nudge_chat] = exported["chats"]
    assert [row["role"] for row in nudge_chat["messages"]] == ["assistant"]
    assert nudge_chat["channel"] == "whatsapp"
    counts = remove_household_data(session, LOCAL_USER_ID)
    session.commit()
    assert counts["advisor_nudges"] == 1
    assert [row.user_id for row in session.scalars(select(AdvisorNudge))] == [OTHER_USER]
