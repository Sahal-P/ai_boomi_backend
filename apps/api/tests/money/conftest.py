from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from finboy.api.deps import current_user_id
from finboy.core.config import Settings
from finboy.db.models.core import User
from finboy.db.models.ledger import (
    Commitment,
    EmailSource,
    SourceEvent,
    Transaction,
    TransactionRevision,
)
from finboy.db.models.mail import AuditEvent, ImportRun
from finboy.db.session import build_engine, get_session
from finboy.main import create_app
from finboy.services.imports.files import parse_eml
from finboy.services.ingestion.pipeline import InboundMessage, ingest_messages
from finboy.services.ingestion.render_demo_mailbox import render
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker


@dataclass
class MailboxAPI:
    factory: sessionmaker[Session]
    user_id: UUID
    run_id: UUID
    client: TestClient
    messages: list[InboundMessage]


@pytest.fixture
def mailbox_api(monkeypatch, tmp_path) -> Iterator[MailboxAPI]:
    """Every PostgreSQL finance test starts with the real rendered 42-message pipeline."""
    from finboy.services.money import engine as money_engine

    settings = Settings()
    engine = build_engine(settings)
    assert settings.environment != "production"
    assert engine.url.host in {"127.0.0.1", "localhost"}
    assert engine.url.database in {
        "finboy",
        "finboy_test",
        "finboy_p1",
        "finboy_p2",
        "finboy_p3",
        "finboy_p4",
        "finboy_p5",
        "finboy_ux_api",
        "finboy_ux_ui",
        "finboy_capture",
        "finboy_pilot",
        "finboy_signup",
    }, "Use a named local disposable FinBoy database"
    factory = sessionmaker(engine, expire_on_commit=False)
    user_id, run_id = uuid4(), uuid4()
    monkeypatch.setenv("FINBOY_EXTRACTION_MODE", "rules")
    monkeypatch.setattr(money_engine, "today_ist", lambda: date(2026, 10, 28))
    with factory.begin() as session:
        session.add(User(id=user_id, display_name="Synthetic money test"))
        session.flush()
        session.add(ImportRun(id=run_id, user_id=user_id, mode="eml_upload", status="running"))
    app = create_app(settings)

    def session_dependency():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[current_user_id] = lambda: user_id
    try:
        directory = tmp_path / "rendered_mailbox"
        render(date(2026, 10, 28), directory)
        messages = [
            parse_eml(path.read_bytes(), source="eml_upload")
            for path in sorted(directory.glob("*.eml"))
        ]
        assert len(messages) == 42
        stats = ingest_messages(factory, user_id=user_id, import_run_id=run_id, messages=messages)
        assert stats.emails_processed == 42 and stats.transactions_created == 26
        assert stats.events_extracted == 36 and stats.duplicates_merged == 6 and stats.failed == 0
        with TestClient(app) as client:
            yield MailboxAPI(factory, user_id, run_id, client, messages)
    finally:
        with factory.begin() as session:
            for model in (
                AuditEvent,
                Commitment,
                TransactionRevision,
                SourceEvent,
                Transaction,
                EmailSource,
                ImportRun,
                User,
            ):
                if model == TransactionRevision:
                    condition = model.transaction_id.in_(
                        select(Transaction.id).where(Transaction.user_id == user_id)
                    )
                else:
                    condition = (model.id if model == User else model.user_id) == user_id
                session.execute(delete(model).where(condition))
        app.state.engine.dispose()
        engine.dispose()
