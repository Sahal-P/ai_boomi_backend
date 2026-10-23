import logging
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from finboy import __version__

logger = logging.getLogger(__name__)


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"]
    service: Literal["finboy-api"] = "finboy-api"
    version: str = __version__
    database: Literal["connected", "unavailable"]


def check_health(session: Session) -> HealthStatus:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("database.unavailable")
        return HealthStatus(status="degraded", database="unavailable")
    return HealthStatus(status="ok", database="connected")
