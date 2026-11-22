"""The admin message routes without a database (docs/conversation-round/contract.md)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from finboy.api.v1 import admin as admin_api
from finboy.services.admin import auth, messages, views

from .support import admin_row, live_session

NOW = datetime(2026, 11, 22, 9, 30, tzinfo=UTC)


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


@pytest.mark.anyio
async def test_opening_messages_is_audited_once_per_visit(
    client: httpx.AsyncClient,
    session: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    recorded: list[tuple[str, object]],
) -> None:
    signed_in(client, session)
    household = uuid4()
    row = views.MessageRow(
        id=uuid4(),
        at=NOW,
        channel="whatsapp",
        direction="in",
        kind="voice",
        text=None,
        transcript="doodhwale ko 500 diye",
        language="hi",
        choices=[],
        media="audio",
        media_bytes=4096,
        status=None,
        outcome=None,
    )
    page = views.MessagePage(
        kept_from=NOW, declined_at=None, items=[row], next_before=messages.cursor(row)
    )
    monkeypatch.setattr(messages, "page", lambda *_: page)
    path = f"/api/v1/admin/households/{household}/messages"
    first = await client.get(path)
    assert first.status_code == 200
    assert first.json()["items"][0]["transcript"] == "doodhwale ko 500 diye"
    assert first.headers["cache-control"] == "no-store"
    earlier = await client.get(path, params={"before": first.json()["next_before"]})
    assert earlier.status_code == 200
    assert recorded == [("messages_viewed", household)]
    for unsafe in ("2026-11-22", f"{NOW.isoformat()}|x' OR 1=1", "x" * 101):
        refused = await client.get(path, params={"before": unsafe})
        assert refused.status_code == 422, unsafe


@pytest.mark.anyio
async def test_an_unknown_household_is_not_found(
    client: httpx.AsyncClient,
    session: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    recorded: list[tuple[str, object]],
) -> None:
    signed_in(client, session)

    def missing(*_: object) -> views.MessagePage:
        raise LookupError

    monkeypatch.setattr(messages, "page", missing)
    response = await client.get(f"/api/v1/admin/households/{uuid4()}/messages")
    assert (response.status_code, response.json()["error"]["code"]) == (404, "not_found")
    assert recorded == []


@pytest.mark.anyio
async def test_a_voice_note_streams_inline_and_is_audited(
    client: httpx.AsyncClient,
    session: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    recorded: list[tuple[str, object]],
) -> None:
    signed_in(client, session)
    household, message = uuid4(), uuid4()
    monkeypatch.setattr(
        messages, "media", lambda *_: messages.Media(household, "audio/ogg", b"OggS synthetic")
    )
    response = await client.get(f"/api/v1/admin/messages/{message}/media")
    assert response.status_code == 200 and response.content == b"OggS synthetic"
    assert response.headers["content-type"] == "audio/ogg"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == f'inline; filename="finboy-{message}.ogg"'
    assert recorded == [("media_opened", household)]


@pytest.mark.anyio
async def test_media_needs_an_admin_and_reports_r2_trouble_plainly(
    client: httpx.AsyncClient,
    session: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    recorded: list[tuple[str, object]],
) -> None:
    path = f"/api/v1/admin/messages/{uuid4()}/media"
    anonymous = await client.get(path)
    assert (anonymous.status_code, anonymous.json()["error"]["code"]) == (401, "admin_required")
    signed_in(client, session)
    unreachable = MagicMock(side_effect=messages.AccessError("media_unavailable"))
    monkeypatch.setattr(messages, "media", unreachable)
    response = await client.get(path)
    assert (response.status_code, response.json()["error"]["code"]) == (503, "media_unavailable")
    assert recorded == []
