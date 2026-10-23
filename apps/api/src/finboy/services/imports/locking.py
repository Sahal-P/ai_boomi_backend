from collections.abc import Iterator
from contextlib import contextmanager

from finboy.services.mail.security import MailError
from sqlalchemy import Engine, text

# Session-level locks use a dedicated connection across pipeline-owned transactions.
# Privacy deletion and imports share this lock so deletion cannot race an extractor commit.
IMPORT_LOCK = 0x46494E424F59


@contextmanager
def import_lock(engine: Engine) -> Iterator[None]:
    with engine.connect() as connection:
        acquired = connection.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": IMPORT_LOCK}
        )
        if not acquired:
            raise MailError("import_busy")
        try:
            yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": IMPORT_LOCK})
