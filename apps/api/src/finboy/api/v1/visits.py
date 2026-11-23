"""Page visits and WhatsApp taps from FinBoy's public pages (docs/ad-journey-round/contract.md).

Public, small and silent: the page never waits for these, and a bad tag is dropped rather than
refused. Only the outcome is logged; the ref and the User-Agent never are.
"""

import logging
from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from finboy.api.deps import DB
from finboy.core.errors import AccessError
from finboy.db.models.visits import REF_PATTERN
from finboy.services.accounts import visits

router = APIRouter(prefix="/visits", tags=["sign-up sources"])
logger = logging.getLogger("finboy.visits")


class VisitInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str = Field(pattern=REF_PATTERN)
    landing: str = Field(min_length=1, max_length=64)
    language: Literal["en", "hi", "ml"] | None = None
    source: str | None = Field(default=None, max_length=200)
    medium: str | None = Field(default=None, max_length=200)
    campaign: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=200)
    # The page saw an `fbclid`; the click ID itself is never sent.
    meta_click: bool = False


class TapInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str = Field(pattern=REF_PATTERN)


def _admit(request: Request) -> None:
    address = request.client.host if request.client else "unknown"
    state = request.app.state
    if not (state.visit_burst.admit() and state.visit_throttle.admit(address)):
        raise AccessError("try_later")


@router.post("", status_code=204)
def record_visit(body: VisitInput, request: Request, session: DB) -> Response:
    _admit(request)
    recorded = visits.record(
        session,
        ref=body.ref,
        tags=visits.clean_tags(
            body.source, body.medium, body.campaign, body.content, meta_click=body.meta_click
        ),
        landing=body.landing,
        language=body.language,
        user_agent=request.headers.get("user-agent", ""),
    )
    session.commit()
    logger.info(
        "visits.recorded", extra={"stage": "visit", "outcome": "new" if recorded else "seen"}
    )
    return Response(status_code=204)


@router.post("/tap", status_code=204)
def record_tap(body: TapInput, request: Request, session: DB) -> Response:
    _admit(request)
    tapped = visits.tap(session, body.ref)
    session.commit()
    logger.info("visits.recorded", extra={"stage": "tap", "outcome": "new" if tapped else "seen"})
    return Response(status_code=204)
