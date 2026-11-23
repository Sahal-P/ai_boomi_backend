"""Apply, Undo and Not now over HTTP (docs/advisor-edits-round/contract.md). Applying and undoing
run on PostgreSQL in test_changes_postgres.py; these need only the SQLite double."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.advisor import AdvisorMessage
from finboy.db.models.changes import RecordChangeSet
from finboy.services.advisor import history
from sqlalchemy import select

from .support import OTHER_USER

pytestmark = pytest.mark.anyio

SUMMARY = {
    "count": 2,
    "groups": [
        {
            "kind": "category",
            "category": "travel",
            "names": ["REDBUS", "Indian Railways"],
            "more_names": 0,
            "new_name": None,
            "payments": 2,
            "amount_minor": 178220,
            "before_minor": None,
            "after_minor": None,
        }
    ],
    "kept": 0,
    "remembered": 2,
    "skipped": 0,
}


def proposal(session, user_id=LOCAL_USER_ID, message_id=None, **values) -> RecordChangeSet:
    now = datetime.now(UTC)
    fields = {
        "channel": "web",
        "state": "proposed",
        "changes": [{"type": "payee_category", "payee": "REDBUS", "category": "travel"}],
        "summary": SUMMARY,
        "created_at": now,
        "expires_at": now + timedelta(hours=24),
    }
    row = RecordChangeSet(user_id=user_id, message_id=message_id, **(fields | values))
    session.add(row)
    session.commit()
    return row


async def test_applying_waits_for_the_release_flag(client, session) -> None:
    row = proposal(session)
    response = await client.post(f"/api/v1/assistant/changes/{row.id}/apply")
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "changes_unavailable"
    session.refresh(row)
    assert row.state == "proposed"


async def test_not_now_closes_only_the_households_own_proposal(client, session) -> None:
    mine, theirs = proposal(session), proposal(session, user_id=OTHER_USER)
    response = await client.post(f"/api/v1/assistant/changes/{theirs.id}/dismiss")
    assert response.status_code == 404 and response.json()["error"]["code"] == "not_found"
    response = await client.post(f"/api/v1/assistant/changes/{mine.id}/dismiss")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "declined" and body["count"] == 2 and body["remembered"] == 2
    assert response.headers["cache-control"] == "no-store"
    again = await client.post(f"/api/v1/assistant/changes/{mine.id}/dismiss")
    assert again.status_code == 200 and again.json()["state"] == "declined"
    response = await client.post(f"/api/v1/assistant/changes/{uuid4()}/dismiss")
    assert response.status_code == 404


async def test_a_reopened_chat_shows_each_proposal_and_its_state(client, session) -> None:
    thread = history.save_turn(
        session,
        user_id=LOCAL_USER_ID,
        channel="web",
        thread=None,
        question="Sort my Other payments",
        answer="Two can move to travel.",
        language="en",
        tool_names=["other_payees", "propose_changes"],
        now=datetime.now(UTC),
    )
    session.commit()
    answer = session.scalar(select(AdvisorMessage).where(AdvisorMessage.role == "assistant"))
    assert answer is not None
    proposal(session, message_id=answer.id, expires_at=datetime.now(UTC) - timedelta(minutes=1))
    response = await client.get(f"/api/v1/assistant/threads/{thread.id}")
    assert response.status_code == 200, response.text
    question, reply = response.json()["messages"]
    assert question["change_set"] is None
    assert reply["change_set"]["state"] == "expired"  # never tapped within its day
    assert reply["change_set"]["groups"][0]["names"] == ["REDBUS", "Indian Railways"]
