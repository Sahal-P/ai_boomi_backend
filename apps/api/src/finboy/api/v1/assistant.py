"""Thin HTTP boundaries over the same services used by WhatsApp."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from finboy.api import deps
from finboy.api.deps import DB, CurrentUser, PremiumUser
from finboy.core.clock import today_ist
from finboy.core.errors import error_response
from finboy.db.session import get_session
from finboy.services.accounts import usage
from finboy.services.advisor import history
from finboy.services.advisor.service import advise
from finboy.services.advisor.suggestions import suggestions
from finboy.services.advisor.tools import EngineToolbox
from finboy.services.assistant.models import AskRequest, AssistantAnswer, SpeakRequest
from finboy.services.assistant.service import answer_question
from finboy.services.money.compat import simulation_response
from finboy.services.speech.media import InvalidAudio
from finboy.services.speech.models import Transcript
from finboy.services.speech.multipart import read_upload
from finboy.services.speech.service import synthesize_speech, transcribe_audio

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ThreadSummary(BaseModel):
    id: UUID
    channel: Literal["web", "whatsapp"]
    title: str
    started_at: datetime
    last_at: datetime
    messages: int


class ThreadList(BaseModel):
    threads: list[ThreadSummary]


class ThreadMessage(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    text: str
    language: Literal["en", "hi", "ml"] | None
    created_at: datetime


class ThreadDetail(BaseModel):
    thread: ThreadSummary
    messages: list[ThreadMessage]


class Deleted(BaseModel):
    deleted: int


class Suggestions(BaseModel):
    suggestions: list[str]


def _thread_missing(request: Request) -> JSONResponse:
    return error_response(request, 404, "thread_not_found", "That chat was not found.")


@router.post("/ask", response_model=AssistantAnswer)
def ask(
    body: AskRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    user_id: CurrentUser,
) -> AssistantAnswer | JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    settings = request.app.state.settings
    if not settings.advisor_enabled:
        # Before the advisor round, Ask stays Premium (docs/subscription-round/contract.md).
        deps.require_premium(session, settings, user_id)
        session.rollback()
    usage.use(session, settings, user_id, "ai")
    if settings.advisor_enabled:
        # Every household gets the advisor and its memory (docs/advisor-round/contract.md).
        try:
            result = advise(
                session,
                user_id=user_id,
                text=body.text,
                display_style=body.display_style,
                channel="web",
                settings=settings,
                thread_id=body.thread_id,
            )
        except LookupError:
            session.rollback()
            return _thread_missing(request)
    else:
        result = answer_question(
            session,
            user_id=user_id,
            text=body.text,
            display_style=body.display_style,
            settings=settings,
        )
    if result.simulation is not None:
        result = result.model_copy(
            update={
                "simulation": simulation_response(
                    result.simulation, include_overdue_line=body.include_overdue_line
                )
            }
        )
    return result


@router.post(
    "/transcribe",
    response_model=Transcript,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["audio"],
                        "properties": {
                            "audio": {"type": "string", "format": "binary"},
                            "language_hint": {"type": "string", "enum": ["en", "hi", "ml"]},
                        },
                    }
                }
            },
        },
    },
)
async def transcribe(
    request: Request, response: Response, session: DB, user_id: PremiumUser
) -> Transcript | JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    settings = request.app.state.settings
    await run_in_threadpool(usage.use, session, settings, user_id, "voice")
    try:
        upload = await read_upload(request, settings.speech_max_audio_bytes)
        return await run_in_threadpool(
            transcribe_audio,
            audio=upload.audio,
            content_type=upload.content_type,
            settings=settings,
            language_hint=upload.language_hint,
        )
    except InvalidAudio as exc:
        return error_response(
            request,
            exc.status_code,
            "invalid_audio",
            "Audio must be a supported recording up to 3 MB and 30 seconds.",
        )


@router.post("/speak", response_class=Response, responses={200: {"content": {"audio/mpeg": {}}}})
def speak(body: SpeakRequest, request: Request, session: DB, user_id: PremiumUser) -> Response:
    usage.use(session, request.app.state.settings, user_id, "voice")
    try:
        audio = synthesize_speech(
            text=body.text, language=body.language, settings=request.app.state.settings
        )
        return Response(
            content=audio.data,
            media_type=audio.media_type,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
    except InvalidAudio as exc:
        return error_response(
            request, exc.status_code, "invalid_speech", "Speech text or language is invalid."
        )


@router.get("/threads", response_model=ThreadList)
def list_threads(response: Response, session: DB, user_id: CurrentUser) -> ThreadList:
    """The household's chats with FinBoy, newest first (web and WhatsApp)."""
    response.headers["Cache-Control"] = "no-store"
    found = history.threads(session, user_id)
    session.rollback()
    return ThreadList(
        threads=[ThreadSummary.model_validate(item, from_attributes=True) for item in found]
    )


@router.get("/threads/{thread_id}", response_model=ThreadDetail)
def get_thread(
    thread_id: UUID, request: Request, response: Response, session: DB, user_id: CurrentUser
) -> ThreadDetail | JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        thread = history.find(session, user_id, thread_id)
        rows = history.messages(session, user_id, thread_id)
    except LookupError:
        session.rollback()
        return _thread_missing(request)
    detail = ThreadDetail(
        thread=ThreadSummary(
            id=thread.id,
            channel=thread.channel,  # type: ignore[arg-type]
            title=thread.title or "",
            started_at=thread.started_at,
            last_at=thread.last_at,
            messages=len(rows),
        ),
        messages=[ThreadMessage.model_validate(row, from_attributes=True) for row in rows],
    )
    session.rollback()
    return detail


@router.delete("/threads/{thread_id}", status_code=204, response_class=Response)
def delete_thread(thread_id: UUID, request: Request, session: DB, user_id: CurrentUser) -> Response:
    try:
        history.delete_thread(session, user_id, thread_id)
    except LookupError:
        session.rollback()
        return _thread_missing(request)
    session.commit()
    return Response(status_code=204)


@router.delete("/threads", response_model=Deleted)
def delete_threads(session: DB, user_id: CurrentUser) -> Deleted:
    """Clear chat history. Memories stay; they are removed on the Memory page."""
    deleted = history.delete_all(session, user_id)
    session.commit()
    return Deleted(deleted=deleted)


@router.get("/suggestions", response_model=Suggestions)
def starter_suggestions(response: Response, session: DB, user_id: CurrentUser) -> Suggestions:
    """Starter questions from the household's own figures, with no model call."""
    response.headers["Cache-Control"] = "no-store"
    found = suggestions(EngineToolbox(session, user_id), today_ist())
    session.rollback()
    return Suggestions(suggestions=found)
