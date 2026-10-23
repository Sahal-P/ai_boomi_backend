from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.mail import AuditEvent
from finboy.db.session import get_session
from finboy.services.imports.locking import import_lock
from finboy.services.mail.http import failure
from finboy.services.mail.security import MailError
from finboy.services.privacy.delete import delete_imported_data

router = APIRouter(prefix="/privacy", tags=["privacy"])
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
def list_audit(session: DB, limit: int = 100, offset: int = 0) -> list[AuditEvent]:
    return list(
        session.scalars(
            select(AuditEvent)
            .where(AuditEvent.user_id == LOCAL_USER_ID)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(max(1, min(limit, 200)))
            .offset(max(0, offset))
        )
    )
