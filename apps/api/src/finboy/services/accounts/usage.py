"""Daily AI and voice allowances per household, so an open beta has a predictable cost.

Counts only (docs/signup-round/contract.md). The owner's household is not limited.
"""

from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from finboy.core.clock import today_ist
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.core.errors import AccessError
from finboy.db.models.accounts import UsageCounter

Kind = Literal["ai", "voice"]


def use(session: Session, settings: Settings, user_id: UUID, kind: Kind) -> None:
    """Count one request for today; past the household's daily limit, refuse it."""
    if user_id == LOCAL_USER_ID:
        return
    count = session.scalar(
        insert(UsageCounter)
        .values(user_id=user_id, day=today_ist(), kind=kind, count=1)
        .on_conflict_do_update(
            index_elements=[UsageCounter.user_id, UsageCounter.day, UsageCounter.kind],
            set_={"count": UsageCounter.count + 1},
        )
        .returning(UsageCounter.count)
    )
    session.commit()
    limit = settings.daily_ai_limit if kind == "ai" else settings.daily_voice_limit
    if isinstance(count, int) and count > limit:
        raise AccessError("usage_limit")


def today(session: Session, user_id: UUID) -> dict[Kind, int]:
    """Today's counts for the admin panel (docs/admin-round/contract.md); reading never counts."""
    counts: dict[Kind, int] = {"ai": 0, "voice": 0}
    for kind, count in session.execute(
        select(UsageCounter.kind, UsageCounter.count).where(
            UsageCounter.user_id == user_id, UsageCounter.day == today_ist()
        )
    ):
        counts[kind] = count
    return counts
