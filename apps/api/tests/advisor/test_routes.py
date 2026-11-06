"""Advisor HTTP contracts: free Ask, the household's own chats and memory, fixed error words."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from finboy.api import deps
from finboy.api.v1 import assistant as assistant_route
from finboy.core.config import LOCAL_USER_ID
from finboy.core.errors import AccessError
from finboy.services.advisor import history, memory
from finboy.services.assistant.models import AssistantAnswer

from .support import OTHER_USER

pytestmark = pytest.mark.anyio


def answer(**extra) -> AssistantAnswer:
    return AssistantAnswer(
        intent="advisor",
        policy="answer",
        display_text="Food this month is ₹4,200.",
        speech_text="Food this month is ₹4,200.",
        speech_language="en",
        facts=[],
        simulation=None,
        evidence_transactions=[],
        warnings=[],
        **extra,
    )


def chat(session, user_id, question="Food this month?"):
    thread = history.save_turn(
        session,
        user_id=user_id,
        channel="web",
        thread=None,
        question=question,
        answer="Food this month is ₹4,200.",
        language="en",
        tool_names=["category_spending"],
        now=datetime.now(UTC),
    )
    session.commit()
    return thread.id


async def test_every_household_can_ask_the_advisor(client, monkeypatch) -> None:
    def refuse(*_args) -> None:
        raise AccessError("premium_required")

    calls: list[dict] = []

    def advise(_session, **kwargs) -> AssistantAnswer:
        calls.append(kwargs)
        return answer(thread_id=uuid4(), follow_ups=["And last month?"])

    monkeypatch.setattr(deps, "require_premium", refuse)
    monkeypatch.setattr(assistant_route, "advise", advise)
    thread_id = uuid4()
    response = await client.post(
        "/api/v1/assistant/ask", json={"text": "Food this month?", "thread_id": str(thread_id)}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == "advisor" and body["follow_ups"] == ["And last month?"]
    assert body["memory_changes"] == [] and response.headers["cache-control"] == "no-store"
    assert calls[0]["channel"] == "web" and calls[0]["thread_id"] == thread_id


async def test_another_households_chat_answers_404(client, monkeypatch) -> None:
    def advise(_session, **_kwargs) -> AssistantAnswer:
        raise LookupError("thread_not_found")

    monkeypatch.setattr(assistant_route, "advise", advise)
    response = await client.post(
        "/api/v1/assistant/ask", json={"text": "More?", "thread_id": str(uuid4())}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "thread_not_found"
    assert "LookupError" not in response.text


async def test_chats_list_open_and_delete_only_the_households_own(client, session) -> None:
    mine = chat(session, LOCAL_USER_ID)
    theirs = chat(session, OTHER_USER, "Their private question")
    listed = (await client.get("/api/v1/assistant/threads")).json()["threads"]
    assert [item["id"] for item in listed] == [str(mine)]
    assert listed[0]["messages"] == 2 and listed[0]["title"] == "Food this month?"
    detail = (await client.get(f"/api/v1/assistant/threads/{mine}")).json()
    assert [item["role"] for item in detail["messages"]] == ["user", "assistant"]
    other = await client.get(f"/api/v1/assistant/threads/{theirs}")
    assert other.status_code == 404 and "Their private question" not in other.text
    assert (await client.delete(f"/api/v1/assistant/threads/{theirs}")).status_code == 404
    assert (await client.delete(f"/api/v1/assistant/threads/{mine}")).status_code == 204
    chat(session, LOCAL_USER_ID)
    assert (await client.delete("/api/v1/assistant/threads")).json() == {"deleted": 1}
    assert history.threads(session, OTHER_USER)[0].id == theirs


async def test_memory_can_be_seen_edited_switched_off_and_cleared(client, session) -> None:
    saved = memory.remember(session, LOCAL_USER_ID, "goal", "Saving for a bike", "web", 80)
    theirs = memory.remember(session, OTHER_USER, "person", "Ravi is the landlord", "web", 80)
    session.commit()
    listed = (await client.get("/api/v1/memory")).json()
    assert listed["enabled"] is True and listed["limit"] == 80
    assert [item["text"] for item in listed["memories"]] == ["Saving for a bike"]
    edited = await client.patch(f"/api/v1/memory/{saved.id}", json={"text": "Saving for a car"})
    assert edited.status_code == 200 and edited.json()["text"] == "Saving for a car"
    secret = await client.patch(f"/api/v1/memory/{saved.id}", json={"text": "My PIN is 1234"})
    assert secret.status_code == 422 and secret.json()["error"]["code"] == "invalid_memory"
    other = await client.patch(f"/api/v1/memory/{theirs.id}", json={"text": "Mine now"})
    assert other.status_code == 404
    assert (await client.put("/api/v1/memory/settings", json={"enabled": "no"})).status_code == 422
    switched = await client.put("/api/v1/memory/settings", json={"enabled": False})
    assert switched.json() == {"enabled": False}
    assert (await client.get("/api/v1/memory")).json()["enabled"] is False
    assert (await client.delete(f"/api/v1/memory/{theirs.id}")).status_code == 404
    assert (await client.delete("/api/v1/memory")).json() == {"deleted": 1}
    assert [row.text for row in memory.listed(session, OTHER_USER)] == ["Ravi is the landlord"]


async def test_the_session_says_the_advisor_is_on(client) -> None:
    body = (await client.get("/api/v1/auth/session")).json()
    assert body["advisor"] is True


async def test_memory_routes_keep_cors_exact(client) -> None:
    allowed = await client.options(
        "/api/v1/memory",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "DELETE"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    refused = await client.options(
        "/api/v1/memory",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "DELETE"},
    )
    assert "access-control-allow-origin" not in refused.headers
