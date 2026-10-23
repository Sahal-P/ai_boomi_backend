"""Explicit synthetic UI fixtures for A2's disposable database; never creates a Google grant."""

import json
from pathlib import Path
from tempfile import gettempdir
from uuid import UUID

from finboy.core.clock import now_ist
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.db.models.mail import ImportRun, MailConnection
from finboy.db.session import build_engine
from finboy.services.mail.security import sha256
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

QA_CONNECTION_ID = UUID("00000000-0000-4000-8000-00000000a201")
QA_RUN_ID = UUID("00000000-0000-4000-8000-00000000a202")


def main() -> None:
    settings = Settings()
    url = make_url(settings.database_url.get_secret_value())
    if (
        settings.environment == "production"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database != "finboy_a2"
    ):
        raise SystemExit("UI fixtures require the local finboy_a2 database")
    directory = Path(gettempdir()) / "finboy-a2-synthetic-eml"
    directory.mkdir(exist_ok=True)
    for number in range(3):
        (directory / f"synthetic-{number}.eml").write_bytes(
            (
                f"From: Synthetic Bank <alerts@example.test>\r\nTo: demo@example.test\r\n"
                f"Date: Wed, 28 Oct 2026 10:00:00 +0530\r\nSubject: Synthetic payment {number}\r\n"
                f"Message-ID: <a2-qa-{number}@example.test>\r\nX-FinBoy-Synthetic: 1\r\n"
                "Content-Type: text/plain; charset=utf-8\r\n\r\n"
                "A synthetic payment of INR 10 was debited.\r\n"
            ).encode()
        )
    engine = build_engine(settings)
    try:
        with Session(engine) as session, session.begin():
            if session.get(MailConnection, QA_CONNECTION_ID) is None:
                session.add(
                    MailConnection(
                        id=QA_CONNECTION_ID,
                        user_id=LOCAL_USER_ID,
                        provider="gmail",
                        account_email_masked="q***@***.test",
                        account_email_sha256=sha256("synthetic.qa@example.test"),
                        scopes=[],
                        status="active",
                        connected_at=now_ist(),
                        last_synced_at=now_ist(),
                    )
                )
            if session.get(ImportRun, QA_RUN_ID) is None:
                session.add(
                    ImportRun(
                        id=QA_RUN_ID,
                        user_id=LOCAL_USER_ID,
                        mode="eml_upload",
                        status="completed",
                        headers_checked=3,
                        candidates_found=3,
                        emails_processed=3,
                        transactions_created=2,
                        duplicates_merged=1,
                        needs_review=1,
                        events_extracted=3,
                        started_at=now_ist(),
                        finished_at=now_ist(),
                    )
                )
        print(
            json.dumps(
                {"synthetic_eml_directory": str(directory), "synthetic_progress_id": str(QA_RUN_ID)}
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
