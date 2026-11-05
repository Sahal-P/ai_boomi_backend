"""Admin sign-in and accounts (docs/admin-round/contract.md).

Passwords use the household password's scrypt helper. Sessions are server-side: the cookie holds
a random token and only its SHA-256 is stored, so the household session key can't mint an admin
session, and signing out ends exactly one browser.
"""

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from finboy.core.access import check_password, password_hash, production
from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.db.models.admin import AdminSession, AdminUser

COOKIE = "__Host-finboy_admin"
DEV_COOKIE = "finboy_admin"  # loopback development is plain HTTP, which refuses __Host- cookies
LOCK_AFTER = 5
LOCK_FOR = timedelta(minutes=15)
SEEN_EVERY = timedelta(minutes=1)
PASSWORD_LENGTH = (12, 256)
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
# Spent on an unknown, disabled or locked account, so every failure costs one scrypt check.
_TIMING_GUARD = password_hash(secrets.token_urlsafe(16))


@dataclass(frozen=True)
class Attempt:
    """A sign-in attempt: the account the email named (for the audit trail), and on success the
    new session's token."""

    admin: AdminUser | None
    token: str | None


def cookie_name(settings: Settings) -> str:
    return COOKIE if production(settings) else DEV_COOKIE


def normalize_email(value: str) -> str | None:
    email = value.strip().lower()
    return email if len(email) <= 254 and EMAIL.fullmatch(email) else None


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def check_new_password(password: str, email: str) -> None:
    low, high = PASSWORD_LENGTH
    if not low <= len(password) <= high or password.strip().lower() == email:
        raise AccessError("weak_password")


def temporary_password() -> str:
    """Shown once to the admin who created the account; changed at first sign-in."""
    return secrets.token_urlsafe(18)


def sign_in(
    session: Session, settings: Settings, *, email: str, password: str, device: str, now: datetime
) -> Attempt:
    address = normalize_email(email)
    admin = (
        session.scalar(select(AdminUser).where(AdminUser.email == address).with_for_update())
        if address
        else None
    )
    if admin is None or admin.disabled_at is not None or _locked(admin, now):
        check_password(password, _TIMING_GUARD)
        return Attempt(admin, None)
    if not check_password(password, admin.password_hash):
        admin.failed_logins += 1
        if admin.failed_logins >= LOCK_AFTER:
            admin.failed_logins, admin.locked_until = 0, now + LOCK_FOR
        return Attempt(admin, None)
    admin.failed_logins, admin.locked_until, admin.last_login_at = 0, None, now
    return Attempt(admin, open_session(session, settings, admin, device=device, now=now))


def _locked(admin: AdminUser, now: datetime) -> bool:
    return admin.locked_until is not None and admin.locked_until > now


def open_session(
    session: Session, settings: Settings, admin: AdminUser, *, device: str, now: datetime
) -> str:
    token = secrets.token_urlsafe(32)
    session.add(
        AdminSession(
            admin_id=admin.id,
            token_sha256=digest(token),
            device=device[:64],
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(hours=settings.admin_session_hours),
        )
    )
    return token


def find_session(
    session: Session, token: str | None, now: datetime
) -> tuple[AdminUser, AdminSession] | None:
    """The live session this token opens, if any; refreshes when it was last seen."""
    if not token or len(token) > 128:
        return None
    row = session.execute(
        select(AdminUser, AdminSession)
        .join(AdminSession, AdminSession.admin_id == AdminUser.id)
        .where(
            AdminSession.token_sha256 == digest(token),
            AdminSession.revoked_at.is_(None),
            AdminSession.expires_at > now,
            AdminUser.disabled_at.is_(None),
        )
    ).one_or_none()
    if row is None:
        return None
    admin, live = row
    if live.last_seen_at < now - SEEN_EVERY:
        live.last_seen_at = now
    return admin, live


def revoke_all(session: Session, admin_id: UUID, now: datetime, *, keep: UUID | None = None) -> int:
    """Ends every live session of one admin, except `keep` (the browser asking)."""
    query = (
        update(AdminSession)
        .where(AdminSession.admin_id == admin_id, AdminSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    if keep is not None:
        query = query.where(AdminSession.id != keep)
    return session.execute(query).rowcount


def set_cookie(request: Request, response: Response, token: str) -> None:
    settings: Settings = request.app.state.settings
    response.set_cookie(
        cookie_name(settings),
        token,
        max_age=settings.admin_session_hours * 60 * 60,
        secure=production(settings),
        httponly=True,
        samesite="strict",
        path="/",
    )


def clear_cookie(request: Request, response: Response) -> None:
    settings: Settings = request.app.state.settings
    response.delete_cookie(
        cookie_name(settings),
        path="/",
        secure=production(settings),
        httponly=True,
        samesite="strict",
    )


def create_admin(
    session: Session,
    *,
    email: str,
    password: str,
    created_by: UUID | None,
    must_change_password: bool,
) -> AdminUser:
    address = normalize_email(email)
    if address is None:
        raise AccessError("invalid_contact")
    check_new_password(password, address)
    if session.scalar(select(AdminUser.id).where(AdminUser.email == address)) is not None:
        raise AccessError("admin_exists")
    admin = AdminUser(
        email=address,
        password_hash=password_hash(password),
        created_by=created_by,
        must_change_password=must_change_password,
    )
    session.add(admin)
    session.flush()
    return admin


def change_password(
    session: Session, admin: AdminUser, *, current: str, new: str, keep: UUID, now: datetime
) -> None:
    """The admin's own change: proves the current password, then ends their other sessions."""
    if not check_password(current, admin.password_hash):
        raise AccessError("admin_login_failed")
    check_new_password(new, admin.email)
    admin.password_hash = password_hash(new)
    admin.must_change_password = False
    revoke_all(session, admin.id, now, keep=keep)


def reset_password(session: Session, admin: AdminUser, password: str, now: datetime) -> None:
    """Server-side recovery: a new password, unlocked, every session ended."""
    check_new_password(password, admin.email)
    admin.password_hash = password_hash(password)
    admin.must_change_password = False
    admin.failed_logins, admin.locked_until = 0, None
    revoke_all(session, admin.id, now)


def disable_admin(session: Session, admin: AdminUser, *, actor: UUID | None, now: datetime) -> None:
    if admin.id == actor:
        raise AccessError("action_not_allowed")
    if admin.disabled_at is not None:
        return
    # Lock every active account so two admins can't disable each other at the same moment.
    active = session.scalars(
        select(AdminUser.id).where(AdminUser.disabled_at.is_(None)).with_for_update()
    ).all()
    if not set(active) - {admin.id}:
        raise AccessError("last_admin")
    admin.disabled_at = now
    revoke_all(session, admin.id, now)


def enable_admin(admin: AdminUser) -> bool:
    """Server-side only: a disabled admin may sign in again, unlocked. False if already active."""
    if admin.disabled_at is None:
        return False
    admin.disabled_at = None
    admin.failed_logins, admin.locked_until = 0, None
    return True
