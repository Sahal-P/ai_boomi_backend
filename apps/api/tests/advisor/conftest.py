"""Advisor fixtures over the helpers in support.py."""

from collections.abc import Iterator

import pytest
from finboy.core.config import Settings
from finboy.services.advisor import service, summaries
from sqlalchemy.orm import Session, sessionmaker

from .support import FixtureToolbox, Item, ScriptedModel, make_factory, make_settings


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    make = make_factory()
    yield make
    make.kw["bind"].dispose()


@pytest.fixture
def session(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory() as value:
        yield value


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def toolbox() -> FixtureToolbox:
    return FixtureToolbox()


@pytest.fixture
def scripted(monkeypatch):
    """Install a scripted model for `service.advise`."""

    def install(*steps: list[Item] | service.AdvisorReply | Exception) -> ScriptedModel:
        model = ScriptedModel(*steps)
        monkeypatch.setattr(service, "client_for", lambda _settings: model)
        return model

    return install


@pytest.fixture(autouse=True)
def quiet_summaries(monkeypatch) -> list[tuple]:
    """Background chat summaries never run in unit tests; test_summaries.py calls them directly."""
    scheduled: list[tuple] = []
    monkeypatch.setattr(summaries, "schedule", lambda *args: scheduled.append(args))
    return scheduled
