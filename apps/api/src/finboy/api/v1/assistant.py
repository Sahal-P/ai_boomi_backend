"""Thin HTTP boundaries over the same services used by WhatsApp."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from finboy.api.deps import DB, CurrentUser
from finboy.core.errors import error_response
from finboy.db.session import get_session
from finboy.services.accounts import usage
from finboy.services.assistant.models import AskRequest, AssistantAnswer, SpeakRequest
from finboy.services.assistant.service import answer_question
from finboy.services.money.compat import simulation_response
from finboy.services.speech.media import InvalidAudio
from finboy.services.speech.models import Transcript
from finboy.services.speech.multipart import read_upload
from finboy.services.speech.service import synthesize_speech, transcribe_audio

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/ask", response_model=AssistantAnswer)
def ask(
    body: AskRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    user_id: CurrentUser,
) -> AssistantAnswer:
    response.headers["Cache-Control"] = "no-store"
    usage.use(session, request.app.state.settings, user_id, "ai")
    result = answer_question(
        session,
        user_id=user_id,
        text=body.text,
        display_style=body.display_style,
        settings=request.app.state.settings,
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
    request: Request, response: Response, session: DB, user_id: CurrentUser
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
def speak(body: SpeakRequest, request: Request, session: DB, user_id: CurrentUser) -> Response:
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
