"""WhatsApp with the advisor on: questions and chat for every household, memory commands."""

import pytest
from finboy.core.clock import today_ist
from finboy.services.advisor import memory
from finboy.services.assistant.models import AnswerSource, AssistantAnswer, MemoryChange
from finboy.services.whatsapp import hindi, pilot
from finboy.services.whatsapp.capture import Capture
from finboy.services.whatsapp.statement import Statement


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


def milkman(monkeypatch, household, *, fact: str | None = "Ramesh is the milkman") -> None:
    """A diary entry whose reading states a lasting fact, recorded without the pipeline."""
    spoken = Statement(
        "spent",
        6000,
        "Ramesh",
        "cash",
        today_ist(),
        "groceries",
        remember=fact,
        remember_kind="person",
    )
    monkeypatch.setattr(pilot.statement, "read_statements", lambda *_args: [spoken])
    monkeypatch.setattr(
        pilot.capture,
        "record_voice",
        lambda *_args, **_kwargs: Capture("saved", 6000, "Ramesh", household.record()),
    )


def test_a_diary_entry_teaches_a_lasting_fact_once(household, monkeypatch):
    household.settings = household.settings.model_copy(update={"advisor_enabled": True})
    milkman(monkeypatch, household)
    assert household.say("Ramesh doodhwale ko 60 diye") is None
    first = household.texts()[-1]
    assert first.startswith("✅") and first.endswith("\n\n" + hindi.MEMORY_UPDATED)
    saved = memory.listed(household.session, household.user_id)
    assert [(row.kind, row.text, row.source) for row in saved] == [
        ("person", "Ramesh is the milkman", "whatsapp")
    ]
    assert household.say("Ramesh doodhwale ko 60 diye") is None
    assert hindi.MEMORY_UPDATED not in household.texts()[-1]  # known facts are not announced
    assert len(memory.listed(household.session, household.user_id)) == 1


def test_a_diary_fact_is_not_kept_with_memory_off_or_the_advisor_off(household, monkeypatch):
    milkman(monkeypatch, household)
    household.say("Ramesh doodhwale ko 60 diye")  # the advisor is off
    household.settings = household.settings.model_copy(update={"advisor_enabled": True})
    memory.set_enabled(household.session, household.user_id, False)
    household.session.commit()
    household.say("Ramesh doodhwale ko 60 diye")
    assert memory.listed(household.session, household.user_id) == []
    assert all(hindi.MEMORY_UPDATED not in text for text in household.texts())


def test_a_reply_from_the_guides_names_them_with_their_official_site(household, monkeypatch):
    household.settings = household.settings.model_copy(update={"advisor_enabled": True})

    def advise(_session, **_kwargs) -> AssistantAnswer:
        return AssistantAnswer(
            intent="advisor",
            policy="answer",
            display_text="पीएम-किसान में साल के ₹6,000 मिलते हैं।",
            speech_text="",
            speech_language="hi",
            facts=[],
            simulation=None,
            evidence_transactions=[],
            warnings=[],
            sources=[AnswerSource(id="pm-kisan", title="पीएम-किसान", url="https://pmkisan.gov.in")],
        )

    monkeypatch.setattr(pilot.advisor, "advise", advise)
    household.say("पीएम किसान का पैसा कब आता है?")
    assert household.texts()[-1] == (
        "पीएम-किसान में साल के ₹6,000 मिलते हैं।\n\n"
        + hindi.GUIDES.format(guides="पीएम-किसान https://pmkisan.gov.in")
    )
