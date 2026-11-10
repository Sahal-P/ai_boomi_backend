"""The advisor: one money coach for the web and WhatsApp (docs/advisor-round/contract.md).

A question goes to the model with a snapshot of the household's money, its saved memories,
summaries of earlier chats and the last turns of this one. The model may call read-only tools
over the money engine; code runs them for the signed-in household only and releases the engine's
read lock before every network call. Every figure in the reply must come from FinBoy's own
numbers (grounding.py), with one chance to correct it. When the model is unavailable, slow or
still unchecked, the keyword rules and templates answer instead, so a question is never lost.
"""

import json
import logging
import re
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal
from uuid import UUID

from openai import OpenAI
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from finboy.core.clock import today_ist
from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import DisplayStyle, Language
from finboy.services.advisor import grounding, history, memory, prompt, snapshot, summaries, tools
from finboy.services.advisor.client import client_for
from finboy.services.assistant import service as assistant
from finboy.services.assistant.intent import amounts_in_question, rule_intent
from finboy.services.assistant.labels import warning_labels
from finboy.services.assistant.language import normalize_speech, resolve_style
from finboy.services.assistant.models import AnswerSource, AskRequest, AssistantAnswer
from finboy.services.money.engine import TransactionView

logger = logging.getLogger(__name__)
Channel = Literal["web", "whatsapp"]
Progress = Callable[[str], None]  # receives a tool name as the advisor starts using it
MAX_DISPLAY = 3500
MAX_SPEECH = 600
MAX_EVIDENCE = 20
MAX_SOURCES = 3
# Tools that read the household's own records (the others: guides, earlier chats, planning maths).
RECORD_TOOLS = frozenset(
    {
        "money_summary",
        "category_spending",
        "find_payments",
        "payees_and_people",
        "dues",
        "budgets_and_goal",
        "compare",
        "afford_monthly",
    }
)
NATIVE = {"hi": re.compile(r"[ऀ-ॿ]"), "ml": re.compile(r"[ഀ-ൿ]")}
LATIN = re.compile(r"[A-Za-z]")
CORRECTION = (
    "These figures in your reply are not in FinBoy's numbers: {missing}. Answer again using only "
    "figures from the tool results, the snapshot, the memories or the chat, copied exactly. Call "
    "a tool if you need a figure, or leave it out."
)


class AdvisorReply(BaseModel):
    """The model's final answer. Figures in it are checked before anyone sees it."""

    model_config = ConfigDict(extra="forbid")
    policy: Literal["answer", "clarify", "decline"]
    display_text: str
    speech_text: str
    follow_ups: list[str]
    memory_updates: list[memory.MemoryUpdate]
    sources: list[str]


class Unchecked(Exception):
    """The reply still quoted a figure FinBoy does not have, after one correction."""


@dataclass(frozen=True)
class Outcome:
    """The checked reply, the tools the model called and the records they returned."""

    reply: AdvisorReply
    tools: list[str]
    evidence: list[TransactionView]
    repaired: bool


def _style(style: str) -> dict[str, str]:
    return {
        "display_language": "hi"
        if style in {"hi", "hinglish"}
        else "ml"
        if style in {"ml", "manglish"}
        else "en",
        "display_script": "Deva" if style == "hi" else "Mlym" if style == "ml" else "Latn",
    }


def _as_input(item: Any) -> dict[str, Any] | None:
    """A reasoning item or tool call to send back next round (store=False keeps no state)."""
    if item.type == "reasoning":
        return item.model_dump(mode="json", by_alias=True, exclude_none=True)
    if item.type == "function_call":
        return item.model_dump(
            mode="json", by_alias=True, exclude_none=True, exclude={"parsed_arguments"}
        )
    return None


def _speech(text: str, language: Language) -> str:
    """Speech that is safe to synthesise, or "" (the text reply still goes out)."""
    spoken = " ".join(text.split())
    if not spoken:
        return ""
    spoken = normalize_speech(spoken[:MAX_SPEECH], language)
    if language in NATIVE and (LATIN.search(spoken) or not NATIVE[language].search(spoken)):
        return ""  # never speak a Hindi or Malayalam reply in the wrong script
    return spoken if len(spoken) <= MAX_SPEECH else ""


def _report(progress: Progress | None, stage: str) -> None:
    if progress is not None:
        with suppress(Exception):  # a closed stream never stops the answer
            progress(stage)


def _stated(texts: list[str]) -> tuple[set[int], set[Decimal]]:
    """Amounts in paise and every number the person gave, in their words and memories."""
    numbers = {value for text in texts for value, _ in grounding.figures(text)}
    paise = {
        int(value * 100)
        for value in numbers
        if 0 < value <= 10**10 and (value * 100) == (value * 100).to_integral_value()
    }
    for text in texts:
        paise |= amounts_in_question(text)
    return paise, numbers


def _sources(cited: list[str], ctx: tools.Context, style: str) -> list[AnswerSource]:
    """The retrieved guides the reply says it used, titled in the reader's script."""
    language = "hi" if style == "hi" else "ml" if style == "ml" else "en"
    found = [ctx.guides[key] for key in dict.fromkeys(cited) if key in ctx.guides]
    return [
        AnswerSource(
            id=guide.id,
            title=guide.title(language),
            url=guide.sources[0] if guide.sources else None,
        )
        for guide in found[:MAX_SOURCES]
    ]


def _uses_records(
    text: str, used: list[str], cited: list[AnswerSource], ctx: tools.Context, snapshot: set
) -> bool:
    """Whether an answer rests on the household's records, so it carries the records warning:
    it called a record tool, or quotes a figure from their snapshot that no cited guide gives.
    A guide explanation, planning maths or a greeting makes no claim about their records."""
    if RECORD_TOOLS.intersection(used):
        return True
    from_guides = grounding.allowed(ctx.guides[source.id].body for source in cited)
    quoted = {value for value, money_like in grounding.figures(text) if money_like or value >= 100}
    return bool((quoted - from_guides) & snapshot)


def _log(outcome: str, channel: str, started: float, used: list[str], changes: int = 0) -> None:
    logger.info(
        "advisor.answered",
        extra={
            "stage": channel,
            "outcome": outcome,
            "count": len(used),
            "tools": ",".join(sorted(set(used))),
            "memory_changes": changes,
            "latency_ms": round((perf_counter() - started) * 1000),
        },
    )


def converse(
    client: OpenAI,
    settings: Settings,
    items: list[Any],
    box: tools.Toolbox,
    ctx: tools.Context,
    session: Session,
    progress: Progress | None = None,
) -> Outcome:
    """The tool loop: at most `advisor_max_tool_rounds` rounds, then an answer without tools.
    Every tool result's figures join `ctx.known`, the figures the reply may quote."""
    deadline = perf_counter() + settings.advisor_timeout_seconds * 2
    definitions = tools.definitions(settings)
    used: list[str] = []
    evidence: list[TransactionView] = []
    rounds, repaired = 0, False
    while True:
        remaining = deadline - perf_counter()
        if remaining < 1:
            raise TimeoutError
        final = rounds >= settings.advisor_max_tool_rounds
        response = client.responses.parse(
            model=settings.advisor_model,
            input=items,
            tools=definitions,
            tool_choice="none" if final else "auto",
            parallel_tool_calls=True,
            text_format=AdvisorReply,
            reasoning={"effort": settings.advisor_reasoning_effort},
            include=["reasoning.encrypted_content"],
            store=False,
            max_output_tokens=4000,
            prompt_cache_key="finboy-advisor-v1",
            timeout=min(settings.advisor_timeout_seconds, remaining),
        )
        calls = [item for item in response.output if item.type == "function_call"]
        if calls and not final:
            rounds += 1
            items.extend(item for item in map(_as_input, response.output) if item is not None)
            for name in dict.fromkeys(call.name for call in calls):
                _report(progress, name)
            for call in calls:
                result = tools.run(box, call.name, call.arguments, ctx, settings)
                used.append(call.name)
                evidence.extend(result.evidence)
                ctx.known |= grounding.allowed([result.output])
                output = {"type": "function_call_output", "call_id": call.call_id}
                items.append(output | {"output": result.output})
            session.rollback()  # release the engine's read lock before the next network call
            continue
        reply = response.output_parsed
        if not isinstance(reply, AdvisorReply) or not reply.display_text.strip():
            raise ProviderUnavailable("advisor_unavailable")
        missing = grounding.unchecked([reply.display_text, reply.speech_text], ctx.known)
        if not missing:
            return Outcome(reply=reply, tools=used, evidence=evidence, repaired=repaired)
        if repaired:
            raise Unchecked
        repaired = True
        items.append({"role": "assistant", "content": reply.display_text})
        items.append(
            {"role": "developer", "content": CORRECTION.format(missing=", ".join(missing[:8]))}
        )


def advise(
    session: Session,
    *,
    user_id: UUID,
    text: str,
    display_style: DisplayStyle,
    channel: Channel,
    settings: Settings,
    thread_id: UUID | None = None,
    toolbox: tools.Toolbox | None = None,
    progress: Progress | None = None,
) -> AssistantAnswer:
    """Answer one question in its chat. A thread of another household raises LookupError.
    `progress` hears each tool as the advisor starts using it (the web shows what it is doing)."""
    request = AskRequest(text=text, display_style=display_style)
    question = request.text.strip()
    if not question:
        raise ValueError("A question is required")
    started, now, today = perf_counter(), datetime.now(UTC), today_ist()
    style, language = resolve_style(question, request.display_style)
    thread = history.current(session, user_id, channel, thread_id, now)

    def fallback(outcome: str, used: list[str]) -> AssistantAnswer:
        session.rollback()
        answer = assistant.answer_question(
            session,
            user_id=user_id,
            text=question,
            display_style=request.display_style,
            settings=settings,
            rules_only=True,
        )
        kept = history.save_turn(
            session,
            user_id=user_id,
            channel=channel,
            thread=history.current(session, user_id, channel, thread_id, now),
            question=question,
            answer=answer.display_text,
            language=answer.speech_language,
            tool_names=[],
            now=now,
        )
        session.commit()
        _log(outcome, channel, started, used)
        return answer.model_copy(update={"thread_id": kept.id})

    if rule_intent(question).intent == "regulated_advice":
        # The security-pick boundary needs no model: the fixed decline, as before.
        return fallback("declined", [])

    box = toolbox or tools.EngineToolbox(
        session, user_id, settings=settings, thread_id=thread.id if thread else None
    )
    memory_on = memory.enabled(session, user_id)
    remembered = memory.recall(session, user_id, question, settings) if memory_on else []
    listing = memory.prompt_block(remembered)
    snap, version, waiting = snapshot.build(box, today)
    turns = history.recent(session, thread, settings.advisor_history_turns)
    earlier = history.earlier(session, user_id, thread.id if thread else None)
    session.rollback()  # release the engine's read lock before any network call

    said, stated = _stated(
        [question, *(t.text for t in turns if t.role == "user"), *listing.texts.values()]
    )
    snapshot_figures = grounding.allowed([json.dumps(snap, ensure_ascii=False)])
    known = grounding.allowed(
        [
            json.dumps(snap, ensure_ascii=False),
            question,
            today.isoformat(),
            *listing.texts.values(),
            *(turn.text for turn in turns),
            *(item.summary for item in earlier),
        ]
    )
    ctx = tools.Context(today=today, said=said, stated=stated, known=known)
    items: list[Any] = [
        {"role": "system", "content": prompt.SYSTEM},
        {
            "role": "developer",
            "content": prompt.context(
                today=today,
                style=style,
                language=language,
                memory_on=memory_on,
                memories=listing.block,
                snapshot=snap,
                earlier=earlier,
            ),
        },
        *({"role": turn.role, "content": turn.text} for turn in turns),
        {"role": "user", "content": question},
    ]
    try:
        result = converse(client_for(settings), settings, items, box, ctx, session, progress)
    except Exception:
        # Unavailable, slow, malformed or still unchecked: the rules and templates answer.
        return fallback("fallback", [])

    reply = result.reply
    display = reply.display_text.strip()[:MAX_DISPLAY]
    changes = (
        memory.apply(
            session,
            user_id,
            reply.memory_updates,
            listing,
            "whatsapp" if channel == "whatsapp" else "web",
            settings.advisor_memory_limit,
        )
        if memory_on
        else []
    )
    kept = history.save_turn(
        session,
        user_id=user_id,
        channel=channel,
        thread=history.current(session, user_id, channel, thread_id, now),
        question=question,
        answer=display,
        language=language,
        tool_names=result.tools,
        now=now,
    )
    session.commit()
    summaries.schedule(session.get_bind(), settings, user_id, kept.id)
    sources = _sources(reply.sources, ctx, style)
    warnings: list[str] = []
    if _uses_records(display, result.tools, sources, ctx, snapshot_figures):
        warnings = ["incomplete_coverage"] + (["pending_review_items"] if waiting else [])
    evidence = list({row.id: row for row in result.evidence}.values())
    outcome = "repaired" if result.repaired else "answered"
    _log(outcome, channel, started, result.tools, len(changes))
    return AssistantAnswer(
        data_version=version,
        intent="advisor",
        policy=reply.policy,
        display_text=display,
        speech_text=_speech(reply.speech_text, language),
        speech_language=language,
        facts=[],
        simulation=None,
        evidence_transactions=evidence[:MAX_EVIDENCE],
        evidence_total=len(evidence),
        evidence_sampled=len(evidence) > MAX_EVIDENCE,
        warnings=warnings,
        warning_labels=warning_labels(warnings, style),
        thread_id=kept.id,
        memory_changes=changes,
        follow_ups=[item.strip()[:120] for item in reply.follow_ups if item.strip()][:3],
        sources=sources,
        **_style(style),
    )
