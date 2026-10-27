from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finboy.api.deps import CurrentUser
from finboy.db.models.mail import ImportRun
from finboy.db.session import get_session
from finboy.services.imports.runner import create_run, run_import
from finboy.services.imports.upload import read_eml_uploads
from finboy.services.ingestion.pipeline import InboundMessage
from finboy.services.mail.http import MailRoute, failure
from finboy.services.mail.security import MailError
from finboy.services.ux.contracts import ImportPage, ImportStarted, IssuePage
from finboy.services.ux.decisions import VersionRequest
from finboy.services.ux.imports import (
    ImportView,
    RetryRequest,
    import_view,
    issues,
    recover_interrupted,
    retry_sources,
    run_for,
)
from finboy.services.ux.state import TaskError, require_version

router = APIRouter(prefix="/imports", tags=["imports"], route_class=MailRoute)
DB = Annotated[Session, Depends(get_session)]


@router.post("/demo", response_model=None)
def start_demo() -> None:
    raise TaskError("demo_read_only")


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
    user_id: CurrentUser,
    messages: Annotated[list[InboundMessage], Depends(uploads)],
) -> dict | JSONResponse:
    try:
        run = create_run(session, mode="eml_upload", user_id=user_id)
        background.add_task(
            run_import, request.app.state.engine, request.app.state.settings, run.id, messages
        )
        return {"import_run_id": str(run.id)}
    except MailError as exc:
        session.rollback()
        return failure(request, exc)


@router.get("", response_model=ImportPage)
def list_imports(
    request: Request,
    session: DB,
    user_id: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
) -> dict:
    recover_interrupted(session, request.app.state.engine, user_id)
    condition = [ImportRun.user_id == user_id, ImportRun.mode != "demo_mailbox"]
    total = session.scalar(select(func.count()).select_from(ImportRun).where(*condition)) or 0
    rows = list(
        session.scalars(
            select(ImportRun)
            .where(*condition)
            .order_by(ImportRun.started_at.desc().nullslast(), ImportRun.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return {
        "items": [import_view(session, row) for row in rows],
        "total": total,
        "next_offset": offset + len(rows) if offset + len(rows) < total else None,
    }


@router.get("/{run_id}", response_model=ImportView)
def get_import(run_id: UUID, request: Request, session: DB, user_id: CurrentUser) -> ImportView:
    recover_interrupted(session, request.app.state.engine, user_id)
    return import_view(session, run_for(session, run_id, user_id))


@router.get("/{run_id}/issues", response_model=IssuePage)
def list_issues(
    run_id: UUID,
    session: DB,
    user_id: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
) -> dict:
    return issues(session, user_id=user_id, run_id=run_id, limit=limit, offset=offset)


@router.post("/{run_id}/retry", status_code=202, response_model=ImportStarted)
def retry(
    run_id: UUID,
    body: RetryRequest,
    request: Request,
    background: BackgroundTasks,
    session: DB,
    user_id: CurrentUser,
) -> dict:
    original, source_ids = retry_sources(session, user_id=user_id, run_id=run_id, request=body)
    run = create_run(
        session, mode="gmail", connection_id=original.mail_connection_id, user_id=user_id
    )
    run.retry_source_ids = [str(key) for key in source_ids]
    session.commit()
    background.add_task(run_import, request.app.state.engine, request.app.state.settings, run.id)
    return {"import_run_id": str(run.id)}


@router.post("/{run_id}/cancel", response_model=ImportView)
def cancel(run_id: UUID, body: VersionRequest, session: DB, user_id: CurrentUser) -> ImportView:
    # Progress changes continuously; a monotonic cancellation flag cannot overwrite it.
    from finboy.services.ingestion.pipeline import _user_lock

    _user_lock(session, user_id)
    row = run_for(session, run_id, user_id)
    if row.status not in {"queued", "running"}:
        return import_view(session, row)
    row.cancel_requested = True
    if row.status == "queued":
        from finboy.core.clock import now_ist

        row.status, row.outcome_detail, row.error_code, row.finished_at = (
            "failed",
            "cancelled",
            "import_failed",
            now_ist(),
        )
    session.flush()
    result = import_view(session, row)
    session.commit()
    return result


@router.post("/{run_id}/continue", status_code=202, response_model=ImportStarted)
def continue_scan(
    run_id: UUID,
    body: VersionRequest,
    request: Request,
    background: BackgroundTasks,
    session: DB,
    user_id: CurrentUser,
) -> dict:
    require_version(session, user_id, body.expected_version)
    original = run_for(session, run_id, user_id)
    if (
        original.mode != "gmail"
        or original.status != "completed"
        or not original.truncated
        or not original.next_page_token_encrypted
    ):
        raise TaskError("invalid_decision")
    connection_id = original.mail_connection_id
    token, start, end = (
        original.next_page_token_encrypted,
        original.window_start,
        original.window_end,
    )
    run = create_run(session, mode="gmail", connection_id=connection_id, user_id=user_id)
    run.resume_page_token_encrypted, run.window_start, run.window_end = token, start, end
    session.commit()
    background.add_task(run_import, request.app.state.engine, request.app.state.settings, run.id)
    return {"import_run_id": str(run.id)}
