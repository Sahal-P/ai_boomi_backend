"""The admin feedback routes without a database (docs/feedback-round/contract.md)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from finboy.api.v1 import admin as admin_api
from finboy.services.admin import auth, views
from finboy.services.admin import feedback as feedback_admin

from .support import admin_row, live_session

NOW = datetime(2026, 11, 22, 9, 30, tzinfo=UTC)
pytestmark = pytest.mark.anyio


def signed_in(client: httpx.AsyncClient, session: MagicMock) -> None:
    admin = admin_row()
    session.execute.return_value.one_or_none.return_value = (
        admin,
        live_session(admin, "synthetic-token"),
    )
    client.cookies.set(auth.DEV_COOKIE, "synthetic-token")


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, object]]:
    entries: list[tuple[str, object]] = []
    monkeypatch.setattr(
        admin_api.audit,
        "record",
        lambda _session, action, **kwargs: entries.append((action, kwargs["household_id"])),
    )
    return entries


def report(household, status="new") -> views.FeedbackDetail:
    return views.FeedbackDetail(
        id=uuid4(),
        household_id=household,
        short_id=household.hex[:8],
        household_name="A household",
        kind="problem",
        status=status,
        has_screenshot=True,
        created_at=NOW,
        message="The date was wrong",
        page="/review",
        status_changed_at=None,
    )


async def test_reading_setting_and_opening_a_report_is_audited(
    client, session, monkeypatch, recorded
) -> None:
    signed_in(client, session)
    household = uuid4()
    found = report(household)
    listed = views.FeedbackPage(
        items=[views.FeedbackRow(**found.model_dump())], total=1, offset=0, next_offset=None, new=1
    )
    monkeypatch.setattr(feedback_admin, "page", lambda *_: listed)
    monkeypatch.setattr(feedback_admin, "detail", lambda *_: found)
    monkeypatch.setattr(feedback_admin, "set_status", lambda *_: report(household, "planned"))
    monkeypatch.setattr(
        feedback_admin, "screenshot", lambda *_: (household, "image/png", b"\x89PNG")
    )
    page = await client.get("/api/v1/admin/feedback", params={"status": "new"})
    assert page.status_code == 200 and "message" not in page.json()["items"][0]
    assert recorded == []
    opened = await client.get(f"/api/v1/admin/feedback/{found.id}")
    assert opened.json()["message"] == "The date was wrong"
    changed = await client.patch(f"/api/v1/admin/feedback/{found.id}", json={"status": "planned"})
    assert changed.json()["status"] == "planned"
    picture = await client.get(f"/api/v1/admin/feedback/{found.id}/screenshot")
    assert picture.status_code == 200 and picture.headers["cache-control"] == "no-store"
    assert recorded == [
        ("feedback_viewed", household),
        ("feedback_status_changed", household),
        ("feedback_screenshot_opened", household),
    ]


async def test_feedback_needs_an_admin(client) -> None:
    assert (await client.get("/api/v1/admin/feedback")).status_code == 401
    bad = await client.patch(f"/api/v1/admin/feedback/{uuid4()}", json={"status": "gone"})
    assert bad.status_code in {401, 422}
