"""Household feedback routes (docs/feedback-round/contract.md)."""

import base64
import logging
from datetime import UTC, datetime

import pytest
from finboy.api.v1 import feedback as route
from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.feedback import Feedback
from finboy.services.advisor.synthetic import OTHER_USER
from finboy.services.conversations import r2
from sqlalchemy import select

pytestmark = pytest.mark.anyio

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()
JPEG = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 64).decode()
SECRET = "my SBI card 4321 bill was wrong"


@pytest.fixture(autouse=True)
def notified(monkeypatch) -> list[object]:
    sent: list[object] = []
    monkeypatch.setattr(
        route.service, "notify", lambda _factory, _settings, item: sent.append(item)
    )
    return sent


async def test_a_report_is_kept_listed_and_announced(client, session, notified) -> None:
    sent = await client.post(
        "/api/v1/feedback",
        json={"kind": "problem", "message": "  The date was wrong  ", "page": "/review?tab=1#x"},
    )
    assert sent.status_code == 201, sent.text
    item = sent.json()["item"]
    assert item["status"] == "new" and item["message"] == "The date was wrong"
    assert item["page"] == "/review" and item["has_screenshot"] is False
    assert notified == [session.scalars(select(Feedback.id)).one()]
    listed = await client.get("/api/v1/feedback")
    assert listed.headers["cache-control"] == "no-store"
    assert listed.json()["screenshots"] is False
    assert [row["kind"] for row in listed.json()["items"]] == ["problem"]


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "complaint", "message": "x"},
        {"kind": "idea", "message": ""},
        {"kind": "idea", "message": "x" * 2001},
        {"kind": "idea", "message": "x", "page": "/" + "p" * 200},
        {"kind": "idea", "message": "x", "extra": True},
    ],
)
async def test_bad_reports_are_refused(client, body) -> None:
    assert (await client.post("/api/v1/feedback", json=body)).status_code == 422


@pytest.mark.parametrize(
    ("shot", "status", "code"),
    [
        ({"type": "image/png", "data": JPEG}, 422, "invalid_screenshot"),
        ({"type": "image/png", "data": "not base64!!"}, 422, "invalid_screenshot"),
        (
            {
                "type": "image/png",
                "data": base64.b64encode(b"\x89PNG\r\n\x1a\n" + bytes(1_550_000)).decode(),
            },
            413,
            "screenshot_too_large",
        ),
    ],
)
async def test_a_screenshot_must_be_what_it_says(client, session, shot, status, code) -> None:
    sent = await client.post(
        "/api/v1/feedback", json={"kind": "problem", "message": "x", "screenshot": shot}
    )
    assert sent.status_code == status and sent.json()["error"]["code"] == code
    assert session.scalars(select(Feedback)).all() == []


async def test_a_screenshot_goes_to_its_households_folder(client, session, monkeypatch) -> None:
    stored: list[tuple[str, str]] = []
    monkeypatch.setattr(r2, "configured", lambda _settings: True)
    monkeypatch.setattr(r2, "put", lambda _s, key, _data, kind: stored.append((key, kind)))
    sent = await client.post(
        "/api/v1/feedback",
        json={"kind": "idea", "message": "x", "screenshot": {"type": "image/png", "data": PNG}},
    )
    assert sent.status_code == 201 and sent.json()["screenshot_saved"] is True
    row = session.scalars(select(Feedback)).one()
    assert stored == [(f"finboy-feedback-dev/{LOCAL_USER_ID}/{row.id}.png", "image/png")]
    assert row.screenshot_key == stored[0][0] and sent.json()["item"]["has_screenshot"] is True


async def test_a_failed_upload_keeps_the_report(client, session, monkeypatch) -> None:
    def refuse(*_args) -> None:
        raise r2.StoreUnavailable

    monkeypatch.setattr(r2, "configured", lambda _settings: True)
    monkeypatch.setattr(r2, "put", refuse)
    sent = await client.post(
        "/api/v1/feedback",
        json={"kind": "idea", "message": "x", "screenshot": {"type": "image/png", "data": PNG}},
    )
    assert sent.status_code == 201 and sent.json()["screenshot_saved"] is False
    assert session.scalars(select(Feedback.screenshot_key)).one() is None


async def test_ten_a_day(client, session) -> None:
    session.add_all(
        Feedback(user_id=LOCAL_USER_ID, kind="idea", message="x", created_at=datetime.now(UTC))
        for _ in range(10)
    )
    session.commit()
    sent = await client.post("/api/v1/feedback", json={"kind": "idea", "message": "x"})
    assert sent.status_code == 429 and sent.json()["error"]["code"] == "feedback_limit"


async def test_only_its_own_reports_can_be_deleted(client, session) -> None:
    mine = Feedback(user_id=LOCAL_USER_ID, kind="idea", message="x")
    theirs = Feedback(user_id=OTHER_USER, kind="idea", message="y")
    session.add_all([mine, theirs])
    session.commit()
    assert (await client.delete(f"/api/v1/feedback/{theirs.id}")).status_code == 404
    assert (await client.delete(f"/api/v1/feedback/{mine.id}")).status_code == 204
    assert session.scalars(select(Feedback.user_id)).all() == [OTHER_USER]
    listed = await client.get("/api/v1/feedback")
    assert listed.json()["items"] == []


async def test_the_message_is_never_logged(client, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    sent = await client.post("/api/v1/feedback", json={"kind": "problem", "message": SECRET})
    assert sent.status_code == 201
    assert all(SECRET not in record.getMessage() for record in caplog.records)
    assert all(SECRET not in str(record.__dict__) for record in caplog.records)
