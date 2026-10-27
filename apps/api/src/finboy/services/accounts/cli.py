"""Operator tools for self-serve sign-up. Counts only: never numbers, emails or records.

uv run --package finboy-api python -m finboy.services.accounts.cli counts
uv run --package finboy-api python -m finboy.services.accounts.cli tidy
"""

import argparse
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.db.models.accounts import SignupWaitlist
from finboy.db.session import build_engine
from finboy.services.accounts import households


def main() -> None:
    parser = argparse.ArgumentParser(prog="finboy.services.accounts.cli")
    parser.add_argument("command", choices=["counts", "tidy"])
    command = parser.parse_args().command
    settings = Settings()
    engine = build_engine(settings)
    try:
        with Session(engine) as session:
            if command == "tidy":
                removed = households.tidy(session)
                session.commit()
                print(json.dumps({"pending_removed": removed}))
                return
            waitlist = session.scalar(select(func.count()).select_from(SignupWaitlist)) or 0
            print(
                json.dumps(
                    {
                        "agreed": households.agreed_count(session),
                        "pending": households.pending_count(session),
                        "limit": settings.signup_limit,
                        "signup_enabled": settings.signup_enabled,
                        "waitlist": waitlist,
                    }
                )
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
