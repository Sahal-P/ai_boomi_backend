"""The message log (docs/conversation-round/contract.md): what FinBoy keeps, and its removal.

Only a household that agreed is recorded (`users.messages_kept_from`; the owner always has), and
only while CONVERSATION_LOG_ENABLED is on. Writing is best effort: a failure is logged with a
fixed stage and never changes or delays a reply. Voice notes and photos go to R2 after the reply
has been sent. Removal deletes the household's R2 folder before its rows, so no file can outlive
the row that points to it.
"""

import logging
import re
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Connection, Engine, delete, exists, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.db.models.conversations import ConversationMessage
from finboy.db.models.core import User
from finboy.services.accounts.login import read_code
from finboy.services.conversations import r2
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.meta import DownloadedMedia
from finboy.services.whatsapp.prompts import parse
from finboy.services.whatsapp.statement import mask

logger = logging.getLogger(__name__)
# A UPI ID's handle has no dot (name@okhdfcbank, 98xxxxxx@ybl); an email address's domain has one.
UPI_ID = re.compile(r"(?<![\w.@-])[\w.-]{2,64}@[a-z][a-z0-9]{1,31}(?![\w.@-])", re.IGNORECASE)
INBOUND = {"text": "text", "audio": "voice", "image": "photo", "document": "document"}
LIMIT = 4096


def clean(text: str | None) -> str | None:
    """Ready to keep: a login code becomes "[login code]"; UPI IDs and account, card, reference
    and phone numbers are masked. Amounts, names and words stay as they were written."""
    if not text or not text.strip():
        return None
    if read_code(text) is not None:
        return "[login code]"
    return mask(UPI_ID.sub("[UPI ID]", text))[:LIMIT]


def kept_from(session: Session, enabled: bool, user_id: UUID) -> datetime | None:
    """From when this household's messages are kept, or None: CONVERSATION_LOG_ENABLED off
    (`enabled`), never agreed, declined, deleted or suspended."""
    if not enabled:
        return None
    row = session.execute(
        select(User.messages_kept_from, User.deleted_at, User.suspended_at).where(
            User.id == user_id
        )
    ).one_or_none()
    if row is None or row.deleted_at is not None or row.suspended_at is not None:
        return None
    return row.messages_kept_from


def _add(session: Session, row: ConversationMessage, stage: str) -> None:
    """Inside the caller's transaction, behind a savepoint, so a failed write rolls back alone."""
    try:
        with session.begin_nested():
            session.add(row)
    except SQLAlchemyError:
        logger.warning("conversation.log_failed", extra={"stage": stage})


def add_inbound(
    session: Session,
    enabled: bool,
    *,
    user_id: UUID,
    receipt_id: UUID,
    question: InboundQuestion,
) -> None:
    """What the household sent, beside its receipt in the webhook's transaction. A tap keeps
    its choice ("agree", "undo"…); a voice note or photo gets its file after the reply."""
    if kept_from(session, enabled, user_id) is None:
        return
    tapped = parse(question.button_id or "") if question.kind == "button" else None
    kind = "command" if question.command else INBOUND.get(question.kind, "tap")
    _add(
        session,
        ConversationMessage(
            user_id=user_id,
            receipt_id=receipt_id,
            direction="in",
            kind=kind,
            text=clean(question.text) if question.kind == "text" else None,
            choices=[tapped[1]] if tapped else [],
            created_at=question.provider_at,
        ),
        "inbound",
    )


def add_sent(
    session: Session,
    enabled: bool,
    *,
    user_id: UUID,
    kind: str,
    text: str | None,
    outcome: str,
    choices: Sequence[str] = (),
    receipt_id: UUID | None = None,
    delivery_id: UUID | None = None,
    language: str | None = None,
) -> None:
    """What FinBoy sent: a reply, its spoken words, a template or a coach message. The caller
    commits, so the row lands with the send's own state."""
    if kept_from(session, enabled, user_id) is None:
        return
    _add(
        session,
        ConversationMessage(
            user_id=user_id,
            receipt_id=receipt_id,
            delivery_id=delivery_id,
            direction="out",
            kind=kind,
            text=clean(text),
            choices=list(choices),
            language=language if language in {"en", "hi", "ml"} else None,
            outcome=outcome,
        ),
        kind,
    )


def note_transcript(
    bind: Engine | Connection, receipt_id: UUID, transcript: str, language: str | None
) -> None:
    """What speech-to-text heard, in its own session, so a later rollback can't drop it."""
    try:
        with Session(bind) as session:
            session.execute(
                update(ConversationMessage)
                .where(
                    ConversationMessage.receipt_id == receipt_id,
                    ConversationMessage.direction == "in",
                )
                .values(
                    transcript=clean(transcript),
                    language=language if language in {"en", "hi", "ml"} else None,
                )
            )
            session.commit()
    except SQLAlchemyError:
        logger.warning("conversation.log_failed", extra={"stage": "transcript"})


def keep_downloads(
    session: Session,
    settings: Settings,
    receipt_id: UUID,
    downloads: Sequence[DownloadedMedia],
) -> None:
    """After the reply, in a fresh session the caller owns: the voice note or photo this message
    carried goes to R2. Statement PDFs are never kept."""
    media = next((item for item in downloads if item.content_type in r2.EXTENSIONS), None)
    if media is None or not settings.conversation_log_enabled or not r2.configured(settings):
        return
    try:
        row = session.scalar(
            select(ConversationMessage).where(
                ConversationMessage.receipt_id == receipt_id,
                ConversationMessage.direction == "in",
                ConversationMessage.kind.in_(("voice", "photo")),
                ConversationMessage.media_key.is_(None),
            )
        )
        if row is None:
            return
        key = r2.key_for(settings, row.user_id, row.id, media.content_type)
        r2.put(settings, key, media.data, media.content_type)
        row.media_key = key
        row.media_type = media.content_type
        row.media_bytes = len(media.data)
        session.commit()
    except SQLAlchemyError, r2.StoreUnavailable:
        session.rollback()
        logger.warning("conversation.log_failed", extra={"stage": "media"})


def remove(session: Session, settings: Settings | None, user_id: UUID) -> int:
    """Clear one household's log: its R2 folder first, then its rows. Used by every erasure and
    by "clear chat history". Raises AccessError("try_later") while R2 can't be reached, or when
    files exist but R2 isn't configured, so no file is ever left without its row."""
    mine = ConversationMessage.user_id == user_id
    if not session.scalar(select(exists().where(mine))):
        return 0
    if settings is not None and r2.configured(settings):
        try:
            r2.delete_folder(settings, user_id)
        except r2.StoreUnavailable:
            raise AccessError("try_later") from None
    elif session.scalar(select(exists().where(mine, ConversationMessage.media_key.is_not(None)))):
        raise AccessError("try_later")
    return session.execute(delete(ConversationMessage).where(mine)).rowcount or 0


def exported(session: Session, user_id: UUID) -> list[dict[str, object]]:
    """The household's own copy for "Export": words and transcripts, never the files."""
    rows = session.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.user_id == user_id)
        .order_by(ConversationMessage.created_at, ConversationMessage.id)
    )
    return [
        {
            "at": row.created_at.isoformat(),
            "direction": row.direction,
            "kind": row.kind,
            "text": row.text,
            "transcript": row.transcript,
            "choices": row.choices,
            "file_kept": row.media_key is not None,
        }
        for row in rows
    ]
