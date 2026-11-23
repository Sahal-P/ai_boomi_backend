"""Frozen assistant HTTP and service contracts; Agent 3 implements behavior."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

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


class MemoryChange(BaseModel):
    """A memory the advisor saved, updated or forgot while answering (docs/advisor-round)."""

    model_config = ConfigDict(extra="forbid")
    action: Literal["saved", "updated", "forgotten"]
    text: str
    id: UUID | None = None


class AnswerSource(BaseModel):
    """A reviewed FinBoy guide (docs/advisor-round/contract.md) or a web page
    (docs/names-search-round/contract.md) an advisor answer is based on."""

    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    url: str | None = None  # a guide's first official source, or the page
    kind: Literal["guide", "web"] = "guide"


class ChangeGroup(BaseModel):
    """One line of an advisor proposal (docs/advisor-edits-round/contract.md), computed by code:
    payments moving to a category, own-account transfers, a payee renamed, a budget or the goal."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["category", "own_transfer", "rename", "budget", "savings_goal"]
    # category: the new category; budget: what the budget is for (a category or "total").
    category: str | None = None
    names: list[str] = Field(default_factory=list)  # the payees, at most three
    more_names: int = 0
    new_name: str | None = None  # rename
    payments: int = 0
    amount_minor: int = 0  # the payments' total
    before_minor: int | None = None  # budget, savings_goal: per month now (None: none set)
    after_minor: int | None = None  # budget, savings_goal: per month after (None: removed)


class ChangeSetView(BaseModel):
    """Changes the advisor proposed, and whether the household applied, undid or dismissed them."""

    model_config = ConfigDict(extra="forbid")
    id: UUID
    state: Literal["proposed", "applied", "undone", "declined", "expired"]
    count: int  # payments changed, plus budgets and the goal
    groups: list[ChangeGroup]
    kept: int = 0  # payments the household set itself, left as they are
    remembered: int = 0  # payees whose category or name FinBoy keeps for their next entries
    skipped: int = 0  # changed since: not applied, or not put back by Undo
    expires_at: datetime
    applied_at: datetime | None = None
    undone_at: datetime | None = None
    data_version: str | None = None


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
    # Advisor round (additive): the chat this answer belongs to, memory changes and follow-ups.
    thread_id: UUID | None = None
    memory_changes: list[MemoryChange] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    sources: list[AnswerSource] = Field(default_factory=list)
    # Advisor edits round (additive): changes proposed with this answer, applied only on a tap.
    change_set: ChangeSetView | None = None


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    include_overdue_line: bool = Field(default=False, strict=True)
    text: str = Field(min_length=1, max_length=2000)
    display_style: DisplayStyle = "auto"
    # Continue this chat (advisor round); omitted starts a new one on the web.
    thread_id: UUID | None = None


class SpeakRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=600)
    language: Language
