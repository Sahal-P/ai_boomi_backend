"""The admin API against the disposable local database: sign-in and lockout, admin accounts,
household search, suspension, erasure, Premium, payments, sign-ups and the migration guard."""

import importlib.util
import io
import sys
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from finboy.core.clock import today_ist
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.core.errors import AccessError
from finboy.db.models.admin import AdminEvent, AdminSession, AdminUser
from finboy.db.models.billing import BillingPayment
from finboy.db.models.core import User
from finboy.db.models.mail import AuditEvent
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.services.admin import actions, cli
from finboy.services.admin.households import short
from finboy.services.billing import links
from sqlalchemy import inspect, or_, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from .database import (
    ADMINS,
    ENCRYPTION_KEY,
    LOGIN,
    PASSWORD,
    SESSION_KEY,
    admin_id,
    create_admin,
    epoch,
    household,
    household_cookie,
    signed_in,
)

pytestmark = pytest.mark.integration

ADMIN = "admin.one@example.test"
OTHER = "admin.two@example.test"
NEW_PASSWORD = "another-synthetic-password"
PHONE = "919812345670"  # synthetic
World = tuple[Settings, sessionmaker]


def code(response: Any) -> str:
    return response.json()["error"]["code"]


def cli_run(monkeypatch: pytest.MonkeyPatch, *args: str, password: str | None = None) -> int:
    if password is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(password + "\n"))
    return cli.main(list(args))


def leaves(value: Any) -> Iterator[Any]:
    """Every value inside a JSON document."""
    if isinstance(value, dict):
        for item in value.values():
            yield from leaves(item)
    elif isinstance(value, list):
        for item in value:
            yield from leaves(item)
    else:
        yield value


def test_sign_in_lockout_server_reset_and_sessions(
    world: World, api: FastAPI, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    _, pg = world
    created = cli_run(
        monkeypatch, "create", "--email", ADMIN.upper(), "--password-stdin", password=PASSWORD
    )
    assert created == 0
    me = admin_id(pg, ADMIN)
    ADMINS.append(me)
    again = cli_run(monkeypatch, "create", "--email", ADMIN, "--password-stdin", password=PASSWORD)
    assert again == 2
    assert cli_run(monkeypatch, "list") == 0
    printed = capsys.readouterr()
    assert f"{ADMIN}  active  last sign-in never" in printed.out
    assert PASSWORD not in printed.out + printed.err

    browser = TestClient(api)
    for _ in range(5):
        wrong = browser.post(LOGIN, json={"email": ADMIN, "password": "synthetic-wrong-password"})
        assert (wrong.status_code, code(wrong)) == (401, "admin_login_failed")
    locked = browser.post(LOGIN, json={"email": ADMIN, "password": PASSWORD})
    assert (locked.status_code, code(locked)) == (401, "admin_login_failed")
    with pg() as session:
        assert session.get(AdminUser, me).locked_until > datetime.now(UTC)

    # The server's reset unlocks the account; the panel never could.
    reset = cli_run(
        monkeypatch, "reset-password", "--email", ADMIN, "--password-stdin", password=NEW_PASSWORD
    )
    assert reset == 0
    first, second = signed_in(api, ADMIN, NEW_PASSWORD), signed_in(api, ADMIN, NEW_PASSWORD)
    listed = first.get("/api/v1/admin/sessions").json()
    assert len(listed) == 2 and sum(row["current"] for row in listed) == 1
    assert first.post("/api/v1/admin/sessions/sign-out-others").status_code == 200
    assert second.get("/api/v1/admin/session").status_code == 401

    change = "/api/v1/admin/password"
    wrong = first.post(change, json={"current": "synthetic-wrong-password", "new": PASSWORD})
    assert (wrong.status_code, code(wrong)) == (401, "admin_login_failed")
    weak = first.post(change, json={"current": NEW_PASSWORD, "new": "short"})
    assert (weak.status_code, code(weak)) == (422, "weak_password")
    assert first.post(change, json={"current": NEW_PASSWORD, "new": PASSWORD}).status_code == 200
    assert first.get("/api/v1/admin/session").status_code == 200

    with pg() as session:  # sessions end on their own after ADMIN_SESSION_HOURS
        session.execute(
            update(AdminSession)
            .where(AdminSession.admin_id == me, AdminSession.revoked_at.is_(None))
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        session.commit()
    assert first.get("/api/v1/admin/session").status_code == 401

    third = signed_in(api, ADMIN)
    token = third.cookies.get("finboy_admin")
    assert third.post("/api/v1/admin/logout").status_code == 200
    replayed = TestClient(api, cookies={"finboy_admin": token}).get("/api/v1/admin/session")
    assert (replayed.status_code, code(replayed)) == (401, "admin_required")
    with pg() as session:
        stored = session.scalars(select(AdminSession.token_sha256)).all()
        assert token not in stored  # only digests are kept
        done = Counter(
            session.scalars(
                select(AdminEvent.action).where(
                    or_(AdminEvent.admin_id == me, AdminEvent.detail["admin"].astext == str(me))
                )
            )
        )
    assert done == Counter(
        login_failed=6,
        login=3,
        admin_created=1,
        admin_password_reset=1,
        sessions_revoked=1,
        password_changed=1,
        logout=1,
    )


def test_admins_are_added_with_a_temporary_password_and_disabled(
    world: World, api: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, pg = world
    me = create_admin(pg, ADMIN)
    mine = signed_in(api, ADMIN)
    added = mine.post("/api/v1/admin/admins", json={"email": OTHER.upper()})
    assert added.status_code == 200 and added.json()["email"] == OTHER
    temporary = added.json()["temporary_password"]
    other = admin_id(pg, OTHER)
    ADMINS.append(other)
    again = mine.post("/api/v1/admin/admins", json={"email": OTHER})
    assert (again.status_code, code(again)) == (409, "admin_exists")

    theirs = TestClient(api)
    first = theirs.post(LOGIN, json={"email": OTHER, "password": temporary})
    assert first.json() == {"email": OTHER, "must_change_password": True}
    blocked = theirs.get("/api/v1/admin/overview")
    assert (blocked.status_code, code(blocked)) == (403, "admin_password_change_required")
    changed = theirs.post(
        "/api/v1/admin/password", json={"current": temporary, "new": NEW_PASSWORD}
    )
    assert changed.json() == {"email": OTHER, "must_change_password": False}
    assert theirs.get("/api/v1/admin/overview").status_code == 200

    itself = mine.post(f"/api/v1/admin/admins/{me}/disable")
    assert (itself.status_code, code(itself)) == (409, "action_not_allowed")
    disabled = mine.post(f"/api/v1/admin/admins/{other}/disable")
    rows = {row["email"]: row for row in disabled.json()}
    assert rows[OTHER]["active"] is False and rows[ADMIN]["you"] is True
    assert theirs.get("/api/v1/admin/session").status_code == 401
    refused = TestClient(api).post(LOGIN, json={"email": OTHER, "password": NEW_PASSWORD})
    assert (refused.status_code, code(refused)) == (401, "admin_login_failed")
    assert temporary not in mine.get("/api/v1/admin/admins").text
    # Only the server lets a disabled admin back in.
    assert cli_run(monkeypatch, "enable", "--email", OTHER) == 0
    assert signed_in(api, OTHER, NEW_PASSWORD).get("/api/v1/admin/session").status_code == 200
    with pg() as session:
        enabled = session.scalars(
            select(AdminEvent.action).where(AdminEvent.detail["admin"].astext == str(other))
        ).all()
    assert {"admin_created", "admin_disabled", "admin_enabled"} <= set(enabled)


def test_households_are_found_by_id_or_exact_number_and_show_no_content(
    world: World, api: FastAPI
) -> None:
    settings, pg = world
    create_admin(pg, ADMIN)
    mine = signed_in(api, ADMIN)
    family = household(pg, phone=PHONE)
    pending, pilot = household(pg, kind="pending"), household(pg, kind="pilot")
    web = TestClient(api, cookies=household_cookie(settings, family, epoch(pg, family)))
    entry = {
        "kind": "spent",
        "amount_minor": 43210,
        "counterparty": "SENSITIVE PAYEE",
        "category": "groceries",
        "day": today_ist().isoformat(),
    }
    assert web.post("/api/v1/entries", json=entry).status_code == 200

    def found(**params: str) -> list[str]:
        page = mine.get("/api/v1/admin/households", params=params)
        assert page.status_code == 200
        return [item["id"] for item in page.json()["items"]]

    for typed in ("+91 98123 45670", "9812345670", short(family)):
        assert found(q=typed) == [str(family)]
    assert found(q="9812345679") == [] and found(q="someone's name") == []
    assert str(pending) in found(kind="pending") and str(family) not in found(kind="pending")
    assert str(pilot) in found(kind="pilot")

    detail = mine.get(f"/api/v1/admin/households/{family}")
    body = detail.json()
    assert (body["kind"], body["status"], body["whatsapp"]) == ("self_serve", "active", True)
    assert body["records"] == {"confirmed": 1} and body["language"] == "hi"
    assert body["imports"] == []  # a quick add is a record, not an import an operator follows
    assert body["actions"] == ["sign_out", "suspend", "erase", "premium", "pay_link"]
    assert body["whatsapp_state"]["replies_on"] is True
    assert body["last_record_at"] is not None and body["usage"]["ai_limit"] > 0

    shown = [
        detail.json(),
        mine.get("/api/v1/admin/households").json(),
        mine.get("/api/v1/admin/overview").json(),
        mine.get("/api/v1/admin/audit").json(),
    ]
    values = [value for document in shown for value in leaves(document)]
    with pg() as session:
        stored_hash = session.scalar(
            select(WhatsAppBinding.sender_hash).where(WhatsAppBinding.user_id == family)
        )
    assert 43210 not in values and stored_hash not in values
    for value in values:
        assert not (isinstance(value, str) and ("SENSITIVE" in value or "9812345670" in value))
    missing = mine.get(f"/api/v1/admin/households/{uuid4()}")
    assert (missing.status_code, code(missing)) == (404, "not_found")


def test_suspension_stops_the_web_and_pay_links_until_restored(world: World, api: FastAPI):
    settings, pg = world
    me = create_admin(pg, ADMIN)
    mine = signed_in(api, ADMIN)
    family = household(pg, phone=PHONE)
    with pg() as session:  # the person had sent STOP on WhatsApp
        session.execute(
            update(WhatsAppBinding).where(WhatsAppBinding.user_id == family).values(enabled=False)
        )
        session.commit()
    before = household_cookie(settings, family, epoch(pg, family))
    assert TestClient(api, cookies=before).get("/api/v1/money/summary").status_code == 200
    link = mine.post(f"/api/v1/admin/households/{family}/pay-link").json()["url"]
    assert link.startswith("http://127.0.0.1:3081/pay#")

    suspended = mine.post(f"/api/v1/admin/households/{family}/suspend").json()
    assert suspended["status"] == "suspended" and suspended["actions"] == ["restore", "erase"]
    old = TestClient(api, cookies=before).get("/api/v1/money/summary")
    assert (old.status_code, code(old)) == (401, "authentication_required")
    current = household_cookie(settings, family, epoch(pg, family))
    paused = TestClient(api, cookies=current).get("/api/v1/money/summary")
    assert (paused.status_code, code(paused)) == (403, "account_suspended")
    with pg() as session, pytest.raises(AccessError, match="^link_expired$"):
        links.read(session, settings, link.split("#", 1)[1])
    twice = mine.post(f"/api/v1/admin/households/{family}/suspend")
    assert (twice.status_code, code(twice)) == (409, "action_not_allowed")
    listed = mine.get("/api/v1/admin/households", params={"status": "suspended"}).json()
    assert str(family) in [item["id"] for item in listed["items"]]

    restored = mine.post(f"/api/v1/admin/households/{family}/restore").json()
    assert restored["status"] == "active"
    assert TestClient(api, cookies=current).get("/api/v1/money/summary").status_code == 200
    # Restoring never turns WhatsApp replies back on after the person's own STOP.
    assert restored["whatsapp_state"]["replies_on"] is False
    with pg() as session:
        done = set(session.scalars(select(AdminEvent.action).where(AdminEvent.admin_id == me)))
    assert {"pay_link_created", "household_suspended", "household_restored"} <= done


def test_erase_follows_each_households_rules_and_never_touches_the_owner(
    world: World, api: FastAPI
) -> None:
    _, pg = world
    me = create_admin(pg, ADMIN)
    mine = signed_in(api, ADMIN)
    family, pilot = household(pg, phone=PHONE), household(pg, kind="pilot")
    pending = household(pg, kind="pending")

    def erase(user_id: UUID, confirm: str | None = None):
        return mine.post(
            f"/api/v1/admin/households/{user_id}/erase",
            json={"confirm": confirm or short(user_id)},
        )

    wrong = erase(family, "zzzzzzzz")
    assert (wrong.status_code, code(wrong)) == (422, "confirmation_mismatch")
    assert erase(family).status_code == 200
    gone = mine.get(f"/api/v1/admin/households/{family}").json()
    assert (gone["status"], gone["actions"], gone["whatsapp"]) == ("deleted", [], False)
    assert erase(pilot).status_code == 200
    former = mine.get(f"/api/v1/admin/households/{pilot}").json()
    assert (former["kind"], former["actions"]) == ("former_pilot", [])
    assert erase(pending).status_code == 200
    assert mine.get(f"/api/v1/admin/households/{pending}").status_code == 404
    owner = erase(LOCAL_USER_ID)
    assert (owner.status_code, code(owner)) == (409, "action_not_allowed")
    paused = mine.post(f"/api/v1/admin/households/{LOCAL_USER_ID}/suspend")
    assert (paused.status_code, code(paused)) == (409, "action_not_allowed")

    with pg() as session:
        erased = session.execute(
            select(AdminEvent.household_id, AdminEvent.detail).where(
                AdminEvent.admin_id == me, AdminEvent.action == "household_erased"
            )
        ).all()
        own = set(
            session.scalars(
                select(AuditEvent.event_type).where(AuditEvent.user_id.in_([family, pilot]))
            )
        )
    assert {(row.household_id, row.detail["via"]) for row in erased} == {
        (family, "self_serve"),
        (pilot, "pilot"),
        (pending, "pending"),
    }
    assert {"account.deleted", "pilot.erased"} <= own  # the household's own trail, as before


def test_premium_payments_and_tidying_sign_ups(
    world: World, api: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, pg = world
    me = create_admin(pg, ADMIN)
    mine = signed_in(api, ADMIN)
    family = household(pg, joined_days_ago=45)
    assert mine.get(f"/api/v1/admin/households/{family}").json()["plan"] == "free"
    for days in (0, 367):
        premium = mine.post(f"/api/v1/admin/households/{family}/premium", json={"days": days})
        assert premium.status_code == 422
    granted = mine.post(f"/api/v1/admin/households/{family}/premium", json={"days": 30}).json()
    assert granted["plan"] == "active"
    paid_through = datetime.fromisoformat(granted["plan_detail"]["paid_through"])
    assert timedelta(days=29) < paid_through - datetime.now(UTC) <= timedelta(days=30)

    with pg() as session:
        payment = BillingPayment(
            user_id=family,
            txnid="FBADMIN" + uuid4().hex[:12],
            kind="checkout",
            started_via="web",
            status="pending",
            amount_minor=29900,
        )
        session.add(payment)
        session.commit()
        payment_id = payment.id
    pending = mine.get("/api/v1/admin/payments", params={"status": "pending"}).json()
    assert str(payment_id) in [row["id"] for row in pending["items"]]

    class PayU:
        def __init__(self, _settings: Settings) -> None:
            pass

        def __enter__(self) -> PayU:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def settle(session, _settings, _client, txnids: list[str]) -> None:
        session.execute(
            update(BillingPayment)
            .where(BillingPayment.txnid.in_(txnids))
            .values(status="paid", mode="UPI")
        )

    monkeypatch.setattr(actions.payu, "PayUClient", PayU)
    monkeypatch.setattr(actions.checkout, "reconcile", settle)
    checked = mine.post(f"/api/v1/admin/payments/{payment_id}/reconcile")
    assert checked.status_code == 200 and checked.json()["status"] == "paid"

    stale = household(pg, kind="pending", joined_days_ago=10)
    assert mine.post("/api/v1/admin/signups/tidy").status_code == 200
    with pg() as session:
        assert session.get(User, stale) is None
        details = dict(
            session.execute(
                select(AdminEvent.action, AdminEvent.detail).where(AdminEvent.admin_id == me)
            ).all()
        )
    assert details["premium_granted"] == {"days": 30}
    assert details["payment_reconciled"] == {"payment": str(payment_id)}
    assert details["signups_tidied"]["removed"] >= 1


def test_overview_and_system_show_counts_and_settings_never_secrets(world: World, api: FastAPI):
    settings, pg = world
    create_admin(pg, ADMIN)
    mine = signed_in(api, ADMIN)
    household(pg)
    household(pg, kind="pending")
    overview = mine.get("/api/v1/admin/overview").json()
    assert overview["households"]["self_serve"] >= 1 and overview["households"]["pending"] >= 1
    assert overview["signups"]["limit"] == settings.signup_limit
    system = mine.get("/api/v1/admin/system")
    body = system.json()
    assert (body["database"], body["schema_status"]) == ("connected", "current")
    assert body["schema_head"] == "0014_admin" and body["flags"]["billing_enabled"] is True
    assert body["limits"]["admin_session_hours"] == settings.admin_session_hours
    assert set(body["providers"].values()) <= {"configured", "missing", "disabled", "off"}
    for secret in (ENCRYPTION_KEY, SESSION_KEY, "s4ltForTestsOnly", "tEsTkY", "postgresql"):
        assert secret not in system.text


def load_migration() -> Any:
    path = Path(__file__).parents[2] / "alembic" / "versions" / "0014_admin.py"
    spec = importlib.util.spec_from_file_location("admin_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_downgrade_refuses_while_admins_or_suspensions_remain(world: World) -> None:
    _, pg = world
    me = create_admin(pg, ADMIN)
    migration = load_migration()
    engine = pg.kw["bind"]
    with engine.connect() as connection:
        transaction = connection.begin()
        with (
            Operations.context(MigrationContext.configure(connection)),
            pytest.raises(DBAPIError, match="Remove admin accounts"),
        ):
            migration.downgrade()
        transaction.rollback()
    # With no admins and no suspensions it goes down and back up; all of it is rolled back.
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            for statement in (
                "DELETE FROM admin_events",
                "DELETE FROM admin_sessions",
                "DELETE FROM admin_users",
                "UPDATE users SET suspended_at = NULL",
            ):
                connection.execute(text(statement))
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
                assert not inspect(connection).has_table("admin_users")
                migration.upgrade()
            assert inspect(connection).has_table("admin_events")
        finally:
            transaction.rollback()
    with pg() as session:
        assert session.get(AdminUser, me) is not None
