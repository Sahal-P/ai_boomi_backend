"""The advisor loop: tools, checked figures, chats, memory and the rules when the model fails."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from finboy.core.config import LOCAL_USER_ID
from finboy.core.errors import ProviderUnavailable
from finboy.core.logging import JsonFormatter
from finboy.db.models.advisor import AdvisorMessage, AdvisorThread, HouseholdMemory
from finboy.services.advisor import memory, service
from finboy.services.assistant.models import AssistantAnswer
from sqlalchemy import select

from .support import OTHER_USER, ask, call, reply


def whole(kind: str) -> dict:
    return {
        "kind": kind,
        "year": None,
        "month": None,
        "start_date": None,
        "end_date": None,
        "months": None,
    }


@pytest.fixture
def rules(monkeypatch):
    """The keyword-rules answer the advisor falls back to; records each call."""
    calls: list[dict] = []

    def answer_question(session, **kwargs) -> AssistantAnswer:
        calls.append(kwargs)
        return AssistantAnswer(
            intent="spending_query",
            policy="answer",
            display_text="Rules answer",
            speech_text="Rules answer",
            speech_language="en",
            facts=[],
            simulation=None,
            evidence_transactions=[],
            warnings=[],
        )

    monkeypatch.setattr(service.assistant, "answer_question", answer_question)
    return calls


def test_tools_then_a_checked_answer_saved_in_its_chat(session, settings, toolbox, scripted):
    model = scripted(
        [
            call("category_spending", {"period": whole("this_month"), "category": "food_dining"}),
            call(
                "find_payments",
                {
                    "period": whole("this_month"),
                    "payee": "Swiggy",
                    "category": None,
                    "direction": "out",
                    "limit": 5,
                },
                "call_2",
            ),
        ],
        reply(
            "You spent *₹4,200* on food this month; ₹770.50 of it on Swiggy.",
            follow_ups=["And last month?", "Set a food budget"],
        ),
    )
    answer = ask(session, settings, toolbox, "How much did I spend on food?")
    assert answer.intent == "advisor" and answer.policy == "answer"
    assert answer.display_text.startswith("You spent *₹4,200*")
    assert answer.follow_ups == ["And last month?", "Set a food budget"]
    assert len(answer.evidence_transactions) == 2 and answer.thread_id is not None
    assert answer.warnings == ["incomplete_coverage", "pending_review_items"]
    first, second = model.calls
    assert first["store"] is False and first["tool_choice"] == "auto"
    assert first["input"][0]["role"] == "system" and first["input"][-1]["content"] == (
        "How much did I spend on food?"
    )
    outputs = [item for item in second["input"] if item.get("type") == "function_call_output"]
    assert [item["call_id"] for item in outputs] == ["call_1", "call_2"]
    rows = session.scalars(select(AdvisorMessage).order_by(AdvisorMessage.created_at)).all()
    assert [(row.role, row.text) for row in rows] == [
        ("user", "How much did I spend on food?"),
        ("assistant", answer.display_text),
    ]
    assert sorted(rows[1].tool_names) == ["category_spending", "find_payments"]


def test_a_figure_finboy_does_not_have_gets_one_correction(session, settings, toolbox, scripted):
    model = scripted(
        reply("You can easily save ₹9,999 a month."),
        reply("Your food budget has ₹800 left this month."),
    )
    answer = ask(session, settings, toolbox, "Can I save more?")
    assert answer.display_text == "Your food budget has ₹800 left this month."
    correction = model.calls[1]["input"][-1]
    assert correction["role"] == "developer" and "9999" in correction["content"]


def test_still_unchecked_falls_back_to_the_rules(session, settings, toolbox, scripted, rules):
    scripted(reply("Save ₹9,999."), reply("Save ₹8,888."))
    answer = ask(session, settings, toolbox, "How much did I spend?")
    assert answer.display_text == "Rules answer" and answer.thread_id is not None
    assert rules[0]["rules_only"] is True
    saved = session.scalars(select(AdvisorMessage.text)).all()
    assert saved == ["How much did I spend?", "Rules answer"]


def test_an_unavailable_model_falls_back_to_the_rules(session, settings, toolbox, scripted, rules):
    scripted(ProviderUnavailable("assistant_unavailable"))
    answer = ask(session, settings, toolbox, "How much did I spend this month?")
    assert answer.display_text == "Rules answer" and len(rules) == 1


@pytest.mark.parametrize(
    "question", ["Which mutual fund should I buy?", "Should I buy Tata Motors shares now?"]
)
def test_a_security_pick_is_declined_without_the_model(
    session, settings, toolbox, scripted, rules, question
):
    model = scripted()
    ask(session, settings, toolbox, question)
    assert model.calls == [] and rules[0]["rules_only"] is True


def test_the_model_cannot_loop_on_tools_forever(session, settings, toolbox, scripted):
    rounds = [
        [call("money_summary", {"period": whole("this_month")}, f"call_{n}")] for n in range(4)
    ]
    model = scripted(*rounds, reply("Money out this month is ₹18,420.50."))
    answer = ask(session, settings, toolbox, "Tell me everything")
    assert answer.display_text == "Money out this month is ₹18,420.50."
    assert [step["tool_choice"] for step in model.calls] == ["auto"] * 4 + ["none"]


def test_memory_is_saved_and_used_in_the_next_chat(session, settings, toolbox, scripted):
    scripted(
        reply(
            "Nice! I'll remember your bike plan.",
            memory_updates=[
                {
                    "action": "add",
                    "ref": None,
                    "kind": "goal",
                    "text": "Saving ₹40,000 for a bike by March 2027",
                }
            ],
        )
    )
    answer = ask(session, settings, toolbox, "I'm saving ₹40,000 for a bike by March 2027")
    assert [(change.action, change.text) for change in answer.memory_changes] == [
        ("saved", "Saving ₹40,000 for a bike by March 2027")
    ]
    model = scripted(reply("Your bike goal is ₹40,000 by March 2027."))
    ask(session, settings, toolbox, "How is my bike plan going?")
    context = model.calls[0]["input"][1]["content"]
    assert "[m1] (goal) Saving ₹40,000 for a bike by March 2027" in context


def test_with_memory_off_nothing_is_read_or_saved(session, settings, toolbox, scripted):
    memory.remember(session, LOCAL_USER_ID, "about", "Works as a nurse", "web", 80)
    memory.set_enabled(session, LOCAL_USER_ID, False)
    session.commit()
    model = scripted(
        reply(
            "Okay.",
            memory_updates=[
                {"action": "add", "ref": None, "kind": "note", "text": "Likes short replies"}
            ],
        )
    )
    answer = ask(session, settings, toolbox, "Keep replies short")
    assert answer.memory_changes == []
    assert "Works as a nurse" not in model.calls[0]["input"][1]["content"]
    assert session.scalars(select(HouseholdMemory.text)).all() == ["Works as a nurse"]


def test_a_whatsapp_chat_continues_until_six_quiet_hours(session, settings, toolbox, scripted):
    model = scripted(reply("Food this month is ₹4,200."), reply("Last month it was ₹3,000."))
    first = ask(session, settings, toolbox, "Food this month?", channel="whatsapp")
    second = ask(session, settings, toolbox, "And last month?", channel="whatsapp")
    assert first.thread_id == second.thread_id
    turns = [item for item in model.calls[1]["input"] if item.get("role") in {"user", "assistant"}]
    assert [item["content"] for item in turns] == [
        "Food this month?",
        "Food this month is ₹4,200.",
        "And last month?",
    ]
    thread = session.get(AdvisorThread, first.thread_id)
    thread.last_at = datetime.now(UTC) - timedelta(hours=7)
    session.commit()
    scripted(reply("Hello again!"))
    third = ask(session, settings, toolbox, "Hi", channel="whatsapp")
    assert third.thread_id != first.thread_id


def test_another_households_chat_is_not_found(session, settings, toolbox, scripted):
    scripted(reply("Food this month is ₹4,200."))
    theirs = ask(session, settings, toolbox, "Food?", user_id=OTHER_USER)
    with pytest.raises(LookupError):
        ask(session, settings, toolbox, "Show me", thread_id=theirs.thread_id)


def test_speech_in_the_wrong_script_is_not_spoken(session, settings, toolbox, scripted):
    scripted(reply("इस महीने खाने पर ₹4,200 खर्च हुए।", speech="Is mahine ₹4,200 kharch hue"))
    answer = ask(session, settings, toolbox, "इस महीने खाने पर कितना खर्च?", display_style="hi")
    assert answer.display_language == "hi" and answer.display_script == "Deva"
    assert answer.speech_text == "" and answer.speech_language == "hi"


def test_logs_carry_no_question_answer_or_figure(session, settings, toolbox, scripted, caplog):
    scripted(reply("Food this month is ₹4,200."))
    with caplog.at_level(logging.INFO):
        ask(session, settings, toolbox, "What did Ramesh get from me?")
    lines = [JsonFormatter().format(record) for record in caplog.records]
    assert any('"event": "advisor.answered"' in line for line in lines)
    for line in lines:
        assert "Ramesh" not in line and "4,200" not in line and "4200" not in line
