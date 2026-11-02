from collections.abc import Iterator

import pytest
from finboy.core.config import Settings
from sqlalchemy.orm import sessionmaker

from .database import open_world
from .support import billing_settings


@pytest.fixture
def billing() -> Settings:
    return billing_settings()


@pytest.fixture
def world() -> Iterator[tuple[Settings, sessionmaker]]:
    """Settings and a session factory on the disposable database; integration tests only."""
    yield from open_world()
