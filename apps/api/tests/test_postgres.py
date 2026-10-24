from collections.abc import Iterator
from uuid import uuid4

import pytest
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.db.base import Base
from finboy.db.models import ImportRun, MailConnection, User
from finboy.db.session import build_engine
from finboy.main import create_app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Connection, insert, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


def local_settings() -> Settings:
    settings = Settings()
    if settings.environment == "production" or make_url(
        settings.database_url.get_secret_value()
    ).host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Integration tests require a local disposable database")
    return settings


@pytest.fixture
def connection() -> Iterator[Connection]:
    engine = build_engine(local_settings())
    try:
        with engine.connect() as connection, connection.begin() as transaction:
            yield connection
            transaction.rollback()
    finally:
        engine.dispose()


def test_postgres_phase1_schema_and_seed(connection: Connection) -> None:
    assert connection.scalar(text("SELECT 1")) == 1
    assert (
        connection.scalar(text("SELECT version_num FROM alembic_version"))
        == "0005_scan_continuation"
    )
    assert set(inspect(connection).get_table_names()) == {"alembic_version", *Base.metadata.tables}
    assert connection.scalar(select(User.display_name).where(User.id == LOCAL_USER_ID)) == "Arun"


def test_import_defaults_and_constraints(connection: Connection) -> None:
    run_id = uuid4()
    connection.execute(
        insert(ImportRun).values(
            id=run_id,
            user_id=LOCAL_USER_ID,
            mode="demo_mailbox",
            status="queued",
        )
    )
    row = connection.execute(select(ImportRun.__table__).where(ImportRun.id == run_id)).one()
    assert row.headers_checked == row.failed == row.transactions_created == 0
    for values in (
        {"mode": "unsupported"},
        {"status": "unknown"},
        {"failed": -1},
        {"error_code": "private-free-text"},
        {"user_id": uuid4()},
    ):
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                insert(ImportRun).values(
                    {
                        "id": uuid4(),
                        "user_id": LOCAL_USER_ID,
                        "mode": "demo_mailbox",
                        "status": "queued",
                        **values,
                    }
                )
            )


def test_provider_check_and_oauth_state_unique(connection: Connection) -> None:
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            insert(MailConnection).values(
                id=uuid4(),
                user_id=LOCAL_USER_ID,
                provider="unsupported",
                account_email_masked="a***@example.invalid",
                account_email_sha256="synthetic-hash",
                scopes=[],
                status="active",
            )
        )
    # No credentials or imported data survive these rolled-back integration transactions.
    states = Base.metadata.tables["oauth_states"]
    connection.execute(
        insert(states).values(
            id=uuid4(),
            user_id=LOCAL_USER_ID,
            state_sha256="synthetic-state-hash",
            encrypted_code_verifier=b"synthetic-encrypted-bytes",
            expires_at=text("now()"),
        )
    )
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            insert(states).values(
                id=uuid4(),
                user_id=LOCAL_USER_ID,
                state_sha256="synthetic-state-hash",
                encrypted_code_verifier=b"synthetic-encrypted-bytes",
                expires_at=text("now()"),
            )
        )


async def test_health_with_real_postgres() -> None:
    app = create_app(local_settings())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_transactions_enforce_money_and_review_contract(connection: Connection) -> None:
    transactions = Base.metadata.tables["transactions"]
    values = {
        "id": uuid4(),
        "user_id": LOCAL_USER_ID,
        "direction": "out",
        "kind": "purchase",
        "amount_minor": 12500,
        "currency": "INR",
        "merchant": "Synthetic merchant",
        "category": "other",
        "occurred_at": text("now()"),
        "confidence": "0.950",
        "confidence_factors": {},
        "status": "confirmed",
        "fingerprint": "synthetic-fingerprint",
    }
    connection.execute(insert(transactions).values(values))
    locked = connection.scalar(
        select(transactions.c.user_locked_fields).where(
            transactions.c.id == values["id"],
        )
    )
    assert locked == []
    for invalid in (
        {"amount_minor": 0},
        {"currency": "USD"},
        {"category": "unknown"},
        {"status": "unknown"},
        {"confidence": "1.001"},
        {"review_reason": "private-free-text"},
        {"linked_transaction_id": uuid4()},
    ):
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(insert(transactions).values({**values, "id": uuid4(), **invalid}))
