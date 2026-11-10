"""Short summaries of finished chats, written in the background (docs/advisor-round/contract.md).

When a household starts a new chat, earlier chats that have gone quiet get a two- or three-line
summary and a title, so later chats can draw on them without resending every message. Failures
are logged without content and retried with the next chat.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.db.models.advisor import AdvisorThread
from finboy.services.advisor import embeddings, history, prompt
from finboy.services.advisor.client import client_for

logger = logging.getLogger(__name__)
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="advisor-summary")
MAX_TRANSCRIPT = 12_000
BACKFILL = 20  # summaries without an embedding, embedded per run


class ChatSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    title: str


def schedule(bind: object, settings: Settings, user_id: UUID, current_id: UUID | None) -> None:
    """Summarise this household's quiet chats in the background; never blocks a reply."""
    if not isinstance(bind, Engine):
        return
    _POOL.submit(_summarize, bind, settings, user_id, current_id)


def _summarize(bind: Engine, settings: Settings, user_id: UUID, current_id: UUID | None) -> None:
    try:
        with Session(bind) as session:
            for thread in history.quiet_unsummarized(session, user_id, current_id):
                lines = [
                    f"{'Household' if row.role == 'user' else 'FinBoy'}: {row.text}"
                    for row in history.messages(session, user_id, thread.id)
                ]
                if len(lines) < 2:
                    continue
                transcript = "\n".join(lines)[-MAX_TRANSCRIPT:]
                session.rollback()
                response = client_for(settings).responses.parse(
                    model=settings.advisor_model,
                    input=[
                        {"role": "system", "content": prompt.SUMMARY},
                        {"role": "user", "content": transcript},
                    ],
                    text_format=ChatSummary,
                    reasoning={"effort": "low"},
                    store=False,
                    max_output_tokens=800,
                    timeout=settings.advisor_timeout_seconds,
                )
                found = response.output_parsed
                if not isinstance(found, ChatSummary) or not found.summary.strip():
                    continue
                summary = " ".join(found.summary.split())[:600]
                title = " ".join(found.title.split())[: history.TITLE]
                row = history.find(session, user_id, thread.id)
                row.summary = summary
                row.title = title or row.title
                row.summarized_at = datetime.now(UTC)
                row.summary_embedding, row.embedding_model = None, None  # for the new summary
                session.commit()
            _embed_summaries(session, settings, user_id)
        logger.info("advisor.summarized", extra={"outcome": "done"})
    except Exception:
        logger.warning("advisor.summarized", extra={"outcome": "failed"})


def _embed_summaries(session: Session, settings: Settings, user_id: UUID) -> None:
    """Embeddings for this household's summaries that have none for the current model, so
    past-chat search can match them by meaning."""
    if not embeddings.available(settings):
        return
    model = settings.openai_embedding_model
    pending = [
        (row.id, f"{row.title or ''}. {row.summary}")
        for row in session.scalars(
            select(AdvisorThread)
            .where(AdvisorThread.user_id == user_id, AdvisorThread.summary.is_not(None))
            .order_by(AdvisorThread.last_at.desc())
            .limit(200)
        )
        if row.embedding_model != model
        or row.summary_embedding is None
        or len(row.summary_embedding) != settings.advisor_embedding_dimensions
    ][:BACKFILL]
    session.rollback()  # no transaction stays open over the network call
    if not pending:
        return
    found = embeddings.embed([text for _, text in pending], settings)
    if found is None:
        return
    for (thread_id, _), vector in zip(pending, found, strict=True):
        row = session.get(AdvisorThread, thread_id)
        if row is not None and row.user_id == user_id:
            row.summary_embedding, row.embedding_model = vector, model
    session.commit()
