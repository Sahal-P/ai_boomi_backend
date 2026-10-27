"""Delete my account (docs/signup-round/contract.md): everything goes except audit counts."""

import logging
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from finboy.api.deps import DB, CurrentUser
from finboy.core.access import clear_session
from finboy.core.config import LOCAL_USER_ID
from finboy.core.errors import AccessError
from finboy.db.models.mail import MailConnection
from finboy.services.accounts.households import erase_household
from finboy.services.imports.locking import import_lock
from finboy.services.mail.oauth import OAuthConfig
from finboy.services.mail.security import MailError, decrypt
from finboy.services.privacy.audit import audit

router = APIRouter(prefix="/account", tags=["account"])
logger = logging.getLogger(__name__)


class DeleteAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal["DELETE"]


def _revoke_gmail(request: Request, session, user_id) -> None:
    """Best effort: FinBoy deletes the grant either way; a failed revoke is audited."""
    tokens = session.scalars(
        select(MailConnection).where(
            MailConnection.user_id == user_id, MailConnection.encrypted_refresh_token.is_not(None)
        )
    ).all()
    if not tokens:
        return
    try:
        config = OAuthConfig.from_settings(request.app.state.settings)
    except MailError:
        return
    google = config.google()
    try:
        for connection in tokens:
            try:
                google.revoke(decrypt(config.encryption_key, connection.encrypted_refresh_token))
                audit(session, "gmail.revoked", "connection", connection.id, user_id=user_id)
            except MailError:
                audit(
                    session,
                    "gmail.revoke_failed",
                    "connection",
                    connection.id,
                    user_id=user_id,
                    result="failure",
                )
    finally:
        google.close()


@router.post("/delete")
def delete_account(
    body: DeleteAccount, request: Request, session: DB, user_id: CurrentUser
) -> JSONResponse:
    if user_id == LOCAL_USER_ID:
        raise AccessError("owner_household")
    with import_lock(request.app.state.engine, user_id):
        _revoke_gmail(request, session, user_id)
        try:
            erase_household(session, user_id)
        except ValueError:
            session.rollback()
            raise AccessError("authentication_required") from None
        audit(session, "account.deleted", "user", user_id, user_id=user_id)
        session.commit()
    logger.info("account.deleted", extra={"outcome": "deleted"})
    response = JSONResponse({"deleted": True})
    clear_session(request, response)
    return response
