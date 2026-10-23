from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.mail import ImportRun
from finboy.db.session import get_session
from finboy.services.imports.files import demo_messages
from finboy.services.imports.runner import create_run, run_import
from finboy.services.imports.upload import read_eml_uploads
from finboy.services.ingestion.pipeline import InboundMessage
from finboy.services.mail.http import MailRoute, failure
from finboy.services.mail.security import MailError

router = APIRouter(prefix="/imports", tags=["imports"], route_class=MailRoute)
DB = Annotated[Session, Depends(get_session)]


class ImportView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mode: str
    status: str
    headers_checked: int
    candidates_found: int
    emails_processed: int
    events_extracted: int
    transactions_created: int
    duplicates_merged: int
    needs_review: int
    non_financial_skipped: int
    failed: int
    error_code: str | None


@router.post("/demo", status_code=202, response_model=None)
def start_demo(request: Request, background: BackgroundTasks, session: DB) -> dict | JSONResponse:
    try:
        messages = demo_messages()
        run = create_run(session, mode="demo_mailbox")
        background.add_task(
            run_import, request.app.state.engine, request.app.state.settings, run.id, messages
        )
        return {"import_run_id": str(run.id)}
    except MailError as exc:
        session.rollback()
        return failure(request, exc)


async def uploads(request: Request) -> list[InboundMessage]:
    return await read_eml_uploads(request)


@router.post(
    "/eml",
    status_code=202,
    response_model=None,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["files"],
                        "properties": {
                            "files": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 50,
                                "items": {"type": "string", "format": "binary"},
                            },
                        },
                    }
                }
            },
        },
    },
)
def start_eml(
    request: Request,
    background: BackgroundTasks,
    session: DB,
    messages: Annotated[list[InboundMessage], Depends(uploads)],
) -> dict | JSONResponse:
    try:
        run = create_run(session, mode="eml_upload")
        background.add_task(
            run_import, request.app.state.engine, request.app.state.settings, run.id, messages
        )
        return {"import_run_id": str(run.id)}
    except MailError as exc:
        session.rollback()
        return failure(request, exc)


@router.get("/{run_id}", response_model=ImportView)
def get_import(run_id: UUID, session: DB) -> ImportRun:
    run = session.scalar(
        select(ImportRun).where(ImportRun.id == run_id, ImportRun.user_id == LOCAL_USER_ID)
    )
    if run is None:
        raise HTTPException(404)
    return run
