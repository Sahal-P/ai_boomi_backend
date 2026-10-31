from contextlib import nullcontext

import pytest
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.db.base import Base
from finboy.db.models import User
from finboy.db.session import get_session
from finboy.main import create_app
from sqlalchemy import JSON, MetaData, create_engine, event
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def mail_factory():
    """SQLite is a unit-test double only (as in tests/mail); PostgreSQL is the runtime store."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if (
                isinstance(column.type, ARRAY | JSONB)
                and "sqlite" not in column.type._variant_mapping
            ):
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
def mail_app(mail_factory, monkeypatch):
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        cors_origins=["http://127.0.0.1:3002"],
        web_app_url="http://127.0.0.1:3002",
    )
    app = create_app(settings)
    app.state.engine.dispose()
    app.state.engine = mail_factory.kw["bind"]

    def session_dependency():
        with mail_factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    monkeypatch.setattr("finboy.services.imports.runner.import_lock", lambda *_args: nullcontext())
    return app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
