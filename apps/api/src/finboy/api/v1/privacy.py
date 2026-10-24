from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.ledger import Transaction
from finboy.db.models.mail import AuditEvent
from finboy.db.session import get_session
from finboy.services.imports.locking import import_lock
from finboy.services.mail.http import MailRoute, failure
from finboy.services.mail.security import MailError
from finboy.services.privacy.audit import audit
from finboy.services.privacy.delete import delete_imported_data
from finboy.services.ux.contracts import (
    DeleteResult,
    DeletionPreview,
    IsolationInventory,
    TaskResult,
)
from finboy.services.ux.decisions import VersionRequest
from finboy.services.ux.privacy import (
    DeleteRequest,
    DeletionScope,
    TaskOutcome,
    deletion_preview,
    export_records,
    isolation_inventory,
)
from finboy.services.ux.state import TaskError, data_version, require_version

router = APIRouter(prefix="/privacy", tags=["privacy"], route_class=MailRoute)
DB = Annotated[Session, Depends(get_session)]


class AuditView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    subject_type: str
    subject_id: UUID
    created_at: datetime


@router.delete("/imported-data", response_model=None)
def delete_data(request: Request, session: DB) -> dict | JSONResponse:
    try:
        with import_lock(request.app.state.engine):
            delete_imported_data(session)
            session.commit()
        return {"status": "ok"}
    except MailError as exc:
        session.rollback()
        return failure(request, exc)


@router.get("/audit-events", response_model=list[AuditView])
def list_audit(
    session: DB,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
) -> list[AuditEvent]:
    return list(
        session.scalars(
            select(AuditEvent)
            .where(AuditEvent.user_id == LOCAL_USER_ID)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(max(1, min(limit, 200)))
            .offset(max(0, offset))
        )
    )


@router.post("/deletion-preview", response_model=DeletionPreview)
def preview_deletion(body: DeletionScope, session: DB) -> dict:
    require_version(session, LOCAL_USER_ID, data_version(session, LOCAL_USER_ID))
    return deletion_preview(session, user_id=LOCAL_USER_ID, connection_id=body.connection_id)


@router.post("/delete", response_model=DeleteResult)
def previewed_delete(body: DeleteRequest, request: Request, session: DB) -> dict:
    try:
        with import_lock(request.app.state.engine):
            require_version(session, LOCAL_USER_ID, body.expected_version)
            deletion_preview(session, user_id=LOCAL_USER_ID, connection_id=body.connection_id)
            delete_imported_data(session, connection_id=body.connection_id)
            session.flush()
            version = data_version(session, LOCAL_USER_ID)
            session.commit()
            return {"status": "ok", "data_version": version}
    except Exception:
        session.rollback()
        raise


@router.post("/export")
def export(body: VersionRequest, session: DB) -> JSONResponse:
    require_version(session, LOCAL_USER_ID, body.expected_version)
    return JSONResponse(
        content=export_records(session, user_id=LOCAL_USER_ID),
        headers={
            "Content-Disposition": 'attachment; filename="finboy-records.json"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/isolation", response_model=IsolationInventory)
def isolation(session: DB) -> dict:
    return isolation_inventory(session, user_id=LOCAL_USER_ID)


@router.post("/task-outcomes", response_model=TaskResult)
def task_outcome(body: TaskOutcome, session: DB) -> dict:
    if body.subject_id is not None:
        item = session.scalar(
            select(Transaction.id).where(
                Transaction.id == body.subject_id,
                Transaction.user_id == LOCAL_USER_ID,
                Transaction.dataset == "household",
            )
        )
        if item is None:
            raise TaskError("not_found")
    audit(
        session,
        "task." + body.task,
        "transaction" if body.subject_id else "user",
        body.subject_id or LOCAL_USER_ID,
    )
    session.commit()
    return {"status": "ok"}
