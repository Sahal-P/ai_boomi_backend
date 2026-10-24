"""Exercise the scope backfill on a pre-upgrade synthetic schema, then roll back."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from finboy.core.config import Settings
from finboy.db.session import build_engine
from sqlalchemy import text

pytestmark = pytest.mark.integration


def test_additive_upgrade_preserves_values_revisions_and_mixed_provenance():
    settings = Settings()
    engine = build_engine(settings)
    assert settings.environment != "production" and engine.url.host in {"127.0.0.1", "localhost"}
    assert engine.url.database in {"finboy_ux_api", "finboy_ux_ui"}
    migrations = Path(__file__).parents[2] / "alembic" / "versions"

    def load(name):
        spec = importlib.util.spec_from_file_location("synthetic_migration", migrations / name)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    schema = "ux_migration_" + uuid4().hex
    try:
        with engine.connect() as connection, connection.begin() as transaction:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            with Operations.context(MigrationContext.configure(connection)):
                load("0002_phase1_phase_1_schema_and_local_user.py").upgrade()
                load("0003_whatsapp.py").upgrade()
                uid = "00000000-0000-0000-0000-000000000001"
                run_demo, run_live = str(uuid4()), str(uuid4())
                for key, mode in [(run_demo, "demo_mailbox"), (run_live, "gmail")]:
                    connection.execute(
                        text(
                            "INSERT INTO import_runs(id,user_id,mode,status) "
                            "VALUES (:id,:uid,:mode,'completed')"
                        ),
                        {"id": key, "uid": uid, "mode": mode},
                    )
                txids = [str(uuid4()) for _ in range(3)]
                for index, key in enumerate(txids):
                    connection.execute(
                        text("""INSERT INTO transactions(id,user_id,direction,kind,amount_minor,
                        currency,merchant,category,occurred_at,confidence,confidence_factors,
                        status,fingerprint)
                      VALUES(:id,:uid,'out','purchase',:amount,'INR','Synthetic merchant',
                        'shopping','2026-10-24T09:00:00+05:30',.9,'{}','confirmed',:fingerprint)"""),
                        {
                            "id": key,
                            "uid": uid,
                            "amount": 10000 + index,
                            "fingerprint": uuid4().hex,
                        },
                    )
                for txid, modes in zip(
                    txids, [["demo_mailbox"], ["gmail"], ["demo_mailbox", "gmail"]], strict=True
                ):
                    for mode in modes:
                        sid, eid = str(uuid4()), str(uuid4())
                        connection.execute(
                            text("""INSERT INTO email_sources(id,user_id,import_run_id,source,
                            provider_message_id,content_sha256,sender_domain,subject_sha256,
                            received_at,classification,processing_status)
                          VALUES(:id,:uid,:run,:source,:provider,:hash,'example.test',:hash,
                            '2026-10-24T09:00:00+05:30','bank_alert','extracted')"""),
                            {
                                "id": sid,
                                "uid": uid,
                                "run": run_demo if mode == "demo_mailbox" else run_live,
                                "source": mode,
                                "provider": uuid4().hex,
                                "hash": "a" * 64,
                            },
                        )
                        connection.execute(
                            text("""INSERT INTO source_events(id,user_id,email_source_id,
                            transaction_id,
                            event_type,amount_minor,currency,extraction_method,extractor_id,
                            evidence,field_confidence)
                          VALUES(:id,:uid,:source,:tx,'debit',10000,'INR','rule','synthetic','{}','{}')"""),
                            {"id": eid, "uid": uid, "source": sid, "tx": txid},
                        )
                revision_id = str(uuid4())
                connection.execute(
                    text("""INSERT INTO transaction_revisions(id,transaction_id,field,old_value,
                        new_value,changed_by,reason)
                  VALUES(:id,:tx,'category','"other"','"shopping"','user','user_correction')"""),
                    {"id": revision_id, "tx": txids[2]},
                )
                values_before = connection.execute(
                    text("SELECT id,amount_minor,merchant,status FROM transactions ORDER BY id")
                ).all()
                sources_before = connection.scalar(text("SELECT count(*) FROM source_events"))
                load("0004_ux_trust.py").upgrade()
                load("0005_scan_continuation.py").upgrade()
                assert (
                    connection.execute(
                        text("SELECT id,amount_minor,merchant,status FROM transactions ORDER BY id")
                    ).all()
                    == values_before
                )
                assert (
                    connection.scalar(text("SELECT count(*) FROM source_events")) == sources_before
                )
                assert connection.scalar(text("SELECT count(*) FROM transaction_revisions")) == 1
                labels = {
                    str(row.id): row.dataset
                    for row in connection.execute(text("SELECT id,dataset FROM transactions"))
                }
                assert [labels[key] for key in txids] == ["demo", "household", "quarantined"]
                connection.execute(
                    text(
                        "UPDATE transactions SET merchant='Corrected synthetic merchant' "
                        "WHERE id=:id"
                    ),
                    {"id": txids[1]},
                )
                assert (
                    connection.scalar(
                        text("SELECT data_version FROM users WHERE id=:id"), {"id": uid}
                    )
                    == 1
                )
            transaction.rollback()
    finally:
        engine.dispose()
