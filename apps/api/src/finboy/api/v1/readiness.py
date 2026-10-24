"""Operational readiness is separate from provider/live acceptance claims."""

import shutil
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.mail import ImportRun
from finboy.db.session import get_session
from finboy.services.whatsapp.config import ChannelUnavailable, channel_config

router = APIRouter(tags=["readiness"])


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
    import_worker: Literal["in_process_not_durable"] = "in_process_not_durable"
    recorded_active_imports: int | None
    live_provider_acceptance: Literal["not_checked_by_readiness"] = "not_checked_by_readiness"


@router.get("/readiness", response_model=Readiness)
def readiness(
    request: Request, response: Response, session: Annotated[Session, Depends(get_session)]
) -> Readiness:
    settings = request.app.state.settings
    database, schema, active = "connected", "unavailable", None
    try:
        session.execute(text("SELECT 1"))
        revision = session.scalar(text("SELECT version_num FROM alembic_version"))
        schema = "current" if revision == "0006_event_origins" else "unavailable"
        active = session.scalar(
            select(func.count())
            .select_from(ImportRun)
            .where(ImportRun.user_id == LOCAL_USER_ID, ImportRun.status.in_(["queued", "running"]))
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
        transcription_configuration="configured"
        if settings.openai_api_key and settings.openai_transcribe_model
        else "missing",
        english_hindi_tts_configuration="configured"
        if settings.resemble_api_key
        and settings.resemble_tts_model
        and settings.resemble_voice_uuid_en
        and settings.resemble_voice_uuid_hi
        else "missing",
        malayalam_tts_configuration="configured"
        if settings.gemini_api_key and settings.gemini_tts_model and settings.gemini_tts_voice
        else "missing",
        whatsapp_configuration=whatsapp,
        recorded_active_imports=active,
    )
    response.status_code = 200 if result.status == "ready" else 503
    return result
