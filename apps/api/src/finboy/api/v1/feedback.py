"""Feedback: a household tells the FinBoy team about a problem or an idea, and sees its status.

docs/feedback-round/contract.md. The message is never logged; a screenshot comes as base64 JSON
after the browser has redrawn it (no metadata) and is checked by its first bytes.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import sessionmaker

from finboy.api.deps import DB, CurrentUser
from finboy.core.errors import error_response
from finboy.db.models.feedback import MAX_MESSAGE, MAX_PAGE, Feedback
from finboy.services.conversations import r2
from finboy.services.feedback import service

router = APIRouter(prefix="/feedback", tags=["feedback"])

Kind = Literal["problem", "idea", "other"]
MESSAGES = {
    "feedback_limit": (429, "You've sent a lot today. Please send more tomorrow."),
    "invalid_screenshot": (422, "That picture can't be attached. Use a PNG, JPEG or WebP image."),
    "screenshot_too_large": (413, "That picture is too large. Try a smaller screenshot."),
}


class Screenshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["image/png", "image/jpeg", "image/webp"]
    data: str = Field(min_length=8, max_length=2_100_000, repr=False)


class FeedbackSend(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kind: Kind
    message: str = Field(min_length=1, max_length=MAX_MESSAGE, repr=False)
    page: str = Field(default="", max_length=MAX_PAGE)
    screenshot: Screenshot | None = None


class FeedbackItem(BaseModel):
    id: UUID
    kind: Kind
    message: str
    page: str
    status: Literal["new", "planned", "done"]
    has_screenshot: bool
    created_at: datetime
    status_changed_at: datetime | None


class FeedbackList(BaseModel):
    screenshots: bool
    items: list[FeedbackItem]


class FeedbackSent(BaseModel):
    item: FeedbackItem
    screenshot_saved: bool


def _item(row: Feedback) -> FeedbackItem:
    return FeedbackItem(
        id=row.id,
        kind=row.kind,  # type: ignore[arg-type]
        message=row.message,
        page=row.page,
        status=row.status,  # type: ignore[arg-type]
        has_screenshot=row.screenshot_key is not None,
        created_at=row.created_at,
        status_changed_at=row.status_changed_at,
    )


@router.get("", response_model=FeedbackList)
def list_feedback(
    request: Request, response: Response, session: DB, user_id: CurrentUser
) -> FeedbackList:
    response.headers["Cache-Control"] = "no-store"
    result = FeedbackList(
        screenshots=r2.configured(request.app.state.settings),
        items=[_item(row) for row in service.listed(session, user_id)],
    )
    session.rollback()
    return result


@router.post("", status_code=201, response_model=FeedbackSent)
def send_feedback(
    body: FeedbackSend,
    request: Request,
    tasks: BackgroundTasks,
    session: DB,
    user_id: CurrentUser,
) -> FeedbackSent | JSONResponse:
    settings = request.app.state.settings
    try:
        image = (
            (body.screenshot.type, service.screenshot(body.screenshot.type, body.screenshot.data))
            if body.screenshot is not None
            else None
        )
        row, kept = service.create(
            session,
            settings,
            user_id,
            kind=body.kind,
            message=body.message,
            page=body.page,
            image=image,
        )
    except service.FeedbackError as error:
        session.rollback()
        status, message = MESSAGES[error.code]
        return error_response(request, status, error.code, message)
    sent = FeedbackSent(item=_item(row), screenshot_saved=kept)
    factory = sessionmaker(bind=request.app.state.engine, expire_on_commit=False)
    tasks.add_task(service.notify, factory, settings, row.id)
    return sent


@router.delete("/{feedback_id}", status_code=204, response_class=Response)
def delete_feedback(
    feedback_id: UUID, request: Request, session: DB, user_id: CurrentUser
) -> Response:
    if not service.remove(session, request.app.state.settings, user_id, feedback_id):
        session.rollback()
        return error_response(request, 404, "feedback_not_found", "That feedback was not found.")
    session.commit()
    return Response(status_code=204)
