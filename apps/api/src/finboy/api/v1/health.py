from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from finboy.db.session import get_session
from finboy.services.health import HealthStatus, check_health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus, responses={503: {"model": HealthStatus}})
def health(response: Response, session: Annotated[Session, Depends(get_session)]) -> HealthStatus:
    result = check_health(session)
    response.status_code = 200 if result.status == "ok" else 503
    response.headers["Cache-Control"] = "no-store"
    return result
