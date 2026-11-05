"""The admin audit log (docs/admin-round/contract.md): fixed actions and allowlisted details.

Kept apart from the household `audit_events`, which households read on their own Privacy page and
which records no actor. The caller commits, so an action and its entry land together.
"""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from finboy.db.models.admin import ACTIONS, AdminEvent

logger = logging.getLogger(__name__)

# Detail never holds contact details, amounts of a household's records or free text.
DETAIL = {"days", "payment", "admin", "removed", "via", "outcome"}


def record(
    session: Session,
    action: str,
    *,
    admin_id: UUID | None,
    household_id: UUID | None = None,
    request_id: str | None = None,
    **detail: str | int,
) -> None:
    if action not in ACTIONS:
        raise ValueError("unknown admin action")
    if set(detail) - DETAIL:
        raise ValueError("unknown admin detail")
    session.add(
        AdminEvent(
            admin_id=admin_id,
            action=action,
            household_id=household_id,
            detail=detail,
            request_id=request_id,
        )
    )
    logger.info("admin.action", extra={"code": action})
