"""Development data comes exclusively from the existing rendered synthetic mailbox."""

import json
import os

from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.db.models.mail import ImportRun
from finboy.db.session import build_engine
from finboy.services.imports.files import demo_messages
from finboy.services.imports.runner import create_run, run_import


def main() -> None:
    settings = Settings()
    engine = build_engine(settings)
    if (
        settings.environment == "production"
        or engine.url.host not in {"127.0.0.1", "localhost"}
        or engine.url.database != "finboy_p1"
    ):
        engine.dispose()
        raise SystemExit("Use the isolated local finboy_p1 development database.")
    # This command cannot accidentally call a paid provider or retain live mailbox data.
    os.environ["FINBOY_EXTRACTION_MODE"] = "rules"
    try:
        with Session(engine) as session:
            run = create_run(session, mode="demo_mailbox")
            run_id = run.id
        run_import(engine, settings, run_id, demo_messages())
        with Session(engine) as session:
            completed = session.get(ImportRun, run_id)
            assert completed is not None
            print(
                json.dumps(
                    {
                        "status": completed.status,
                        "emails_processed": completed.emails_processed,
                        "transactions_created": completed.transactions_created,
                        "failed": completed.failed,
                    }
                )
            )
            if completed.status != "completed" or completed.failed:
                raise SystemExit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
