"""WhatsApp with the advisor on: questions and chat for every household, memory commands."""

import pytest
from finboy.services.advisor import memory
from finboy.services.assistant.models import AssistantAnswer, MemoryChange
from finboy.services.whatsapp import hindi, pilot


@pytest.fixture
def advised(household, monkeypatch) -> list[dict]:
    household.settings = household.settings.model_copy(update={"advisor_enabled": True})
    calls: list[dict] = []

    def advise(_session, **kwargs) -> AssistantAnswer:
        calls.append(kwargs)
        return AssistantAnswer(
            intent="advisor",
            policy="answer",
            display_text="इस हफ़्ते खाने पर ₹420 खर्च हुए।",
            speech_text="इस हफ़्ते खाने पर ₹420 खर्च हुए।",
            speech_language="hi",
            facts=[],
            simulation=None,
            evidence_transactions=[],
            warnings=[],
            memory_changes=[MemoryChange(action="saved", text="Saving for a bike")],
        )

    monkeypatch.setattr(pilot.advisor, "advise", advise)
    return calls


def test_a_question_goes_to_the_advisor_even_on_the_free_plan(household, advised, monkeypatch):
    household.self_serve = True
    monkeypatch.setattr(pilot.premium, "allowed", lambda _conversation: False)
    assert household.say("How much did I spend on food this week?") is None
    assert advised[0]["channel"] == "whatsapp" and advised[0]["display_style"] == "hi"
    assert household.texts() == ["इस हफ़्ते खाने पर ₹420 खर्च हुए।\n\n" + hindi.MEMORY_UPDATED]


def test_everyday_chat_reaches_the_advisor_instead_of_i_didnt_understand(household, advised):
    household.say("namaste")
    assert len(advised) == 1 and hindi.UNCLEAR not in household.texts()


def test_memory_off_and_forget_everything_work_without_the_model(household, advised):
    memory.remember(household.session, household.user_id, "goal", "Saving for a bike", "user", 80)
    household.session.commit()
    household.say("मेमोरी बंद")
    assert memory.enabled(household.session, household.user_id) is False
    household.say("memory on")
    assert memory.enabled(household.session, household.user_id) is True
    household.say("सब भूल जाओ")
    assert memory.listed(household.session, household.user_id) == []
    assert household.texts() == [hindi.MEMORY_OFF, hindi.MEMORY_ON, hindi.MEMORY_FORGOTTEN]
    assert advised == []


def test_with_the_advisor_off_nothing_changes(household, monkeypatch):
    called = []
    monkeypatch.setattr(pilot.advisor, "advise", lambda *_a, **_k: called.append(1))
    household.say("namaste")
    household.say("memory off")
    assert called == [] and hindi.UNCLEAR in household.texts()
