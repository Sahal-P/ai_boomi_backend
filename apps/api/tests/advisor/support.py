"""Advisor test helpers: the synthetic household, a scripted model and a quick `ask`."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.services.advisor import embeddings, service
from finboy.services.advisor.synthetic import OTHER_USER, SyntheticHousehold, make_store, payment
from sqlalchemy.orm import Session

FixtureToolbox = SyntheticHousehold
make_factory = make_store
__all__ = ["OTHER_USER", "FixtureToolbox", "make_factory", "payment"]


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        cors_origins=["http://localhost:3000"],
        environment="test",
        openai_api_key="sk-synthetic-test-key",
        openai_assistant_model="synthetic-model",
        advisor_enabled=True,
    )


def embedding_settings() -> Settings:
    """Settings with embeddings and the guides on (a synthetic model; no network in tests)."""
    return make_settings().model_copy(
        update={
            "openai_embedding_model": "synthetic-embedding",
            "advisor_embedding_dimensions": 64,
            "knowledge_enabled": True,
        }
    )


class ConceptEmbedder:
    """Stands in for `embeddings.embed`: a text points along the axes of the concept words it
    contains, so a match by meaning without shared words is easy to set up. Records each call."""

    def __init__(self, concepts: dict[str, int], dimensions: int = 64) -> None:
        self.concepts, self.dimensions = concepts, dimensions
        self.calls: list[list[str]] = []

    def __call__(self, texts: list[str], _settings: Settings) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self.vector(text) for text in texts]

    def vector(self, text: str) -> list[float]:
        values = [0.0] * self.dimensions
        for word, axis in self.concepts.items():
            if word in text.casefold():
                values[axis] = 1.0
        if not any(values):
            values[-1] = 1.0
        return embeddings.normalise(values)


class Item(SimpleNamespace):
    def model_dump(self, **_: Any) -> dict[str, Any]:
        return {key: value for key, value in vars(self).items() if key != "parsed_arguments"}


def call(name: str, arguments: dict[str, Any], call_id: str = "call_1") -> Item:
    return Item(type="function_call", name=name, arguments=json.dumps(arguments), call_id=call_id)


def reply(
    text: str,
    *,
    speech: str | None = None,
    policy: str = "answer",
    follow_ups: list[str] | None = None,
    memory_updates: list[dict[str, Any]] | None = None,
    sources: list[str] | None = None,
) -> service.AdvisorReply:
    return service.AdvisorReply.model_validate(
        {
            "policy": policy,
            "display_text": text,
            "speech_text": text if speech is None else speech,
            "follow_ups": follow_ups or [],
            "memory_updates": memory_updates or [],
            "sources": sources or [],
        }
    )


class ScriptedModel:
    """Stands in for the OpenAI client: each `responses.parse` call returns the next step."""

    def __init__(self, *steps: list[Item] | service.AdvisorReply | Exception) -> None:
        self.steps = list(steps)
        self.calls: list[dict[str, Any]] = []
        self.responses = SimpleNamespace(parse=self.parse)

    def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs | {"input": list(kwargs["input"])})
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        if isinstance(step, list):
            return SimpleNamespace(output=step, output_parsed=None)
        message = Item(type="message")
        return SimpleNamespace(output=[message], output_parsed=step)


def ask(session: Session, settings: Settings, toolbox: FixtureToolbox, text: str, **kwargs):
    values: dict[str, Any] = {
        "user_id": LOCAL_USER_ID,
        "display_style": "en",
        "channel": "web",
    } | kwargs
    return service.advise(session, text=text, settings=settings, toolbox=toolbox, **values)


def now() -> datetime:
    return datetime.now(UTC)
