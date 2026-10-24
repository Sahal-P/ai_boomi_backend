"""Read-only pre/post-migration provenance inventory. Prints aggregate counts only."""

import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.db.session import build_engine


def inventory(connection: Connection, user_id: UUID) -> dict[str, int]:
    transactions = connection.execute(
        text("""
        WITH provenance AS (
          SELECT e.transaction_id,bool_or(s.source='demo_mailbox') demo,
                 bool_or(s.source<>'demo_mailbox') household
          FROM source_events e JOIN email_sources s ON s.id=e.email_source_id
          WHERE e.user_id=:uid GROUP BY e.transaction_id
        ) SELECT count(*) FILTER(WHERE demo AND NOT household) demo_only,
                 count(*) FILTER(WHERE demo AND household) mixed
          FROM provenance WHERE transaction_id IS NOT NULL
    """),
        {"uid": user_id},
    ).one()
    obligations = connection.execute(
        text("""
        WITH provenance AS (
          SELECT c.id,bool_or(s.source='demo_mailbox') demo,
                 bool_or(s.source<>'demo_mailbox') household
          FROM commitments c JOIN source_events e ON e.user_id=c.user_id
            AND e.event_type IN ('bill_due','emi_due') AND e.amount_minor=c.amount_minor
            AND e.due_date=c.due_date
            AND coalesce(e.merchant_normalized,'Unidentified obligation')=c.label
          JOIN email_sources s ON s.id=e.email_source_id
          WHERE c.user_id=:uid GROUP BY c.id
        ) SELECT count(*) FILTER(WHERE demo AND NOT household) demo_only,
                 count(*) FILTER(WHERE demo AND household) mixed FROM provenance
    """),
        {"uid": user_id},
    ).one()
    return {
        "demo_only_transactions": transactions.demo_only,
        "mixed_transactions": transactions.mixed,
        "demo_only_obligations": obligations.demo_only,
        "mixed_obligations": obligations.mixed,
    }


def main() -> None:
    engine = build_engine(Settings())
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            print(json.dumps(inventory(connection, LOCAL_USER_ID)))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
