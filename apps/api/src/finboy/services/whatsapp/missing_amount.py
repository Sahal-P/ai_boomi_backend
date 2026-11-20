"""A diary entry that lacks only its amount, held in memory until the household's next message.

FinBoy asks "how many rupees?" and people answer with just the number ("700"), so the entry it
asked about waits for that answer. It lives only in this API process (one worker): it is never
written to the database or a log, it is forgotten after a few minutes or on a restart, and any
other message replaces it (docs/whatsapp.md, "Missing amounts").
"""

from threading import Lock
from time import monotonic
from uuid import UUID

from finboy.services.whatsapp.statement import Statement

LIFETIME_SECONDS = 600  # as long as the "change the amount" prompt
_held: dict[UUID, tuple[float, Statement]] = {}
_lock = Lock()


def hold(binding_id: UUID, statement: Statement) -> None:
    now = monotonic()
    with _lock:
        for key in [key for key, (expires, _) in _held.items() if expires <= now]:
            del _held[key]
        _held[binding_id] = (now + LIFETIME_SECONDS, statement)


def take(binding_id: UUID) -> Statement | None:
    """The waiting entry, once: taking it forgets it."""
    with _lock:
        expires, statement = _held.pop(binding_id, (0.0, None))
    return statement if monotonic() < expires else None
