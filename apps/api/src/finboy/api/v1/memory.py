"""The household's memory: see, edit and delete what FinBoy remembers, or turn it off.

docs/advisor-round/contract.md. Every household can use it. Memories are written by the advisor
while it answers; here the household manages them, like ChatGPT's "Manage memories".
"""

from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from finboy.api.deps import DB, CurrentUser
from finboy.core.errors import error_response
from finboy.db.models.advisor import AdvisorThread
from finboy.services.advisor import memory
from finboy.services.advisor.memory import MemoryView

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryList(BaseModel):
    enabled: bool
    limit: int
    memories: list[MemoryView]
    chats: int


class MemoryEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=memory.MAX_TEXT)


class MemorySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = Field(strict=True)


class Deleted(BaseModel):
    deleted: int


def _missing(request: Request) -> JSONResponse:
    return error_response(request, 404, "memory_not_found", "That memory was not found.")


@router.get("", response_model=MemoryList)
def list_memories(
    request: Request, response: Response, session: DB, user_id: CurrentUser
) -> MemoryList:
    response.headers["Cache-Control"] = "no-store"
    result = MemoryList(
        enabled=memory.enabled(session, user_id),
        limit=request.app.state.settings.advisor_memory_limit,
        memories=[memory.view(row) for row in memory.listed(session, user_id)],
        chats=session.scalar(select(func.count()).where(AdvisorThread.user_id == user_id)) or 0,
    )
    session.rollback()
    return result


@router.patch("/{memory_id}", response_model=MemoryView)
def edit_memory(
    memory_id: UUID, body: MemoryEdit, request: Request, session: DB, user_id: CurrentUser
) -> MemoryView | JSONResponse:
    try:
        row = memory.edit(session, user_id, memory_id, body.text)
    except ValueError:
        session.rollback()
        return error_response(
            request,
            422,
            "invalid_memory",
            "A memory must be a short fact without OTPs, PINs, passwords or account numbers.",
        )
    if row is None:
        session.rollback()
        return _missing(request)
    session.commit()
    return memory.view(row)


@router.delete("/{memory_id}", status_code=204, response_class=Response)
def delete_memory(memory_id: UUID, request: Request, session: DB, user_id: CurrentUser) -> Response:
    if not memory.forget(session, user_id, memory_id):
        session.rollback()
        return _missing(request)
    session.commit()
    return Response(status_code=204)


@router.delete("", response_model=Deleted)
def delete_memories(session: DB, user_id: CurrentUser) -> Deleted:
    deleted = memory.forget_all(session, user_id)
    session.commit()
    return Deleted(deleted=deleted)


@router.put("/settings", response_model=MemorySettings)
def memory_settings(body: MemorySettings, session: DB, user_id: CurrentUser) -> MemorySettings:
    memory.set_enabled(session, user_id, body.enabled)
    session.commit()
    return MemorySettings(enabled=body.enabled)
