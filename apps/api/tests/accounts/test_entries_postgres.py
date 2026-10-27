"""Quick add, daily limits and "Delete my account" through the real API and PostgreSQL."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from finboy.core.clock import today_ist
from finboy.db.models.core import User
from finboy.db.models.ledger import EmailSource, Transaction
from finboy.db.models.mail import AuditEvent
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.main import create_app
from sqlalchemy import select

from .support import FIRST, Phone, settings_for, sign_in_with_whatsapp

pytestmark = pytest.mark.integration


def signed_in(world, **changes) -> tuple[TestClient, Phone]:
    _, pg, config = world
    settings = settings_for(**changes)
    phone = Phone(pg, settings, config, FIRST)
    browser = TestClient(create_app(settings))
    browser.__enter__()
    sign_in_with_whatsapp(browser, phone)
    assert browser.post("/api/v1/auth/whatsapp/complete").status_code == 200
    return browser, phone


def test_quick_add_previews_then_saves_with_one_tap(world) -> None:
    browser, phone = signed_in(world)
    _, pg, _ = world
    try:
        preview = browser.post("/api/v1/entries/preview", json={"text": "Paid the milkman 500"})
        assert preview.status_code == 200
        assert preview.json()["kind"] == "spent" and preview.json()["amount_minor"] == 50000
        assert preview.json()["day"] == today_ist().isoformat()
        with pg() as session:  # a preview stores nothing
            assert not session.scalars(
                select(Transaction).where(Transaction.user_id == phone.household())
            ).all()

        saved = browser.post(
            "/api/v1/entries",
            json={
                "kind": "spent",
                "amount_minor": 50000,
                "counterparty": "Milkman",
                "category": "groceries",
                "day": today_ist().isoformat(),
            },
        )
        assert saved.status_code == 200 and saved.json()["kind"] == "record"
        detail = browser.get(f"/api/v1/transactions/{saved.json()['transaction_id']}").json()
        record = detail["transaction"]
        assert record["status"] == "confirmed" and record["category"] == "groceries"
        assert [source["source"] for source in detail["sources"]] == ["manual_entry"]
        assert browser.get("/api/v1/money/summary").json()["confirmed_outflows_minor"] == 50000
        with pg() as session:
            source = session.scalars(
                select(EmailSource).where(EmailSource.user_id == phone.household())
            ).one()
            assert source.source == "manual_entry"
        # A typed entry is not an import, so the Sources history stays empty.
        assert browser.get("/api/v1/imports").json()["total"] == 0

        # Save is a decision like any other, so it can be undone.
        undone = browser.post(
            f"/api/v1/transactions/{saved.json()['transaction_id']}/decisions/"
            f"{saved.json()['decision_id']}/undo",
            json={"expected_version": saved.json()["data_version"]},
        )
        assert undone.status_code == 200
        assert browser.get("/api/v1/money/summary").json()["confirmed_outflows_minor"] == 0

        due = browser.post(
            "/api/v1/entries",
            json={
                "kind": "due",
                "amount_minor": 120000,
                "label": "School fees",
                "category": "education",
                "due_date": (today_ist() + timedelta(days=5)).isoformat(),
            },
        )
        assert due.status_code == 200 and due.json()["kind"] == "due"
        listed = browser.get("/api/v1/money/obligations").json()["items"]
        assert [(row["label"], row["amount_minor"]) for row in listed] == [("School fees", 120000)]

        # Typed entries are checked again on the server.
        future = browser.post(
            "/api/v1/entries",
            json={
                "kind": "spent",
                "amount_minor": 100,
                "day": (today_ist() + timedelta(days=2)).isoformat(),
            },
        )
        assert future.status_code == 422
        assert (
            browser.post("/api/v1/entries", json={"kind": "spent", "amount_minor": 0}).status_code
            == 422
        )
    finally:
        browser.__exit__(None, None, None)


def test_daily_ai_limit_is_per_household(world) -> None:
    browser, _ = signed_in(world, daily_ai_limit=2)
    try:
        for _ in range(2):
            assert (
                browser.post(
                    "/api/v1/entries/preview", json={"text": "spent 20 on tea"}
                ).status_code
                == 200
            )
        limited = browser.post("/api/v1/entries/preview", json={"text": "spent 20 on tea"})
        assert limited.status_code == 429 and limited.json()["error"]["code"] == "usage_limit"
    finally:
        browser.__exit__(None, None, None)
    # The owner's household is not limited.
    _, pg, _ = world
    with TestClient(create_app(settings_for(daily_ai_limit=1))) as owner:
        for _ in range(3):
            assert (
                owner.post("/api/v1/entries/preview", json={"text": "spent 20"}).status_code == 200
            )


def test_delete_my_account_keeps_only_the_numbered_row_and_audit(world) -> None:
    browser, phone = signed_in(world)
    _, pg, config = world
    household = phone.household()
    try:
        browser.post(
            "/api/v1/entries",
            json={"kind": "spent", "amount_minor": 50000, "day": today_ist().isoformat()},
        )
        refused = browser.post("/api/v1/account/delete", json={"confirm": "yes"})
        assert refused.status_code == 422
        deleted = browser.post("/api/v1/account/delete", json={"confirm": "DELETE"})
        assert deleted.status_code == 200 and deleted.json() == {"deleted": True}
        # Every browser of that household is signed out, and the session no longer works.
        assert browser.get("/api/v1/auth/session").json()["household"]["owner"] is True
    finally:
        browser.__exit__(None, None, None)
    with pg() as session:
        user = session.get(User, household)
        assert user is not None and user.deleted_at is not None
        assert not session.scalars(
            select(Transaction).where(Transaction.user_id == household)
        ).all()
        assert not session.scalars(
            select(WhatsAppBinding).where(
                WhatsAppBinding.sender_hash == config.digest("sender", FIRST)
            )
        ).all()
        events = session.scalars(
            select(AuditEvent.event_type).where(AuditEvent.user_id == household)
        ).all()
        assert "account.deleted" in events


def test_the_owner_cannot_delete_the_owner_household(world) -> None:
    with TestClient(create_app(settings_for())) as owner:
        response = owner.post("/api/v1/account/delete", json={"confirm": "DELETE"})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "owner_household"
