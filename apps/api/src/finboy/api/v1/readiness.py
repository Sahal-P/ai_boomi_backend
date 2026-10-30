"""Operational readiness is separate from provider/live acceptance claims."""

import shutil
from typing import Annotated, Literal

from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from finboy.api.deps import CurrentUser
from finboy.core.config import API_ROOT, Settings
from finboy.db.models.mail import ImportRun
from finboy.db.session import get_session
from finboy.services.triage.provider import MODELS as DECISION_MODELS
from finboy.services.whatsapp.config import ChannelUnavailable, channel_config

router = APIRouter(tags=["readiness"])
SCHEMA_HEAD = ScriptDirectory(str(API_ROOT / "alembic")).get_current_head()


class Readiness(BaseModel):
    status: Literal["ready", "degraded"]
    database: Literal["connected", "unavailable"]
    schema_status: Literal["current", "unavailable"]
    speech_tools: Literal["available", "missing"]
    gmail_configuration: Literal["configured", "missing"]
    transcription_configuration: Literal["configured", "missing"]
    english_hindi_tts_configuration: Literal["configured", "missing"]
    malayalam_tts_configuration: Literal["configured", "missing"]
    whatsapp_configuration: Literal["disabled", "configured", "missing"]
    triage_configuration: Literal["off", "configured", "missing"]
    import_worker: Literal["in_process_not_durable"] = "in_process_not_durable"
    recorded_active_imports: int | None
    live_provider_acceptance: Literal["not_checked_by_readiness"] = "not_checked_by_readiness"


def _transcription(settings: Settings) -> bool:
    """Settings for every language the chosen provider routing can reach."""
    if settings.speech_transcribe_provider == "sarvam":
        return bool(settings.sarvam_api_key and settings.sarvam_stt_model)
    # Groq covers English/Hindi only; Malayalam and misdetections still go to OpenAI.
    openai = bool(settings.openai_api_key and settings.openai_transcribe_model)
    if settings.speech_transcribe_provider == "groq":
        return openai and bool(settings.groq_api_key and settings.groq_transcribe_model)
    return openai


def _malayalam_tts(settings: Settings) -> bool:
    if settings.malayalam_tts_provider == "sarvam":
        return bool(
            settings.sarvam_api_key and settings.sarvam_tts_model and settings.sarvam_tts_speaker_ml
        )
    return bool(settings.gemini_api_key and settings.gemini_tts_model and settings.gemini_tts_voice)


def _triage(settings: Settings) -> Literal["off", "configured", "missing"]:
    if not settings.triage_enabled:
        return "off"
    if settings.liquid_api_key and settings.liquid_decision_model in DECISION_MODELS:
        return "configured"
    return "missing"


@router.get("/readiness", response_model=Readiness)
def readiness(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    user_id: CurrentUser,
) -> Readiness:
    settings = request.app.state.settings
    database, schema, active = "connected", "unavailable", None
    try:
        session.execute(text("SELECT 1"))
        revision = session.scalar(text("SELECT version_num FROM alembic_version"))
        schema = "current" if revision == SCHEMA_HEAD else "unavailable"
        active = session.scalar(
            select(func.count())
            .select_from(ImportRun)
            .where(ImportRun.user_id == user_id, ImportRun.status.in_(["queued", "running"]))
        )
    except SQLAlchemyError:
        session.rollback()
        database = "unavailable"
    whatsapp = "disabled"
    if settings.whatsapp_enabled:
        try:
            channel_config(settings)
            whatsapp = "configured"
        except ChannelUnavailable:
            whatsapp = "missing"
    result = Readiness(
        status="ready" if database == "connected" and schema == "current" else "degraded",
        database=database,
        schema_status=schema,
        speech_tools="available"
        if shutil.which(settings.ffmpeg_binary) and shutil.which(settings.ffprobe_binary)
        else "missing",
        gmail_configuration="configured"
        if settings.google_oauth_client_id
        and settings.google_oauth_client_secret
        and settings.token_encryption_key
        and settings.google_oauth_redirect_uri
        else "missing",
        transcription_configuration="configured" if _transcription(settings) else "missing",
        english_hindi_tts_configuration="configured"
        if settings.resemble_api_key
        and settings.resemble_tts_model
        and settings.resemble_voice_uuid_en
        and settings.resemble_voice_uuid_hi
        else "missing",
        malayalam_tts_configuration="configured" if _malayalam_tts(settings) else "missing",
        whatsapp_configuration=whatsapp,
        triage_configuration=_triage(settings),
        recorded_active_imports=active,
    )
    response.status_code = 200 if result.status == "ready" else 503
    return result
