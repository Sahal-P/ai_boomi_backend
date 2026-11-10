"""Home's "For you": the coach's current nudges (docs/advisor-round/contract.md, phase 3).

The same detectors as the WhatsApp coach, read live for the signed-in household with no model
call and nothing written. `whatsapp` says whether its WhatsApp number gets them too: `on`, `off`
(it can send "coach on"), or `none` (no diary number linked).
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from finboy.api.deps import DB, CurrentUser
from finboy.core.clock import today_ist
from finboy.core.errors import error_response
from finboy.db.models.core import User
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.services.advisor import coach
from finboy.services.advisor.coach import WebItem
from finboy.services.advisor.tools import EngineToolbox

router = APIRouter(prefix="/coach", tags=["coach"])


class ForYou(BaseModel):
    items: list[WebItem]
    whatsapp: Literal["none", "off", "on"]


def whatsapp_state(session: Session, user_id: UUID) -> Literal["none", "off", "on"]:
    """Whether a consented, enabled diary number of this household gets the coach's nudges."""
    rows = session.scalars(
        select(WhatsAppBinding.coach_opt_in_at)
        .join(User, User.id == WhatsAppBinding.user_id)
        .where(
            WhatsAppBinding.user_id == user_id,
            WhatsAppBinding.enabled.is_(True),
            WhatsAppBinding.consented_at.is_not(None),
            or_(User.pilot.is_(True), User.joined_via.is_not(None)),
        )
    ).all()
    if not rows:
        return "none"
    return "on" if any(value is not None for value in rows) else "off"


@router.get("", response_model=ForYou)
def for_you(
    request: Request, response: Response, session: DB, user_id: CurrentUser
) -> ForYou | JSONResponse:
    settings = request.app.state.settings
    if not settings.coach_active:
        return error_response(request, 404, "coach_off", "FinBoy's coach is not switched on.")
    response.headers["Cache-Control"] = "no-store"
    found = coach.detect(EngineToolbox(session, user_id, settings=settings), today_ist())
    result = ForYou(items=coach.web_items(found), whatsapp=whatsapp_state(session, user_id))
    session.rollback()  # read-only: release the engine's read lock
    return result
