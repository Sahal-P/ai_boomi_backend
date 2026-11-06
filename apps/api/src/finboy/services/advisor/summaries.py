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
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.services.advisor import history, prompt
from finboy.services.advisor.client import client_for

logger = logging.getLogger(__name__)
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="advisor-summary")
MAX_TRANSCRIPT = 12_000


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
                row = history.find(session, user_id, thread.id)
                row.summary = " ".join(found.summary.split())[:600]
                row.title = " ".join(found.title.split())[: history.TITLE] or row.title
                row.summarized_at = datetime.now(UTC)
                session.commit()
        logger.info("advisor.summarized", extra={"outcome": "done"})
    except Exception:
        logger.warning("advisor.summarized", extra={"outcome": "failed"})
