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
from finboy.core.config import API_ROOT
from finboy.db.models.mail import ImportRun
from finboy.db.session import get_session
from finboy.services import providers

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
    result = Readiness(
        status="ready" if database == "connected" and schema == "current" else "degraded",
        database=database,
        schema_status=schema,
        speech_tools="available"
        if shutil.which(settings.ffmpeg_binary) and shutil.which(settings.ffprobe_binary)
        else "missing",
        gmail_configuration="configured" if providers.gmail(settings) else "missing",
        transcription_configuration="configured"
        if providers.transcription(settings)
        else "missing",
        english_hindi_tts_configuration="configured"
        if providers.english_hindi_tts(settings)
        else "missing",
        malayalam_tts_configuration="configured"
        if providers.malayalam_tts(settings)
        else "missing",
        whatsapp_configuration=providers.whatsapp(settings),
        triage_configuration=providers.triage(settings),
        recorded_active_imports=active,
    )
    response.status_code = 200 if result.status == "ready" else 503
    return result
