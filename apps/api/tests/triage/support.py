"""Synthetic d1-ultra answers for unit tests; no network."""

import threading
import time
from collections.abc import Callable

from finboy.core.config import Settings
from finboy.services.triage.provider import ChoiceAnswer, NoulAnswer
from finboy.services.triage.service import Sorted
from pydantic import SecretStr


def choice(option: str, probability: float = 0.97) -> ChoiceAnswer:
    """`option` chosen with `probability`; the rest goes to a runner-up."""
    return ChoiceAnswer(
        type="choice",
        choice=option,
        probabilities={option: probability, "runner_up": round(1 - probability, 6)},
    )


def noul(probability: float) -> NoulAnswer:
    return NoulAnswer(type="noul", noul=probability)


def sorted_answers(**answers: ChoiceAnswer | NoulAnswer) -> Sorted:
    return Sorted(answers)


def triaged(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "triage_enabled": True,
            "liquid_api_key": SecretStr("liquid_synthetic"),
            "liquid_decision_model": "d1-ultra",
        }
    )


def held[T](value: T, release: threading.Event) -> Callable[..., T]:
    """A model call that is still working until the test releases it."""

    def call(*_args: object, **_kwargs: object) -> T:
        assert release.wait(5)
        return value

    return call


def late[T](value: T, seconds: float = 0.05) -> Callable[..., T]:
    """A model call that finishes after d1-ultra has answered."""

    def call(*_args: object, **_kwargs: object) -> T:
        time.sleep(seconds)
        return value

    return call
