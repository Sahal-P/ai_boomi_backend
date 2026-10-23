from contextlib import nullcontext

import pytest
from cryptography.fernet import Fernet
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.db.base import Base
from finboy.db.models import User
from finboy.db.session import get_session
from finboy.main import create_app
from sqlalchemy import JSON, MetaData, create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def mail_factory():
    """SQLite is a unit-test double only; PostgreSQL remains the sole runtime store."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if isinstance(column.type, ARRAY | JSONB):
                column.type = column.type.with_variant(JSON(), "sqlite")
        copy = table.to_metadata(metadata)
        for column in copy.columns:
            if column.server_default and "::" in str(column.server_default.arg):
                column.server_default = None
    metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(User(id=LOCAL_USER_ID, display_name="Synthetic user"))
    yield factory
    engine.dispose()


@pytest.fixture
def mail_settings():
    return Settings(
        _env_file=None,
        environment="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        cors_origins=["http://127.0.0.1:3002"],
        web_app_url="http://127.0.0.1:3002",
        google_oauth_client_id="synthetic-client",
        google_oauth_client_secret="SENSITIVE_SECRET",
        google_oauth_redirect_uri="http://127.0.0.1:8002/api/v1/connections/gmail/callback",
        token_encryption_key=Fernet.generate_key().decode(),
    )


@pytest.fixture
def mail_app(mail_factory, mail_settings, monkeypatch):
    app = create_app(mail_settings)
    app.state.engine.dispose()
    app.state.engine = mail_factory.kw["bind"]

    def session_dependency():
        with mail_factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    for module in (
        "finboy.services.imports.runner",
        "finboy.api.v1.connections",
        "finboy.api.v1.privacy",
    ):
        monkeypatch.setattr(f"{module}.import_lock", lambda _engine: nullcontext())
    return app


@pytest.fixture
def eml() -> bytes:
    return (
        b"From: Synthetic Bank <alerts@example.test>\r\n"
        b"To: demo@example.test\r\nDate: Wed, 28 Oct 2026 10:00:00 +0530\r\n"
        b"Subject: Payment notification\r\nMessage-ID: <one@example.test>\r\n"
        b"X-FinBoy-Synthetic: 1\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
        b"A synthetic payment of INR 10 was debited.\r\n"
    )
