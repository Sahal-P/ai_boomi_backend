"""Admin sign-in, sessions, accounts, the audit log and the sign-in throttle, without a database."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from finboy.core import access
from finboy.core.access import KeyedThrottle
from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.db.models.admin import AdminEvent, AdminSession
from finboy.services.admin import audit, auth
from sqlalchemy.orm import Session

from .support import PASSWORD, admin_row, live_session

NOW = datetime(2026, 11, 5, 9, 30, tzinfo=UTC)
NEW_PASSWORD = "another-synthetic-password"


@pytest.fixture
def db() -> MagicMock:
    return MagicMock(spec=Session)


def sign_in(
    db: MagicMock, settings: Settings, password: str = PASSWORD, email: str = " Admin@Example.TEST"
) -> auth.Attempt:
    return auth.sign_in(
        db, settings, email=email, password=password, device="Chrome · macOS", now=NOW
    )


def refused(code: str):
    return pytest.raises(AccessError, match=f"^{code}$")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" Admin@Example.TEST ", "admin@example.test"),
        ("no-at-sign.example.test", None),
        ("two@@example.test", None),
        ("space in@example.test", None),
        ("a@b.c", None),
        ("x" * 65 + "@example.test", None),
    ],
)
def test_emails_are_normalised_or_refused(value: str, expected: str | None) -> None:
    assert auth.normalize_email(value) == expected


@pytest.mark.parametrize("password", ["ten-chars!", "x" * 257, " Admin@Example.test "])
def test_short_long_or_email_passwords_are_refused(password: str) -> None:
    with refused("weak_password"):
        auth.check_new_password(password, "admin@example.test")


def test_temporary_passwords_are_long_and_random() -> None:
    first, second = auth.temporary_password(), auth.temporary_password()
    assert first != second and len(first) >= 24
    auth.check_new_password(first, "admin@example.test")


def test_a_correct_password_opens_one_server_side_session(
    db: MagicMock, settings: Settings
) -> None:
    admin = admin_row(failed_logins=3)
    db.scalar.return_value = admin
    attempt = sign_in(db, settings)
    assert attempt.admin is admin and attempt.token
    query = db.scalar.call_args.args[0].compile(compile_kwargs={"literal_binds": True})
    assert "'admin@example.test'" in str(query) and "FOR UPDATE" in str(query)
    stored = db.add.call_args.args[0]
    assert isinstance(stored, AdminSession)
    # Only the digest is kept, so a database copy can't be replayed as a cookie.
    assert stored.token_sha256 == auth.digest(attempt.token) != attempt.token
    assert stored.expires_at == NOW + timedelta(hours=settings.admin_session_hours)
    assert admin.failed_logins == 0 and admin.last_login_at == NOW


def test_five_wrong_passwords_lock_the_account_for_fifteen_minutes(
    db: MagicMock, settings: Settings
) -> None:
    admin = admin_row()
    db.scalar.return_value = admin
    for failures in range(1, 5):
        assert sign_in(db, settings, password="synthetic-wrong-password").token is None
        assert admin.failed_logins == failures and admin.locked_until is None
    assert sign_in(db, settings, password="synthetic-wrong-password").token is None
    assert admin.locked_until == NOW + timedelta(minutes=15) and admin.failed_logins == 0
    # Even the right password waits out the lock.
    assert sign_in(db, settings).token is None
    db.add.assert_not_called()


@pytest.mark.parametrize("found", ["unknown", "disabled", "locked"])
def test_unknown_disabled_and_locked_accounts_cost_the_same_check(
    db: MagicMock, settings: Settings, monkeypatch: pytest.MonkeyPatch, found: str
) -> None:
    checked: list[str] = []
    real = auth.check_password

    def check(password: str, stored: str) -> bool:
        checked.append(stored)
        return real(password, stored)

    monkeypatch.setattr(auth, "check_password", check)
    admin = (
        None
        if found == "unknown"
        else admin_row(
            disabled_at=NOW if found == "disabled" else None,
            locked_until=NOW + timedelta(minutes=1) if found == "locked" else None,
        )
    )
    db.scalar.return_value = admin
    attempt = sign_in(db, settings)
    assert attempt.token is None and attempt.admin is admin
    assert checked == [auth._TIMING_GUARD]
    db.add.assert_not_called()


def test_a_malformed_email_still_costs_a_check_but_no_lookup(
    db: MagicMock, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    checked: list[str] = []
    monkeypatch.setattr(auth, "check_password", lambda _password, stored: checked.append(stored))
    assert sign_in(db, settings, email="not-an-email") == auth.Attempt(None, None)
    assert checked == [auth._TIMING_GUARD]
    db.scalar.assert_not_called()


@pytest.mark.parametrize("token", [None, "", "x" * 129])
def test_missing_or_oversized_tokens_never_reach_the_database(
    db: MagicMock, token: str | None
) -> None:
    assert auth.find_session(db, token, NOW) is None
    db.execute.assert_not_called()


def test_only_live_sessions_of_active_admins_count(db: MagicMock) -> None:
    admin = admin_row()
    live = live_session(admin, "synthetic-token", now=NOW - timedelta(minutes=5))
    db.execute.return_value.one_or_none.return_value = (admin, live)
    assert auth.find_session(db, "synthetic-token", NOW) == (admin, live)
    query = str(db.execute.call_args.args[0])
    for rule in (
        "admin_sessions.revoked_at IS NULL",
        "admin_sessions.expires_at >",
        "admin_users.disabled_at IS NULL",
        "admin_sessions.token_sha256 =",
    ):
        assert rule in query
    # Last seen is refreshed at most once a minute.
    assert live.last_seen_at == NOW
    auth.find_session(db, "synthetic-token", NOW + timedelta(seconds=30))
    assert live.last_seen_at == NOW
    db.execute.return_value.one_or_none.return_value = None
    assert auth.find_session(db, "synthetic-token", NOW) is None


def test_changing_the_password_keeps_this_browser_and_ends_the_others(db: MagicMock) -> None:
    admin = admin_row(must_change_password=True)
    keep = uuid4()
    with refused("admin_login_failed"):
        auth.change_password(
            db, admin, current="synthetic-wrong-password", new=NEW_PASSWORD, keep=keep, now=NOW
        )
    with refused("weak_password"):
        auth.change_password(db, admin, current=PASSWORD, new="short", keep=keep, now=NOW)
    db.execute.assert_not_called()
    auth.change_password(db, admin, current=PASSWORD, new=NEW_PASSWORD, keep=keep, now=NOW)
    assert not admin.must_change_password
    assert access.check_password(NEW_PASSWORD, admin.password_hash)
    revoked = db.execute.call_args.args[0]
    assert "admin_sessions.id !=" in str(revoked)
    assert keep in revoked.compile().params.values()


def test_a_server_reset_unlocks_and_ends_every_session(db: MagicMock) -> None:
    admin = admin_row(
        failed_logins=4, locked_until=NOW + timedelta(minutes=10), must_change_password=True
    )
    with refused("weak_password"):
        auth.reset_password(db, admin, "admin@example.test", NOW)
    auth.reset_password(db, admin, NEW_PASSWORD, NOW)
    assert admin.failed_logins == 0 and admin.locked_until is None
    assert not admin.must_change_password
    assert "admin_sessions.id !=" not in str(db.execute.call_args.args[0])


def test_nobody_disables_themselves_or_the_last_active_admin(db: MagicMock) -> None:
    admin = admin_row()
    with refused("action_not_allowed"):
        auth.disable_admin(db, admin, actor=admin.id, now=NOW)
    db.scalars.return_value.all.return_value = [admin.id]
    with refused("last_admin"):
        auth.disable_admin(db, admin, actor=uuid4(), now=NOW)
    assert admin.disabled_at is None
    db.scalars.return_value.all.return_value = [admin.id, uuid4()]
    auth.disable_admin(db, admin, actor=None, now=NOW)
    assert admin.disabled_at == NOW
    assert "UPDATE admin_sessions" in str(db.execute.call_args.args[0])


def test_the_server_can_let_a_disabled_admin_back_in_unlocked() -> None:
    admin = admin_row(disabled_at=NOW, failed_logins=3, locked_until=NOW + timedelta(minutes=5))
    assert auth.enable_admin(admin)
    assert admin.disabled_at is None and admin.failed_logins == 0 and admin.locked_until is None
    assert not auth.enable_admin(admin)  # already active


def test_new_admins_need_a_valid_unique_email_and_a_strong_password(db: MagicMock) -> None:
    def create(email: str, password: str = NEW_PASSWORD):
        return auth.create_admin(
            db, email=email, password=password, created_by=None, must_change_password=True
        )

    with refused("invalid_contact"):
        create("not-an-email")
    with refused("weak_password"):
        create("new@example.test", "too-short")
    db.scalar.return_value = uuid4()  # the email is taken
    with refused("admin_exists"):
        create("New@Example.test")
    db.scalar.return_value = None
    created = create(" New@Example.TEST")
    assert created.email == "new@example.test" and created.must_change_password
    assert access.check_password(NEW_PASSWORD, created.password_hash)
    assert NEW_PASSWORD not in created.password_hash


def test_the_audit_log_takes_fixed_actions_and_allowlisted_details(db: MagicMock) -> None:
    with pytest.raises(ValueError):
        audit.record(db, "export_everything", admin_id=None)
    with pytest.raises(ValueError):
        audit.record(db, "premium_granted", admin_id=None, phone="9876543210")
    db.add.assert_not_called()
    household = uuid4()
    audit.record(db, "premium_granted", admin_id=uuid4(), household_id=household, days=30)
    event = db.add.call_args.args[0]
    assert isinstance(event, AdminEvent)
    assert event.action == "premium_granted" and event.household_id == household
    assert event.detail == {"days": 30}


def test_the_sign_in_throttle_counts_each_key_apart_and_forgets_old_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [100.0]
    monkeypatch.setattr(access, "monotonic", lambda: clock[0])
    throttle = KeyedThrottle(limit=3, seconds=60, keys=2)
    assert [throttle.admit("address:a") for _ in range(4)] == [True, True, True, False]
    assert throttle.admit("address:b")  # another source keeps its own attempts
    clock[0] += 60
    assert throttle.admit("address:a")  # the minute has passed
    throttle.admit("address:c")
    assert list(throttle.windows) == ["address:a", "address:c"]  # bounded, oldest key first out
