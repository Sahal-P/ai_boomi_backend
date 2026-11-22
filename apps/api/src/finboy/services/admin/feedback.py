"""Household feedback for the FinBoy team (docs/feedback-round/contract.md).

The list shows who sent what kind of report and its status, not its words; reading one report,
opening its screenshot and changing its status are each recorded in the audit log by the route.
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.db.models.core import User
from finboy.db.models.feedback import Feedback
from finboy.services.admin.views import FeedbackDetail, FeedbackPage, FeedbackRow
from finboy.services.conversations import r2

PAGE = 50
Status = Literal["new", "planned", "done"]


def _row(row: Feedback, name: str | None) -> FeedbackRow:
    return FeedbackRow(
        id=row.id,
        household_id=row.user_id,
        short_id=row.user_id.hex[:8],
        household_name=name,
        kind=row.kind,  # type: ignore[arg-type]
        status=row.status,  # type: ignore[arg-type]
        has_screenshot=row.screenshot_key is not None,
        created_at=row.created_at,
    )


def new_count(session: Session) -> int:
    return session.scalar(select(func.count()).where(Feedback.status == "new")) or 0


def page(session: Session, status: Status | None, offset: int) -> FeedbackPage:
    query = select(Feedback, User.display_name).join(User, User.id == Feedback.user_id)
    counted = select(func.count()).select_from(Feedback)
    if status is not None:
        query = query.where(Feedback.status == status)
        counted = counted.where(Feedback.status == status)
    found = session.execute(
        query.order_by(Feedback.created_at.desc(), Feedback.id).offset(offset).limit(PAGE)
    ).all()
    total = session.scalar(counted) or 0
    following = offset + PAGE
    return FeedbackPage(
        items=[_row(row, name) for row, name in found],
        total=total,
        offset=offset,
        next_offset=following if following < total else None,
        new=new_count(session),
    )


def detail(session: Session, feedback_id: UUID) -> FeedbackDetail:
    found = session.execute(
        select(Feedback, User.display_name)
        .join(User, User.id == Feedback.user_id)
        .where(Feedback.id == feedback_id)
    ).one_or_none()
    if found is None:
        raise AccessError("not_found")
    row, name = found
    return FeedbackDetail(
        **_row(row, name).model_dump(),
        message=row.message,
        page=row.page,
        status_changed_at=row.status_changed_at,
    )


def set_status(session: Session, feedback_id: UUID, status: Status) -> FeedbackDetail:
    row = session.get(Feedback, feedback_id)
    if row is None:
        raise AccessError("not_found")
    if row.status != status:
        row.status, row.status_changed_at = status, datetime.now(UTC)
        session.flush()
    return detail(session, feedback_id)


def screenshot(session: Session, settings: Settings, feedback_id: UUID) -> tuple[UUID, str, bytes]:
    """A report's screenshot read from R2 for an admin; nothing is cached."""
    row = session.get(Feedback, feedback_id)
    if row is None or row.screenshot_key is None or row.screenshot_type not in r2.EXTENSIONS:
        raise AccessError("not_found")
    try:
        data = r2.get(settings, row.screenshot_key)
    except r2.StoreUnavailable:
        raise AccessError("media_unavailable") from None
    return row.user_id, row.screenshot_type, data
