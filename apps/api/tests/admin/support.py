"""Synthetic admins and sessions for the admin tests; never real credentials."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from finboy.core.access import password_hash
from finboy.db.models.admin import AdminSession, AdminUser
from finboy.services.admin import auth

PASSWORD = "synthetic-admin-password"
HASH = password_hash(PASSWORD)  # scrypt is deliberately slow, so hash once
ORIGIN = "https://household.example.test"
LOGIN = "/api/v1/admin/login"


def admin_row(**changes: object) -> AdminUser:
    values: dict[str, object] = {
        "id": uuid4(),
        "email": "admin@example.test",
        "password_hash": HASH,
        "must_change_password": False,
        "failed_logins": 0,
        "locked_until": None,
        "last_login_at": None,
        "disabled_at": None,
    }
    values.update(changes)
    return AdminUser(**values)


def live_session(
    admin: AdminUser, token: str, *, now: datetime | None = None, **changes: object
) -> AdminSession:
    now = now or datetime.now(UTC)
    values: dict[str, object] = {
        "id": uuid4(),
        "admin_id": admin.id,
        "token_sha256": auth.digest(token),
        "device": "Chrome · macOS",
        "created_at": now,
        "last_seen_at": now,
        "expires_at": now + timedelta(hours=8),
        "revoked_at": None,
    }
    values.update(changes)
    return AdminSession(**values)
