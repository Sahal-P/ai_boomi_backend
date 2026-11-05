from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from finboy.core.config import Settings
from finboy.main import create_app
from sqlalchemy.orm import sessionmaker

from .database import open_world


@pytest.fixture
def world() -> Iterator[tuple[Settings, sessionmaker]]:
    """Settings and a session factory on the disposable database; integration tests only."""
    yield from open_world()


@pytest.fixture
def api(world: tuple[Settings, sessionmaker]) -> Iterator[FastAPI]:
    app = create_app(world[0])
    yield app
    app.state.engine.dispose()
