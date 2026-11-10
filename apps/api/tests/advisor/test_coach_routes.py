"""Home's "For you" over HTTP (docs/advisor-round/contract.md, phase 3)."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from finboy.api.v1 import coach as coach_route
from finboy.core.config import LOCAL_USER_ID
from finboy.db.models import User
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.services.advisor import coach
from finboy.services.money.budgets import BudgetStatus
from finboy.services.money.engine import CommitmentView

from .support import make_settings

pytestmark = pytest.mark.anyio


@pytest.fixture
def settings():
    return make_settings().model_copy(update={"coach_enabled": True})


def nudges() -> list[coach.Nudge]:
    due = CommitmentView(
        id=uuid4(),
        kind="bill",
        label="Electricity bill",
        amount_minor=150000,
        due_date=date(2026, 11, 19),
        status="upcoming",
        confidence=0.9,
    )
    return [
        coach.Nudge("due_soon", str(due.id), "warning", coach.DueDetail(due, 1)),
        coach.Nudge(
            "budget_near",
            "2026-11:food_dining",
            "warning",
            coach.BudgetDetail(BudgetStatus("food_dining", 500000, 420000), 13),
        ),
        coach.Nudge("goal_progress", "2026-11", "good", coach.GoalDetail(500000, 600000, 7)),
        coach.Nudge(
            "budget_near",
            "2026-11:transport",
            "warning",
            coach.BudgetDetail(BudgetStatus("transport", 300000, 250000), 13),
        ),
    ]


def bind(session, user_id, *, opted_in: bool) -> None:
    session.add(
        WhatsAppBinding(
            id=uuid4(),
            user_id=user_id,
            sender_hash=uuid4().hex,
            enabled=True,
            consented_at=datetime.now(UTC),
            coach_opt_in_at=datetime.now(UTC) if opted_in else None,
            last_inbound_at=datetime.now(UTC),
        )
    )
    session.commit()


async def test_for_you_shows_the_first_three_written_by_code(client, monkeypatch) -> None:
    reads: list[date] = []

    def detect(_box, today: date) -> list[coach.Nudge]:
        reads.append(today)
        return nudges()

    monkeypatch.setattr(coach_route.coach, "detect", detect)
    response = await client.get("/api/v1/coach")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["whatsapp"] == "none", "the owner's number gets no diary nudges"
    assert [item["kind"] for item in body["items"]] == ["due_soon", "budget_near", "goal_progress"]
    first = body["items"][0]
    assert first == {
        "kind": "due_soon",
        "tone": "warning",
        "title": "Due soon",
        "text": "Electricity bill: ₹1,500 due tomorrow.",
        "href": "#obligations",
        "ask": "What do I have to pay this week?",
    }
    assert body["items"][1]["ask"] == "How can I spend less on food & dining?"
    assert len(reads) == 1


async def test_for_you_reads_as_404_while_the_coach_is_off(app, client) -> None:
    app.state.settings = app.state.settings.model_copy(update={"coach_enabled": False})
    response = await client.get("/api/v1/coach")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "coach_off"
    session_view = (await client.get("/api/v1/auth/session")).json()
    assert session_view["coach"] is False


async def test_the_session_says_the_coach_is_on(client) -> None:
    assert (await client.get("/api/v1/auth/session")).json()["coach"] is True


def test_whatsapp_says_whether_a_diary_number_gets_nudges(session) -> None:
    household = User(id=uuid4(), display_name="Household", joined_via="whatsapp")
    session.add(household)
    session.commit()
    assert coach_route.whatsapp_state(session, household.id) == "none"
    bind(session, household.id, opted_in=False)
    assert coach_route.whatsapp_state(session, household.id) == "off"
    bind(session, household.id, opted_in=True)
    assert coach_route.whatsapp_state(session, household.id) == "on"
    # The owner's own number uses the older question flow: no diary, so no nudges.
    bind(session, LOCAL_USER_ID, opted_in=True)
    assert coach_route.whatsapp_state(session, LOCAL_USER_ID) == "none"


async def test_a_failure_reads_as_a_plain_error_without_details(client, monkeypatch) -> None:
    def broken(_box, _today):
        raise RuntimeError("SENSITIVE engine detail ₹4,200")

    monkeypatch.setattr(coach_route.coach, "detect", broken)
    response = await client.get("/api/v1/coach")
    assert response.status_code == 500
    assert "SENSITIVE" not in response.text and "₹" not in response.text
    assert response.json()["error"]["code"]


async def test_for_you_keeps_cors_exact(client) -> None:
    allowed = await client.options(
        "/api/v1/coach",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    refused = await client.options(
        "/api/v1/coach",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in refused.headers
