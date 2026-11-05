"""Delete my account (docs/signup-round/contract.md): everything goes except audit counts."""

import logging
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from finboy.api.deps import DB, CurrentUser
from finboy.core.access import clear_session
from finboy.core.config import LOCAL_USER_ID
from finboy.core.errors import AccessError
from finboy.services.accounts.erasure import erase_self_serve

router = APIRouter(prefix="/account", tags=["account"])
logger = logging.getLogger(__name__)


class DeleteAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal["DELETE"]


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
