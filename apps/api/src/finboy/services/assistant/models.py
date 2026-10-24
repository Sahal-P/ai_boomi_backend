"""Frozen assistant HTTP and service contracts; Agent 3 implements behavior."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from finboy.core.languages import DisplayStyle, Language
from finboy.services.money.engine import CashFlowSimulation, TransactionView


class AssistantFact(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: str
    label: str = ""
    amount_minor: int | None = None
    count: int | None = None
    currency: Literal["INR"] | None = None


class ResolvedPeriod(BaseModel):
    start: date
    end: date
    label: str


class AssistantAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    data_version: str = "0"
    dataset: Literal["household"] = "household"
    resolved_period: ResolvedPeriod | None = None
    display_language: Literal["en", "hi", "ml"] = "en"
    display_script: Literal["Latn", "Deva", "Mlym"] = "Latn"
    evidence_total: int = 0
    evidence_sampled: bool = False
    warning_labels: dict[str, str] = Field(default_factory=dict)
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
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    include_overdue_line: bool = Field(default=False, strict=True)
    text: str = Field(min_length=1, max_length=2000)
    display_style: DisplayStyle = "auto"


class SpeakRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=600)
    language: Language
