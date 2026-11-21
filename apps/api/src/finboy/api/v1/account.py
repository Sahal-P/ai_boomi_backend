"""The household's own account: its name (docs/names-search-round/contract.md) and deleting it
(docs/signup-round/contract.md), where everything goes except audit counts."""

import logging
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from finboy.api.deps import DB, CurrentUser
from finboy.core.access import clear_session
from finboy.core.config import LOCAL_USER_ID
from finboy.core.errors import AccessError
from finboy.db.models.core import User
from finboy.services.accounts.erasure import erase_self_serve
from finboy.services.accounts.households import clean_name

router = APIRouter(prefix="/account", tags=["account"])
logger = logging.getLogger(__name__)


class DeleteAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal["DELETE"]


class Name(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(max_length=200)


@router.post("/name")
def save_name(body: Name, session: DB, user_id: CurrentUser) -> Name:
    """The name the household goes by; never logged."""
    user = session.get(User, user_id)
    if user is None:
        raise AccessError("authentication_required")
    name = clean_name(body.name)
    if name is None:
        raise AccessError("invalid_name")
    user.display_name = name
    session.commit()
    logger.info("account.named", extra={"outcome": "saved"})
    return Name(name=name)


@router.post("/delete")
def delete_account(
    body: DeleteAccount, request: Request, session: DB, user_id: CurrentUser
) -> JSONResponse:
    if user_id == LOCAL_USER_ID:
        raise AccessError("owner_household")
    try:
        erase_self_serve(session, request.app.state.settings, request.app.state.engine, user_id)
    except ValueError:
        raise AccessError("authentication_required") from None
    logger.info("account.deleted", extra={"outcome": "deleted"})
    response = JSONResponse({"deleted": True})
    clear_session(request, response)
    return response
