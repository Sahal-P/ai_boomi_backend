import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import Engine, text

from finboy.core.config import LOCAL_USER_ID
from finboy.services.mail.security import MailError

# Session-level locks use a dedicated connection across pipeline-owned transactions.
# Privacy deletion and imports share this lock so deletion cannot race an extractor commit.
IMPORT_LOCK = 0x46494E424F59


def lock_key(user_id: UUID) -> int:
    """The owner keeps the original key; each pilot household gets its own (no cross-waiting)."""
    if user_id == LOCAL_USER_ID:
        return IMPORT_LOCK
    digest = hashlib.sha256(b"finboy-import\0" + user_id.bytes).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


@contextmanager
def import_lock(engine: Engine, user_id: UUID = LOCAL_USER_ID) -> Iterator[None]:
    key = lock_key(user_id)
    with engine.connect() as connection:
        acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
        if not acquired:
            raise MailError("import_busy")
        try:
            yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
