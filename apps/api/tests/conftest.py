from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from finboy.core.config import Settings
from finboy.db.session import get_session
from finboy.main import create_app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        cors_origins=["http://localhost:3000"],
        environment="test",
    )


@pytest.fixture
def session() -> MagicMock:
    return MagicMock(spec=Session)


@pytest.fixture
def app(settings: Settings, session: MagicMock) -> FastAPI:
    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: session
    return app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client
