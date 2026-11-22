"""Feedback tests on an in-memory SQLite copy of the schema, with two synthetic households."""

from collections.abc import Iterator

import pytest
from finboy.services.advisor.synthetic import make_store
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    make = make_store()
    yield make
    make.kw["bind"].dispose()


@pytest.fixture
def session(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory() as value:
        yield value
