import pytest
from finboy.core.config import Settings
from finboy.db.session import build_engine
from finboy.main import create_app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect, text

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


def test_postgres_connection_and_migration_baseline() -> None:
    settings = Settings()
    if settings.environment == "production":
        pytest.fail("Integration tests must not run against a production environment")
    engine = build_engine(settings)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001_phase0"
            )
            assert inspect(connection).get_table_names() == ["alembic_version"]
    finally:
        engine.dispose()


async def test_health_with_real_postgres() -> None:
    settings = Settings()
    if settings.environment == "production":
        pytest.fail("Integration tests must not run against a production environment")
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"
