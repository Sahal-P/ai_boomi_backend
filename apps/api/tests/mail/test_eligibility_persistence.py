"""Exercise real ingestion and persistence against the existing SQLite unit double."""

from dataclasses import asdict, fields
from email.message import EmailMessage
from uuid import UUID

import pytest
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.db.models.ledger import (
    Commitment,
    EmailSource,
    ExtractionCache,
    SourceEvent,
    Transaction,
)
from finboy.db.models.mail import ImportRun
from finboy.services.ingestion import pipeline
from finboy.services.ingestion.llm import ExtractionUnavailable, LLMResult, cache_key
from finboy.services.ingestion.normalize import NormalizedMessage, normalize
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker


def inbound(identifier: str, body: str) -> pipeline.InboundMessage:
    message = EmailMessage()
    message["From"] = "Synthetic notification <notify@alerts.hdfcbank.test>"
    message["Subject"] = "Synthetic notification"
    message["Date"] = "Sat, 24 Oct 2026 10:00:00 +0530"
    message.set_content(body)
    return pipeline.InboundMessage("eml_upload", identifier, message.as_bytes())


def nonfinancial_messages() -> list[pipeline.InboundMessage]:
    return [
        inbound(
            "synthetic-job",
            "Developer vacancy. Salary INR 800000 per year. Benefits include paid time off.",
        ),
        inbound("synthetic-offer", "Get paid INR 500 for every friend you refer. Limited offer."),
        inbound(
            "synthetic-example",
            "Sample bill INR 1200 due 30-10-26. This example explains how billing works.",
        ),
    ]


def new_run(factory: sessionmaker[Session]) -> UUID:
    with factory.begin() as session:
        run = ImportRun(user_id=LOCAL_USER_ID, mode="eml_upload", status="running")
        session.add(run)
        session.flush()
        return run.id


@pytest.fixture
def ingestion_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        openai_extraction_model="synthetic-extractor",
        openai_api_key="synthetic-local-key",
    )
    monkeypatch.setattr(pipeline, "Settings", lambda: settings)
    # SQLite has no advisory locks; all persistence assertions below use real code.
    monkeypatch.setattr(pipeline, "_user_lock", lambda _session, _user_id: None)
    monkeypatch.setenv("FINBOY_EXTRACTION_MODE", "rules")
    return settings


def test_nonfinancial_inputs_persist_as_skipped_without_ledger_rows_and_reimport_is_idempotent(
    mail_factory: sessionmaker[Session], ingestion_settings: Settings
) -> None:
    messages = nonfinancial_messages()
    first_run = new_run(mail_factory)
    first = pipeline.ingest_messages(
        mail_factory, user_id=LOCAL_USER_ID, import_run_id=first_run, messages=messages
    )
    assert first == pipeline.IngestionStats(
        headers_checked=3, emails_processed=3, non_financial_skipped=3
    )

    second = pipeline.ingest_messages(
        mail_factory,
        user_id=LOCAL_USER_ID,
        import_run_id=new_run(mail_factory),
        messages=messages,
    )
    assert second == pipeline.IngestionStats(headers_checked=3, emails_processed=3)

    with mail_factory() as session:
        sources = session.scalars(select(EmailSource)).all()
        assert len(sources) == 3
        assert {source.provider_message_id for source in sources} == {
            message.provider_message_id for message in messages
        }
        assert all(source.processing_status == "skipped" for source in sources)
        assert all(source.import_run_id == first_run for source in sources)
        assert session.scalar(select(func.count()).select_from(SourceEvent)) == 0
        assert session.scalar(select(func.count()).select_from(Transaction)) == 0
        assert session.scalar(select(func.count()).select_from(Commitment)) == 0
        assert session.scalar(select(func.count()).select_from(ExtractionCache)) == 0


def ingest_serially(
    factory: sessionmaker[Session], run_id: UUID, messages: list[pipeline.InboundMessage]
) -> pipeline.IngestionStats:
    # StaticPool is a unit double, not a concurrent PostgreSQL store. Separate calls
    # keep provider/cache writes serial while exercising the complete real pipeline.
    results = [
        pipeline.ingest_messages(
            factory, user_id=LOCAL_USER_ID, import_run_id=run_id, messages=[message]
        )
        for message in messages
    ]
    return pipeline.IngestionStats(
        **{
            field.name: sum(getattr(result, field.name) for result in results)
            for field in fields(results[0])
        }
    )


@pytest.mark.parametrize("mode", ["rules", "live-veto", "cached-veto", "provider-outage"])
def test_real_pipeline_keeps_provider_states_conservative_without_dropping_real_notifications(
    mode: str,
    mail_factory: sessionmaker[Session],
    ingestion_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notifications = [
        inbound(
            "synthetic-invoice",
            "Invoice INR 799; Merchant: Amazon; Order ID: SYN-INVOICE; Date: 10-10-26 12:05;",
        ),
        inbound(
            "synthetic-settlement",
            "Debited INR 799 to Amazon on 10-10-26 12:05; UTR: SYN-DEBIT; XX1234 via card;",
        ),
    ]
    messages = nonfinancial_messages() + notifications
    calls = 0
    veto = LLMResult(events=[], not_transaction=True)

    def provider(_message: NormalizedMessage, _settings: Settings) -> LLMResult:
        nonlocal calls
        calls += 1
        if mode == "provider-outage":
            raise ExtractionUnavailable("extraction_unavailable")
        assert mode == "live-veto", "Rules and cached modes must not call a provider"
        return veto

    monkeypatch.setattr(pipeline, "live_extract", provider)
    if mode != "rules":
        monkeypatch.setenv("FINBOY_EXTRACTION_MODE", "live")
    if mode == "cached-veto":
        with mail_factory.begin() as session:
            for message in notifications:
                session.add(
                    ExtractionCache(
                        cache_key="household:"
                        + cache_key(
                            normalize(message.raw_rfc822),
                            ingestion_settings.openai_extraction_model,
                        ),
                        result=veto.model_dump(mode="json"),
                    )
                )

    stats = ingest_serially(mail_factory, new_run(mail_factory), messages)
    has_veto = mode in {"live-veto", "cached-veto"}
    expected = pipeline.IngestionStats(
        headers_checked=5,
        emails_processed=5,
        candidates_found=1 if has_veto else 2,
        events_extracted=1 if has_veto else 2,
        transactions_created=1 if has_veto else 2,
        needs_review=1,
        non_financial_skipped=4 if has_veto else 3,
    )
    assert asdict(stats) == asdict(expected)
    assert calls == (2 if mode in {"live-veto", "provider-outage"} else 0)

    with mail_factory() as session:
        sources = session.scalars(select(EmailSource)).all()
        assert len(sources) == 5
        assert all(
            source.processing_status == "skipped"
            for source in sources
            if source.provider_message_id.startswith(
                ("synthetic-job", "synthetic-offer", "synthetic-example")
            )
        )
        invoice = next(
            source for source in sources if source.provider_message_id == "synthetic-invoice"
        )
        assert invoice.processing_status == ("skipped" if has_veto else "extracted")
        transactions = session.scalars(select(Transaction)).all()
        assert len(transactions) == (1 if has_veto else 2)
        assert all(transaction.amount_minor == 79900 for transaction in transactions)
        settlement = next(
            transaction for transaction in transactions if transaction.reference_id == "SYN-DEBIT"
        )
        assert settlement.status == ("needs_review" if has_veto else "confirmed")
        if has_veto:
            assert settlement.confidence < 0.9
        assert session.scalar(select(func.count()).select_from(SourceEvent)) == len(transactions)
        assert session.scalar(select(func.count()).select_from(Commitment)) == 0
        assert session.scalar(select(func.count()).select_from(ExtractionCache)) == (
            2 if has_veto else 0
        )


@pytest.mark.parametrize("cached", [False, True])
def test_model_vetoed_bill_is_failed_for_recovery_without_deducting_a_commitment(
    cached: bool,
    mail_factory: sessionmaker[Session],
    ingestion_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = inbound(
        "synthetic-conflicted-bill",
        "Bill amount INR 799 due 30-10-26; Biller: Electricity; "
        "Date: 10-10-26 12:05; Ref: SYN-BILL; XX1234 via card;",
    )
    monkeypatch.setenv("FINBOY_EXTRACTION_MODE", "live")
    veto = LLMResult(events=[], not_transaction=True)
    calls = 0

    def provider(_message: NormalizedMessage, _settings: Settings) -> LLMResult:
        nonlocal calls
        calls += 1
        assert not cached, "A cached veto must not call the provider"
        return veto

    monkeypatch.setattr(pipeline, "live_extract", provider)
    if cached:
        with mail_factory.begin() as session:
            session.add(
                ExtractionCache(
                    cache_key="household:"
                    + cache_key(
                        normalize(message.raw_rfc822), ingestion_settings.openai_extraction_model
                    ),
                    result=veto.model_dump(mode="json"),
                )
            )
    stats = pipeline.ingest_messages(
        mail_factory,
        user_id=LOCAL_USER_ID,
        import_run_id=new_run(mail_factory),
        messages=[message],
    )
    assert stats == pipeline.IngestionStats(
        headers_checked=1, candidates_found=1, emails_processed=1, failed=1
    )
    assert calls == (0 if cached else 1)
    with mail_factory() as session:
        sources = session.scalars(select(EmailSource)).all()
        assert len(sources) == 1
        assert sources[0].processing_status == "failed"
        assert sources[0].provider_message_id == "synthetic-conflicted-bill"
        assert session.scalar(select(func.count()).select_from(SourceEvent)) == 0
        assert session.scalar(select(func.count()).select_from(Transaction)) == 0
        assert session.scalar(select(func.count()).select_from(Commitment)) == 0
