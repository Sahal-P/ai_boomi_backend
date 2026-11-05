"""Request dependencies shared by household and admin routes."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.access import Claim, production
from finboy.core.config import LOCAL_USER_ID
from finboy.core.errors import AccessError
from finboy.db.models.core import User
from finboy.db.session import get_session
from finboy.services.accounts.households import active
from finboy.services.admin import auth as admin_auth
from finboy.services.billing.plans import require_premium

DB = Annotated[Session, Depends(get_session)]


def current_user_id(request: Request, session: DB) -> UUID:
    """The signed-in household. Another household's IDs then read as missing (404)."""
    claim: Claim | None = getattr(request.state, "claim", None)
    if claim is None:
        if production(request.app.state.settings):
            raise AccessError("authentication_required")
        return LOCAL_USER_ID  # loopback development and tests act as the owner
    if claim.epoch is None:
        return LOCAL_USER_ID  # the owner's household password
    row = session.execute(
        select(User.pilot, User.session_epoch, User.deleted_at, User.suspended_at).where(
            User.id == claim.user_id
        )
    ).one_or_none()
    # End the read snapshot so the route starts its own transaction.
    session.rollback()
    if row is None or row.deleted_at is not None or row.session_epoch != claim.epoch:
        raise AccessError("authentication_required")
    if not active(row):
        raise AccessError("account_suspended")
    if row.pilot and claim.user_id != LOCAL_USER_ID:
        raise AccessError("web_not_available")  # pilot households stay on WhatsApp
    return claim.user_id


CurrentUser = Annotated[UUID, Depends(current_user_id)]


def premium_user(request: Request, session: DB, user_id: CurrentUser) -> UUID:
    """The signed-in household, on a plan with Premium (docs/subscription-round/contract.md).

    Checked before any audio or file is read, so the Free plan costs nothing.
    """
    require_premium(session, request.app.state.settings, user_id)
    session.rollback()  # end the read snapshot, as `current_user_id` does
    return user_id


PremiumUser = Annotated[UUID, Depends(premium_user)]

# Answered while an admin still has to replace a temporary password.
PASSWORD_ROUTES = {"/api/v1/admin/session", "/api/v1/admin/password", "/api/v1/admin/logout"}


@dataclass(frozen=True)
class AdminAccess:
    id: UUID
    email: str
    session_id: UUID
    must_change_password: bool


def current_admin(request: Request, session: DB) -> AdminAccess:
    """The signed-in admin (docs/admin-round/contract.md). Unlike household routes there is no
    loopback shortcut: every admin route needs a live admin session, in every environment."""
    token = request.cookies.get(admin_auth.cookie_name(request.app.state.settings))
    found = admin_auth.find_session(session, token, datetime.now(UTC))
    if found is None:
        session.rollback()
        raise AccessError("admin_required")
    admin, live = found
    access = AdminAccess(admin.id, admin.email, live.id, admin.must_change_password)
    session.commit()  # keeps a refreshed `last_seen_at` and ends the read snapshot
    if access.must_change_password and request.url.path not in PASSWORD_ROUTES:
        raise AccessError("admin_password_change_required")
    return access


CurrentAdmin = Annotated[AdminAccess, Depends(current_admin)]
