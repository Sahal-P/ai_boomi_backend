"""Long-term memory: lasting facts, one copy each, never secrets, the household in control."""

from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.advisor import HouseholdMemory
from finboy.services.advisor import memory
from finboy.services.advisor.memory import MemoryUpdate
from sqlalchemy import func, select

from .support import OTHER_USER


def update(
    action: str, *, ref: str | None = None, kind: str | None = None, text: str | None = None
):
    return MemoryUpdate(action=action, ref=ref, kind=kind, text=text)


def count(session, user_id=LOCAL_USER_ID) -> int:
    return session.scalar(
        select(func.count()).select_from(HouseholdMemory).where(HouseholdMemory.user_id == user_id)
    )


def test_secrets_are_never_kept_and_long_numbers_are_masked() -> None:
    assert memory.clean("My UPI PIN is 4321") is None
    assert memory.clean("OTP was 123456") is None
    assert memory.clean("मेरा पासवर्ड abc है") is None
    assert memory.clean("Account 123456789012 is for rent") == "Account [number] is for rent"
    assert memory.clean("PAN ABCDE1234F is in the file") == "PAN [id] is in the file"
    assert memory.clean("   ") is None
    assert memory.clean("x" * 301) is None


def test_the_same_fact_is_kept_once(session) -> None:
    first = memory.remember(session, LOCAL_USER_ID, "goal", "Saving for a bike", "web", 80)
    again = memory.remember(session, LOCAL_USER_ID, "goal", "saving  for a BIKE!", "web", 80)
    session.commit()
    assert first is not None and again is not None and first.id == again.id
    assert count(session) == 1


def test_a_full_memory_makes_room_from_the_oldest(session) -> None:
    for number in range(3):
        memory.remember(session, LOCAL_USER_ID, "note", f"Fact number {number}", "web", 3)
        session.commit()
    memory.remember(session, LOCAL_USER_ID, "note", "The newest fact", "web", 3)
    session.commit()
    texts = [row.text for row in memory.listed(session, LOCAL_USER_ID)]
    assert texts[0] == "The newest fact" and "Fact number 0" not in texts and len(texts) == 3


def test_the_model_updates_and_forgets_only_listed_memories(session) -> None:
    memory.remember(session, LOCAL_USER_ID, "goal", "Saving for a bike by March", "web", 80)
    memory.remember(session, OTHER_USER, "person", "Ravi is the landlord", "web", 80)
    session.commit()
    listing = memory.prompt_block(memory.listed(session, LOCAL_USER_ID))
    assert listing.block == "[m1] (goal) Saving for a bike by March"
    changes = memory.apply(
        session,
        LOCAL_USER_ID,
        [
            update("update", ref="m1", kind="goal", text="Saving for a bike by June"),
            update("forget", ref="m7"),  # not listed: ignored
            update("add", kind="person", text="Ramesh is the milkman"),
            update("add", kind="note", text="My card CVV is 123"),  # a secret: refused
        ],
        listing,
        "web",
        80,
    )
    session.commit()
    assert [(change.action, change.text) for change in changes] == [
        ("updated", "Saving for a bike by June"),
        ("saved", "Ramesh is the milkman"),
    ]
    later = memory.prompt_block(memory.listed(session, LOCAL_USER_ID))
    forgotten = memory.apply(session, LOCAL_USER_ID, [update("forget", ref="m2")], later, "web", 80)
    session.commit()
    assert [change.action for change in forgotten] == ["forgotten"]
    assert count(session) == 1 and count(session, OTHER_USER) == 1


def test_a_household_controls_its_memory(session) -> None:
    saved = memory.remember(session, LOCAL_USER_ID, "about", "Works as a teacher", "web", 80)
    session.commit()
    assert memory.edit(session, OTHER_USER, saved.id, "Works as a doctor") is None
    edited = memory.edit(session, LOCAL_USER_ID, saved.id, "Works as a head teacher")
    assert edited is not None and edited.text == "Works as a head teacher"
    assert memory.forget(session, OTHER_USER, saved.id) is False
    memory.set_enabled(session, LOCAL_USER_ID, False)
    session.commit()
    assert memory.enabled(session, LOCAL_USER_ID) is False
    assert memory.forget_all(session, LOCAL_USER_ID) == 1
