"""Request dependencies shared by household routes."""

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
        select(User.pilot, User.session_epoch, User.deleted_at).where(User.id == claim.user_id)
    ).one_or_none()
    # End the read snapshot so the route starts its own transaction.
    session.rollback()
    if row is None or row.deleted_at is not None or row.session_epoch != claim.epoch:
        raise AccessError("authentication_required")
    if row.pilot and claim.user_id != LOCAL_USER_ID:
        raise AccessError("web_not_available")  # pilot households stay on WhatsApp
    return claim.user_id


CurrentUser = Annotated[UUID, Depends(current_user_id)]
