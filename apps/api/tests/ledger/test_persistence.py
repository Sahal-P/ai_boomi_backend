"""Only isolated synthetic users are created; production DBs are never accepted."""

from dataclasses import asdict
from uuid import uuid4

import pytest
from finboy.core.config import Settings
from finboy.services.ingestion.render_demo_mailbox import MAILBOX
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration


@pytest.fixture
def storage(monkeypatch):
    import json

    from finboy.db.models.core import User
    from finboy.db.models.ledger import (
        Commitment,
        EmailSource,
        SourceEvent,
        Transaction,
        TransactionRevision,
    )
    from finboy.db.models.mail import ImportRun

    settings = Settings()
    engine = create_engine(settings.database_url.get_secret_value(), hide_parameters=True)
    assert engine.url.host in {"localhost", "127.0.0.1"}
    assert settings.environment != "production"
    assert engine.url.database in {
        "finboy",
        "finboy_a1",
        "finboy_test",
        "finboy_p1",
        "finboy_p2",
        "finboy_p3",
        "finboy_p4",
        "finboy_p5",
        "finboy_ux_api",
        "finboy_ux_ui",
        "finboy_capture",
    }, "Use a local test database"
    factory = sessionmaker(engine, expire_on_commit=False)
    user_id, run_id = uuid4(), uuid4()
    monkeypatch.setenv("FINBOY_EXTRACTION_MODE", "rules")
    manifest = json.loads((MAILBOX.parent / "llm_cassettes" / "manifest.json").read_text())
    monkeypatch.setenv("OPENAI_EXTRACTION_MODEL", manifest["model"])
    with factory.begin() as session:
        session.add(User(id=user_id, display_name="Synthetic ingestion test"))
        session.flush()
        session.add(ImportRun(id=run_id, user_id=user_id, mode="eml_upload", status="running"))
    try:
        yield factory, user_id, run_id
    finally:
        with factory.begin() as session:
            for model in (
                Commitment,
                TransactionRevision,
                SourceEvent,
                Transaction,
                EmailSource,
                ImportRun,
                User,
            ):
                if model == TransactionRevision:
                    session.execute(
                        delete(model).where(
                            model.transaction_id.in_(
                                select(Transaction.id).where(Transaction.user_id == user_id)
                            )
                        )
                    )
                else:
                    session.execute(
                        delete(model).where(
                            (model.id if model == User else model.user_id) == user_id
                        )
                    )
        engine.dispose()


def inbound(path, provider_id=None):
    import hashlib

    from finboy.services.ingestion.pipeline import InboundMessage

    raw = path.read_bytes()
    return InboundMessage("eml_upload", provider_id or hashlib.sha256(raw).hexdigest(), raw)


def test_full_mailbox_idempotency_locks_and_links(storage):
    from finboy.db.models.ledger import (
        Commitment,
        EmailSource,
        SourceEvent,
        Transaction,
        TransactionRevision,
    )
    from finboy.services.ingestion.pipeline import ingest_messages

    factory, user_id, run_id = storage
    messages = [inbound(path) for path in sorted(MAILBOX.glob("*.eml"))]
    progress = []
    stats = ingest_messages(
        factory,
        user_id=user_id,
        import_run_id=run_id,
        messages=messages,
        on_progress=progress.append,
    )
    assert asdict(stats) == dict(
        headers_checked=42,
        candidates_found=36,
        emails_processed=42,
        events_extracted=36,
        transactions_created=26,
        duplicates_merged=6,
        needs_review=2,
        non_financial_skipped=6,
        failed=0,
    )
    assert (
        len(progress) == 42
        and progress[0].emails_processed == 1
        and progress[-1].emails_processed == 42
    )
    with factory.begin() as session:
        txs = list(session.scalars(select(Transaction).where(Transaction.user_id == user_id)))
        assert len(txs) == 26
        confirmed = [tx for tx in txs if tx.status == "confirmed"]
        income = sum(tx.amount_minor for tx in confirmed if tx.kind in {"salary", "income_other"})
        outflows = sum(
            tx.amount_minor for tx in confirmed if tx.direction == "out" and tx.kind != "transfer"
        )
        returns = sum(tx.amount_minor for tx in confirmed if tx.kind in {"refund", "reversal"})
        assert income == 6200000 and outflows - returns == 3742000
        assert sum(tx.amount_minor for tx in txs if tx.status == "needs_review") == 234000
        assert sum(tx.linked_transaction_id is not None for tx in txs) == 3
        assert sum(tx.status == "failed" for tx in txs) == 1
        assert (
            len(
                list(
                    session.scalars(
                        select(Commitment).where(
                            Commitment.user_id == user_id, Commitment.status == "paid"
                        )
                    )
                )
            )
            == 1
        )
        amazon = next(tx for tx in txs if tx.amount_minor == 79900)
        assert (
            session.scalar(
                select(func.count())
                .select_from(SourceEvent)
                .where(SourceEvent.transaction_id == amazon.id)
            )
            == 3
        )
        arya = next(tx for tx in txs if tx.merchant == "HOTEL ARYA")
        arya.category = "food_dining"
        arya.user_locked_fields = ["category"]
        session.add(
            TransactionRevision(
                transaction_id=arya.id,
                field="category",
                old_value="travel",
                new_value="food_dining",
                changed_by="user",
                reason="user_correction",
            )
        )
        review = next(tx for tx in txs if tx.amount_minor == 184000)
        review.status = "confirmed"
        session.add(
            TransactionRevision(
                transaction_id=review.id,
                field="status",
                old_value="needs_review",
                new_value="confirmed",
                changed_by="user",
                reason="user_confirmation",
            )
        )
        vpa = next(tx for tx in txs if tx.amount_minor == 50000)
        vpa.status = "rejected"
    again = ingest_messages(factory, user_id=user_id, import_run_id=run_id, messages=messages)
    assert (
        again.transactions_created == 0
        and again.duplicates_merged == 0
        and again.events_extracted == 0
    )
    # New provider IDs exercise reconciliation, rather than just provider-id idempotency.
    changed = ingest_messages(
        factory,
        user_id=user_id,
        import_run_id=run_id,
        messages=[
            inbound(MAILBOX / "07-arya.eml", "new-arya"),
            inbound(MAILBOX / "25-revieworder.eml", "new-review"),
            inbound(MAILBOX / "26-reviewvpa.eml", "new-vpa"),
        ],
    )
    assert changed.duplicates_merged == 3 and changed.failed == 0
    with factory() as session:
        assert session.get(Transaction, arya.id).category == "food_dining"
        assert session.get(Transaction, review.id).status == "confirmed"
        assert session.get(Transaction, vpa.id).status == "rejected"
        assert (
            session.scalar(
                select(func.count()).select_from(EmailSource).where(EmailSource.user_id == user_id)
            )
            == 45
        )


def test_merge_keep_separate_and_tenant_scope(storage):
    from finboy.db.models.ledger import SourceEvent, Transaction, TransactionRevision
    from finboy.services.ingestion.pipeline import ingest_messages
    from finboy.services.ledger.reconcile import keep_separate, merge_transactions

    factory, user_id, run_id = storage
    one = inbound(MAILBOX / "12-amazon799.eml")
    # A conflicting reference amount becomes a review item; explicit merge keeps the chosen amount.
    two = type(one)(
        one.source, "different-notification", one.raw_rfc822.replace(b"799.00", b"899.00")
    )
    stats = ingest_messages(factory, user_id=user_id, import_run_id=run_id, messages=[one, two])
    assert stats.transactions_created == 2 and stats.needs_review == 1
    with factory.begin() as session:
        txs = list(
            session.scalars(
                select(Transaction)
                .where(Transaction.user_id == user_id)
                .order_by(Transaction.amount_minor)
            )
        )
        keep, merge = txs
        assert merge.possible_duplicate_of_id == keep.id
        keep_separate(session, user_id=user_id, transaction_id=merge.id)
        assert "dedupe" in merge.user_locked_fields and merge.possible_duplicate_of_id is None
        with pytest.raises(ValueError, match="transaction_not_found"):
            merge_transactions(session, user_id=uuid4(), keep_id=keep.id, merge_id=merge.id)
        merge_transactions(session, user_id=user_id, keep_id=keep.id, merge_id=merge.id)
        merge_transactions(session, user_id=user_id, keep_id=keep.id, merge_id=merge.id)
        assert merge.status == "merged" and merge.merged_into_id == keep.id
        assert (
            session.scalar(
                select(func.count())
                .select_from(SourceEvent)
                .where(SourceEvent.transaction_id == keep.id)
            )
            == 2
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(TransactionRevision)
                .where(TransactionRevision.transaction_id == merge.id)
            )
            >= 3
        )


def test_failure_is_atomic_and_next_message_commits(storage, monkeypatch, caplog):
    from finboy.db.models.ledger import EmailSource, Transaction
    from finboy.services.ingestion import pipeline

    factory, user_id, run_id = storage
    original = pipeline.persist_event
    calls = 0

    def fail_first(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("private email content must never reach logs")
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline, "persist_event", fail_first)
    stats = pipeline.ingest_messages(
        factory,
        user_id=user_id,
        import_run_id=run_id,
        messages=[inbound(MAILBOX / "01-salary.eml"), inbound(MAILBOX / "02-rent.eml")],
    )
    assert stats.failed == 1 and stats.transactions_created == 1 and stats.events_extracted == 1
    assert "private email content" not in caplog.text
    with factory() as session:
        assert (
            session.scalar(
                select(func.count()).select_from(Transaction).where(Transaction.user_id == user_id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count()).select_from(EmailSource).where(EmailSource.user_id == user_id)
            )
            == 2
        )


def test_structured_cache_reused_without_network(storage, monkeypatch):
    from finboy.db.models.ledger import ExtractionCache
    from finboy.services.ingestion import pipeline
    from finboy.services.ingestion.llm import cache_key
    from finboy.services.ingestion.normalize import normalize

    factory, user_id, run_id = storage
    monkeypatch.setenv("FINBOY_EXTRACTION_MODE", "offline")
    message = inbound(MAILBOX / "01-salary.eml")
    key = "household:" + cache_key(
        normalize(message.raw_rfc822), Settings().openai_extraction_model
    )
    with factory() as session:
        already_existed = (
            session.scalar(select(ExtractionCache.id).where(ExtractionCache.cache_key == key))
            is not None
        )
    try:
        first = pipeline.ingest_messages(
            factory, user_id=user_id, import_run_id=run_id, messages=[message]
        )
        assert first.transactions_created == 1 and first.failed == 0
        with factory() as session:
            cached = session.scalar(select(ExtractionCache).where(ExtractionCache.cache_key == key))
            assert cached is not None and set(cached.result) == {"events", "not_transaction"}

        def unexpected(*args, **kwargs):
            raise AssertionError("cache should avoid extractor calls")

        monkeypatch.setattr(pipeline, "cassette_extract", unexpected)
        monkeypatch.setattr(pipeline, "live_extract", unexpected)
        again = pipeline.ingest_messages(
            factory,
            user_id=user_id,
            import_run_id=run_id,
            messages=[type(message)(message.source, "cache-reimport", message.raw_rfc822)],
        )
        assert again.failed == 0 and again.duplicates_merged == 1
    finally:
        if not already_existed:
            with factory.begin() as session:
                session.execute(delete(ExtractionCache).where(ExtractionCache.cache_key == key))
