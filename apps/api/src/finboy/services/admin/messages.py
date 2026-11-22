"""A household's kept messages for the admin panel (docs/conversation-round/contract.md).

Only a household that agreed has any. WhatsApp messages carry their delivery or read state, and
the household's Ask chats on the web are merged in from the day it agreed. The routes record
every page and every file opened in the admin audit log.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.db.models.advisor import AdvisorMessage, AdvisorThread
from finboy.db.models.conversations import ConversationMessage
from finboy.db.models.core import User
from finboy.db.models.whatsapp import WhatsAppDelivery, WhatsAppReceipt
from finboy.services.admin.views import MessagePage, MessageRow, MessageState
from finboy.services.conversations import r2
from finboy.services.conversations.store import clean

PAGE = 50


@dataclass(frozen=True)
class Media:
    user_id: UUID
    content_type: str
    data: bytes


def state(session: Session, user_id: UUID) -> MessageState:
    row = session.execute(
        select(User.messages_kept_from, User.messages_declined_at).where(User.id == user_id)
    ).one()
    count = session.scalar(
        select(func.count())
        .select_from(ConversationMessage)
        .where(ConversationMessage.user_id == user_id)
    )
    return MessageState(
        kept_from=row.messages_kept_from, declined_at=row.messages_declined_at, count=count or 0
    )


def cursor(row: MessageRow) -> str:
    """Where the next page starts: the oldest message shown, by time and then ID, since several
    WhatsApp messages can carry the same second."""
    return f"{row.at.isoformat()}|{row.id}"


def _after(value: str) -> tuple[datetime, UUID]:
    at, _, ident = value.partition("|")
    try:
        return datetime.fromisoformat(at), UUID(ident)
    except ValueError:
        raise AccessError("not_found") from None


def page(session: Session, user_id: UUID, before: str | None) -> MessagePage:
    """Newest first, 50 at a time; `next_before` continues from the oldest one shown."""
    known = session.execute(
        select(User.messages_kept_from, User.messages_declined_at).where(User.id == user_id)
    ).one_or_none()
    if known is None:
        raise LookupError(user_id)
    edge = _after(before) if before is not None else None
    found = (
        select(ConversationMessage, WhatsAppDelivery.provider_status, WhatsAppReceipt.error_code)
        .outerjoin(WhatsAppDelivery, WhatsAppDelivery.id == ConversationMessage.delivery_id)
        .outerjoin(WhatsAppReceipt, WhatsAppReceipt.id == ConversationMessage.receipt_id)
        .where(ConversationMessage.user_id == user_id)
    )
    if edge is not None:
        found = found.where(tuple_(ConversationMessage.created_at, ConversationMessage.id) < edge)
    rows = [
        _whatsapp(message, provider_status, error_code)
        for message, provider_status, error_code in session.execute(
            found.order_by(
                ConversationMessage.created_at.desc(), ConversationMessage.id.desc()
            ).limit(PAGE + 1)
        )
    ]
    if known.messages_kept_from is not None:
        web = (
            select(AdvisorMessage)
            .join(AdvisorThread, AdvisorThread.id == AdvisorMessage.thread_id)
            .where(
                AdvisorMessage.user_id == user_id,
                AdvisorThread.channel == "web",
                AdvisorMessage.created_at >= known.messages_kept_from,
            )
        )
        if edge is not None:
            web = web.where(tuple_(AdvisorMessage.created_at, AdvisorMessage.id) < edge)
        rows += [
            _web(message)
            for message in session.scalars(
                web.order_by(AdvisorMessage.created_at.desc(), AdvisorMessage.id.desc()).limit(
                    PAGE + 1
                )
            )
        ]
    rows.sort(key=lambda item: (item.at, item.id), reverse=True)
    shown = rows[:PAGE]
    return MessagePage(
        kept_from=known.messages_kept_from,
        declined_at=known.messages_declined_at,
        items=shown,
        next_before=cursor(shown[-1]) if len(rows) > PAGE else None,
    )


def _whatsapp(
    message: ConversationMessage, provider_status: str | None, error_code: str | None
) -> MessageRow:
    sent = message.direction == "out"
    return MessageRow(
        id=message.id,
        at=message.created_at,
        channel="whatsapp",
        direction="out" if sent else "in",
        kind=message.kind,
        text=message.text,
        transcript=message.transcript,
        language=message.language,
        choices=message.choices,
        media=_media_kind(message.media_type) if message.media_key else None,
        media_bytes=message.media_bytes if message.media_key else None,
        status=(provider_status or message.outcome) if sent else None,
        outcome=None if sent else error_code,
    )


def _web(message: AdvisorMessage) -> MessageRow:
    return MessageRow(
        id=message.id,
        at=message.created_at,
        channel="web",
        direction="in" if message.role == "user" else "out",
        kind="text",
        text=clean(message.text),
        transcript=None,
        language=message.language,
        choices=[],
        media=None,
        media_bytes=None,
        status=None,
        outcome=None,
    )


def _media_kind(content_type: str | None) -> Literal["audio", "image"] | None:
    if content_type is None:
        return None
    return "audio" if content_type.startswith("audio/") else "image"


def media(session: Session, settings: Settings, message_id: UUID) -> Media:
    """A kept voice note or photo, read from R2 for an admin; nothing is cached."""
    row = session.execute(
        select(
            ConversationMessage.user_id,
            ConversationMessage.media_key,
            ConversationMessage.media_type,
        ).where(ConversationMessage.id == message_id)
    ).one_or_none()
    if row is None or row.media_key is None or row.media_type not in r2.EXTENSIONS:
        raise AccessError("not_found")
    try:
        data = r2.get(settings, row.media_key)
    except r2.StoreUnavailable:
        raise AccessError("media_unavailable") from None
    return Media(row.user_id, row.media_type, data)
