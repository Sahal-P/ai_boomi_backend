"""Liquid AI's decision API. Mockable; no request/response bodies, secrets or errors are logged.

A decision model answers named yes/no ("noul") and choice questions about a text or picture with
probabilities, in one pass, and writes no text (https://docs.liquid.ai/lfm/models/d1).
"""

import base64
from typing import Annotated, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.services.speech.providers import bounded_request

# Only the decision model that passed the live check and the offline gate.
MODELS = {"d1-ultra"}
MAX_RESPONSE_BYTES = 64 * 1024
Probability = Annotated[float, Field(ge=0, le=1)]


class Noul(BaseModel):
    """A yes/no question; the answer is the probability of yes."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["noul"] = "noul"
    instructions: str


class Choice(BaseModel):
    """One option from `criteria`, which maps each option to what it means."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["choice"] = "choice"
    instructions: str
    criteria: dict[str, str]


Question = Noul | Choice


class NoulAnswer(BaseModel):
    type: Literal["noul"]
    noul: Probability


class ChoiceAnswer(BaseModel):
    type: Literal["choice"]
    choice: str
    probabilities: dict[str, Probability]


Answer = NoulAnswer | ChoiceAnswer


class Decision(BaseModel):
    answers: dict[str, Annotated[Answer, Field(discriminator="type")]]


def decision_client(settings: Settings) -> httpx.Client:
    # A late decision is skipped, never retried: the slower model call is already running.
    return httpx.Client(timeout=settings.triage_timeout_seconds, follow_redirects=False)


def decide(
    state: str,
    questions: dict[str, Question],
    settings: Settings,
    *,
    images: tuple[bytes, ...] = (),
) -> dict[str, Answer]:
    """Every question answered with its own type and an offered option, or ProviderUnavailable."""
    key, model = settings.liquid_api_key, settings.liquid_decision_model
    if key is None or model not in MODELS:
        raise ProviderUnavailable("configuration_missing")
    body: dict[str, object] = {
        "model": model,
        "state": state,
        "questions": {name: question.model_dump() for name, question in questions.items()},
    }
    if images:
        # JPEG previews only; the API takes no remote image URLs.
        body["images"] = [
            {"content_type": "image/jpeg", "base64": base64.b64encode(image).decode("ascii")}
            for image in images
        ]
    try:
        with decision_client(settings) as client:
            raw = bounded_request(
                client,
                "POST",
                str(settings.liquid_base_url).rstrip("/") + "/decisions/v1/systemone",
                limit=MAX_RESPONSE_BYTES,
                headers={"Authorization": "Bearer " + key.get_secret_value()},
                json=body,
            )
        answers = Decision.model_validate_json(raw).answers
    except httpx.HTTPError, ProviderUnavailable, ValidationError:
        raise ProviderUnavailable() from None
    for name, question in questions.items():
        answer = answers.get(name)
        if answer is None or answer.type != question.type:
            raise ProviderUnavailable()
        if isinstance(answer, ChoiceAnswer) and (
            not isinstance(question, Choice)
            or answer.choice not in question.criteria
            or not answer.probabilities.keys() <= question.criteria.keys()
        ):
            raise ProviderUnavailable()
    return {name: answers[name] for name in questions}
