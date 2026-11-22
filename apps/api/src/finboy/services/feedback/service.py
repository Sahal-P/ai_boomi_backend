"""Feedback households send from the web app, and its screenshots (docs/feedback-round/contract.md).

The message is written for the FinBoy team and read in the admin panel; it is never logged. A
screenshot is checked by its first bytes (PNG, JPEG or WebP; the browser has already redrawn it,
which drops location and other metadata) and kept in the private R2 bucket under a key built
from IDs. The owner gets an email that names the type and links to it, never its words.
"""

import base64
import binascii
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session, sessionmaker

from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.db.models.feedback import MAX_PAGE, Feedback
from finboy.services.conversations import r2
from finboy.services.outbound_email import resend, templates

logger = logging.getLogger(__name__)

DAILY_LIMIT = 10
MAX_SCREENSHOT = 1_500_000
LISTED = 50


class FeedbackError(Exception):
    """Why a report could not be taken: a fixed code, never the message."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _looks_like(content_type: str, data: bytes) -> bool:
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def screenshot(content_type: str, encoded: str) -> bytes:
    """The decoded image, only when it is what it says it is and small enough."""
    try:
        data = base64.b64decode(encoded, validate=True)
    except binascii.Error, ValueError:
        raise FeedbackError("invalid_screenshot") from None
    if len(data) > MAX_SCREENSHOT:
        raise FeedbackError("screenshot_too_large")
    if not data or not _looks_like(content_type, data):
        raise FeedbackError("invalid_screenshot")
    return data


def app_path(page: str) -> str:
    """Only the app path the report came from: no origin, query string or fragment."""
    path = page.split("?", 1)[0].split("#", 1)[0].strip()
    return path[:MAX_PAGE] if path.startswith("/") and not path.startswith("//") else ""


def listed(session: Session, user_id: UUID) -> list[Feedback]:
    return list(
        session.scalars(
            select(Feedback)
            .where(Feedback.user_id == user_id)
            .order_by(Feedback.created_at.desc(), Feedback.id)
            .limit(LISTED)
        )
    )


def create(
    session: Session,
    settings: Settings,
    user_id: UUID,
    *,
    kind: str,
    message: str,
    page: str,
    image: tuple[str, bytes] | None,
) -> tuple[Feedback, bool]:
    """Keep a report, then its screenshot. Returns the row and whether the screenshot (if any)
    was kept: a report is never lost because R2 could not take its picture."""
    day_ago = datetime.now(UTC) - timedelta(days=1)
    sent = session.scalar(
        select(func.count())
        .select_from(Feedback)
        .where(Feedback.user_id == user_id, Feedback.created_at >= day_ago)
    )
    if (sent or 0) >= DAILY_LIMIT:
        raise FeedbackError("feedback_limit")
    row = Feedback(id=uuid4(), user_id=user_id, kind=kind, message=message, page=app_path(page))
    session.add(row)
    session.commit()
    if image is None:
        return row, True
    if not r2.configured(settings):
        return row, False
    content_type, data = image
    key = f"{settings.feedback_prefix}{user_id}/{row.id}.{r2.EXTENSIONS[content_type]}"
    try:
        r2.put(settings, key, data, content_type)
    except r2.StoreUnavailable:
        logger.warning("feedback.screenshot_failed", extra={"stage": "put"})
        return row, False
    row.screenshot_key, row.screenshot_type, row.screenshot_bytes = key, content_type, len(data)
    session.commit()
    return row, True


def remove(session: Session, settings: Settings, user_id: UUID, feedback_id: UUID) -> bool:
    """A household deletes one of its own reports, its screenshot first."""
    row = session.scalar(
        select(Feedback).where(Feedback.id == feedback_id, Feedback.user_id == user_id)
    )
    if row is None:
        return False
    if row.screenshot_key:
        if not r2.configured(settings):
            raise AccessError("try_later")
        try:
            r2.delete(settings, row.screenshot_key)
        except r2.StoreUnavailable:
            raise AccessError("try_later") from None
    session.delete(row)
    return True


def remove_all(session: Session, settings: Settings | None, user_id: UUID) -> int:
    """Erasure: the household's screenshot folder, then its reports. Raises
    AccessError("try_later") while R2 can't be reached, so no file outlives its row."""
    mine = Feedback.user_id == user_id
    if not session.scalar(select(exists().where(mine))):
        return 0
    if settings is not None and r2.configured(settings):
        try:
            r2.delete_folder(settings, user_id, settings.feedback_prefix)
        except r2.StoreUnavailable:
            raise AccessError("try_later") from None
    elif session.scalar(select(exists().where(mine, Feedback.screenshot_key.is_not(None)))):
        raise AccessError("try_later")
    return session.execute(delete(Feedback).where(mine)).rowcount or 0


def notify(factory: sessionmaker[Session], settings: Settings, feedback_id: UUID) -> None:
    """After the reply: the owner's email about a new report. Best effort, sent once."""
    if not settings.feedback_email or not settings.resend_api_key:
        return
    with factory() as session:
        row = session.get(Feedback, feedback_id)
        if row is None or row.notified_at is not None:
            return
        origin = str(settings.web_app_url).rstrip("/") if settings.web_app_url else None
        message = templates.feedback_received(
            kind=row.kind,
            link=f"{origin}/admin/feedback?open={row.id}" if origin else None,
            screenshot=row.screenshot_key is not None,
        )
        try:
            resend.send(settings, settings.feedback_email, message, row.id)
        except Exception:
            logger.warning("feedback.notify_failed", extra={"stage": "email"})
            return
        row.notified_at = datetime.now(UTC)
        session.commit()
