"""Frozen assistant HTTP and service contracts; Agent 3 implements behavior."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from finboy.core.languages import DisplayStyle, Language
from finboy.services.money.engine import CashFlowSimulation, TransactionView


class AssistantFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    amount_minor: int | None = None
    count: int | None = None
    currency: Literal["INR"] | None = None


class AssistantAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: str
    policy: Literal["answer", "decline", "clarify"]
    display_text: str
    speech_text: str
    speech_language: Language
    facts: list[AssistantFact]
    simulation: CashFlowSimulation | None
    evidence_transactions: list[TransactionView]
    warnings: list[str]


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)
    display_style: DisplayStyle = "auto"


class SpeakRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=600)
    language: Language
