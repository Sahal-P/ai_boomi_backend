"""Chats with FinBoy (docs/advisor-round/contract.md).

On the web each "New chat" is a thread; on WhatsApp a thread ends after six quiet hours. The last
turns of the current thread and short summaries of earlier ones go back to the model, so a
follow-up like "and last month?" works and earlier conversations are not lost. Only questions
and answers are kept: never audio, photos or diary messages.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from finboy.db.models.advisor import AdvisorMessage, AdvisorThread

IDLE = timedelta(hours=6)
MAX_TEXT = 4000
TITLE = 80


@dataclass(frozen=True)
class Turn:
    role: str
    text: str


@dataclass(frozen=True)
class Earlier:
    title: str
    summary: str
    last_at: datetime


def find(session: Session, user_id: UUID, thread_id: UUID) -> AdvisorThread:
    """The household's own thread; another household's reads as missing."""
    row = session.get(AdvisorThread, thread_id)
    if row is None or row.user_id != user_id:
        raise LookupError("thread_not_found")
    return row


def current(
    session: Session, user_id: UUID, channel: str, thread_id: UUID | None, now: datetime
) -> AdvisorThread | None:
    """The thread a new question continues, or None when it starts a new one."""
    if thread_id is not None:
        return find(session, user_id, thread_id)
    if channel != "whatsapp":
        return None
    return session.scalar(
        select(AdvisorThread)
        .where(
            AdvisorThread.user_id == user_id,
            AdvisorThread.channel == "whatsapp",
            AdvisorThread.last_at >= now - IDLE,
        )
        .order_by(AdvisorThread.last_at.desc())
        .limit(1)
    )


def recent(session: Session, thread: AdvisorThread | None, turns: int) -> list[Turn]:
    if thread is None or turns <= 0:
        return []
    rows = session.execute(
        select(AdvisorMessage.role, AdvisorMessage.text)
        .where(AdvisorMessage.thread_id == thread.id)
        .order_by(AdvisorMessage.created_at.desc(), AdvisorMessage.id.desc())
        .limit(turns * 2)
    ).all()
    return [Turn(row.role, row.text) for row in reversed(rows)]


def earlier(session: Session, user_id: UUID, exclude: UUID | None, limit: int = 3) -> list[Earlier]:
    conditions = [AdvisorThread.user_id == user_id, AdvisorThread.summary.is_not(None)]
    if exclude is not None:
        conditions.append(AdvisorThread.id != exclude)
    rows = session.scalars(
        select(AdvisorThread).where(*conditions).order_by(AdvisorThread.last_at.desc()).limit(limit)
    )
    return [Earlier(row.title or "", row.summary or "", row.last_at) for row in rows]


def save_turn(
    session: Session,
    *,
    user_id: UUID,
    channel: str,
    thread: AdvisorThread | None,
    question: str,
    answer: str,
    language: str,
    tool_names: list[str],
    now: datetime,
) -> AdvisorThread:
    """The question and its answer, in the thread they belong to (created when new)."""
    if thread is None:
        thread = AdvisorThread(
            user_id=user_id,
            channel=channel,
            title=" ".join(question.split())[:TITLE],
            started_at=now,
            last_at=now,
        )
        session.add(thread)
        session.flush()
    thread.last_at = now
    session.add_all(
        [
            AdvisorMessage(
                thread_id=thread.id,
                user_id=user_id,
                role="user",
                text=question[:MAX_TEXT],
                language=language,
                created_at=now,
            ),
            AdvisorMessage(
                thread_id=thread.id,
                user_id=user_id,
                role="assistant",
                text=(answer or "…")[:MAX_TEXT],
                language=language,
                tool_names=sorted(set(tool_names)),
                created_at=now + timedelta(microseconds=1),
            ),
        ]
    )
    return thread


@dataclass(frozen=True)
class ThreadView:
    id: UUID
    channel: str
    title: str
    started_at: datetime
    last_at: datetime
    messages: int


def threads(session: Session, user_id: UUID, limit: int = 50) -> list[ThreadView]:
    counts = (
        select(AdvisorMessage.thread_id, func.count().label("messages"))
        .where(AdvisorMessage.user_id == user_id)
        .group_by(AdvisorMessage.thread_id)
        .subquery()
    )
    rows = session.execute(
        select(AdvisorThread, counts.c.messages)
        .join(counts, counts.c.thread_id == AdvisorThread.id)
        .where(AdvisorThread.user_id == user_id)
        .order_by(AdvisorThread.last_at.desc())
        .limit(limit)
    ).all()
    return [
        ThreadView(
            row.AdvisorThread.id,
            row.AdvisorThread.channel,
            row.AdvisorThread.title or "",
            row.AdvisorThread.started_at,
            row.AdvisorThread.last_at,
            row.messages,
        )
        for row in rows
    ]


def messages(session: Session, user_id: UUID, thread_id: UUID) -> list[AdvisorMessage]:
    find(session, user_id, thread_id)
    return list(
        session.scalars(
            select(AdvisorMessage)
            .where(AdvisorMessage.thread_id == thread_id)
            .order_by(AdvisorMessage.created_at, AdvisorMessage.id)
        )
    )


def delete_thread(session: Session, user_id: UUID, thread_id: UUID) -> None:
    find(session, user_id, thread_id)
    session.execute(delete(AdvisorThread).where(AdvisorThread.id == thread_id))


def delete_all(session: Session, user_id: UUID) -> int:
    removed = session.execute(delete(AdvisorThread).where(AdvisorThread.user_id == user_id))
    return removed.rowcount or 0


def quiet_unsummarized(
    session: Session, user_id: UUID, current_id: UUID | None, now: datetime | None = None
) -> list[AdvisorThread]:
    """Earlier threads with at least one full turn and no summary yet, newest first."""
    now = now or datetime.now(UTC)
    conditions = [
        AdvisorThread.user_id == user_id,
        AdvisorThread.summary.is_(None),
        AdvisorThread.last_at < now - timedelta(minutes=10),
    ]
    if current_id is not None:
        conditions.append(AdvisorThread.id != current_id)
    return list(
        session.scalars(
            select(AdvisorThread).where(*conditions).order_by(AdvisorThread.last_at.desc()).limit(3)
        )
    )
