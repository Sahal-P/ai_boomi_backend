"""The coach on WhatsApp (docs/advisor-round/contract.md, phase 3): opt-in, commands and sends.

`finboy.services.pilot.cli coach` runs `send_nudges` from a systemd timer, hourly 09:00–19:00 IST.
Each opted-in, consented, enabled diary household with no message from FinBoy yet today (a nudge,
a check-in or a due reminder) gets the most important nudge it has not had before. Inside
WhatsApp's 24-hour window that is a message the advisor words with the household's memories, with
a "Stop coaching" button; outside it, the approved WHATSAPP_COACH_TEMPLATE around the
code-written line. Without the template, nothing goes out until the household writes again. The
(number, kind, period) and (number, day) rows are written before the send, so nothing goes out
twice. A sent nudge joins the household's WhatsApp chat; logs carry kinds and counts only.
"""

import logging
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from time import perf_counter
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from openai import OpenAI
from sqlalchemy import exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from finboy.core.config import Settings
from finboy.db.models.advisor import AdvisorNudge
from finboy.db.models.core import User
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppCheckin, WhatsAppReminder
from finboy.services.advisor import coach, history
from finboy.services.advisor.tools import EngineToolbox, Toolbox
from finboy.services.whatsapp import checkin, prompts, reminders
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.meta import MetaClient, MetaUnavailable, SendUnknown

if TYPE_CHECKING:
    from finboy.db.models.whatsapp import WhatsAppPrompt
    from finboy.services.whatsapp.pilot import Conversation

logger = logging.getLogger(__name__)
# WhatsApp's 24-hour window, with room for a slow send: later than this, only the template.
WINDOW = timedelta(hours=23, minutes=30)
END = r"\s*[.!।]*\s*"
ON = re.compile(
    r"\s*(?:coach\s+on|turn\s+on\s+(?:the\s+)?coach(?:ing)?|start\s+coaching"
    r"|कोच\s+चालू(?:\s+करो)?|coach\s+chalu(?:\s+karo)?|കോച്ച്\s+ഓൺ(?:\s+ചെയ്യൂ)?)" + END,
    re.IGNORECASE,
)
OFF = re.compile(
    r"\s*(?:coach\s+off|turn\s+off\s+(?:the\s+)?coach(?:ing)?|stop\s+coaching"
    r"|कोच\s+बंद(?:\s+करो)?|coach\s+band(?:\s+karo)?|കോച്ച്\s+ഓഫ്(?:\s+ചെയ്യൂ)?)" + END,
    re.IGNORECASE,
)
ToolboxFactory = Callable[[Session, UUID], Toolbox]


def _switch(conversation: Conversation, value: bool) -> str | None:
    """The coach is strictly opt-in, and stops the same way (STOP also stops every send)."""
    conversation.binding.coach_opt_in_at = datetime.now(UTC) if value else None
    conversation.session.commit()
    words = conversation.words
    text = words.COACH_ON if value else words.COACH_OFF
    sent = conversation.send(text)
    if sent:
        conversation.speak(text)
    return conversation.done(sent)


def command(text: str) -> Callable[[Conversation], str | None] | None:
    """ "coach on" / "coach off" (Hindi and Malayalam too), when a whole message says it."""
    if ON.fullmatch(text):
        return lambda conversation: _switch(conversation, True)
    if OFF.fullmatch(text):
        return lambda conversation: _switch(conversation, False)
    return None


def choice(conversation: Conversation, prompt: WhatsAppPrompt, picked: str) -> str | None:
    """A tap on "Coach me" (under "this week") or "Stop coaching" (under a nudge)."""
    prompts.answer(prompt)
    return _switch(conversation, picked == "coach")


def offer(conversation: Conversation) -> tuple[str, tuple[str, str]]:
    """Under "this week": the question and "Coach me", or "Stop coaching" once opted in."""
    binding, words = conversation.binding, conversation.words
    prompt = prompts.open_prompt(conversation.session, binding, "coach_opt_in")
    if binding.coach_opt_in_at is not None:
        return "", (prompts.button(prompt, "nocoach"), words.COACH_NO)
    return "\n\n" + words.COACH_ASK, (prompts.button(prompt, "coach"), words.COACH_YES)


def due(session: Session, today: date) -> list[tuple[WhatsAppBinding, bool]]:
    """Opted-in, consented, enabled diary households that heard nothing from FinBoy yet today,
    each with whether it joined by itself."""
    since = datetime.combine(today, time.min, reminders.IST).astimezone(UTC)
    rows = session.execute(
        select(WhatsAppBinding, User.joined_via.is_not(None))
        .join(User, User.id == WhatsAppBinding.user_id)
        .where(
            User.deleted_at.is_(None),
            User.suspended_at.is_(None),
            or_(User.pilot.is_(True), User.joined_via.is_not(None)),
            WhatsAppBinding.enabled.is_(True),
            WhatsAppBinding.consented_at.is_not(None),
            WhatsAppBinding.coach_opt_in_at.is_not(None),
            ~exists().where(
                AdvisorNudge.binding_id == WhatsAppBinding.id, AdvisorNudge.day == today
            ),
            ~exists().where(
                WhatsAppCheckin.binding_id == WhatsAppBinding.id,
                WhatsAppCheckin.created_at >= since,
            ),
            ~exists().where(
                WhatsAppReminder.binding_id == WhatsAppBinding.id,
                WhatsAppReminder.created_at >= since,
            ),
        )
        .order_by(WhatsAppBinding.id)
    ).all()
    return [(binding, bool(self_serve)) for binding, self_serve in rows]


def period_key(config: ChannelConfig, nudge: coach.Nudge) -> str:
    """A keyed digest of the nudge's kind and period, so no payee name sits in the claim."""
    return config.digest("nudge", f"{nudge.kind}:{nudge.key}")


def pick(
    session: Session,
    config: ChannelConfig,
    binding: WhatsAppBinding,
    box: Toolbox,
    today: date,
) -> coach.Nudge | None:
    """The most important nudge this number has not had. A pilot household that chose due
    reminders hears about dues from them (reminders.py), so the coach leaves dues alone."""
    found = coach.detect(box, today)
    if binding.reminders_opt_in_at is not None:
        found = [nudge for nudge in found if nudge.kind != "due_soon"]
    keys = [period_key(config, nudge) for nudge in found]
    if not keys:
        return None
    had = set(
        session.scalars(
            select(AdvisorNudge.period_key).where(
                AdvisorNudge.binding_id == binding.id, AdvisorNudge.period_key.in_(keys)
            )
        )
    )
    return next((nudge for nudge, key in zip(found, keys, strict=True) if key not in had), None)


def claim(
    session: Session,
    config: ChannelConfig,
    binding: WhatsAppBinding,
    nudge: coach.Nudge,
    today: date,
    via: str,
) -> AdvisorNudge | None:
    """The unique rows are written before any send, so a crash or a second run never repeats
    a nudge or sends two in a day."""
    row = AdvisorNudge(
        id=uuid4(),
        binding_id=binding.id,
        user_id=binding.user_id,
        kind=nudge.kind,
        period_key=period_key(config, nudge),
        day=today,
        via=via,
        state="sending",
    )
    try:
        with session.begin_nested():
            session.add(row)
            session.flush()
    except IntegrityError:
        return None
    return row


def _inside(binding: WhatsAppBinding, now: datetime) -> bool:
    """Whether the household wrote to FinBoy recently enough for an ordinary message."""
    last = binding.last_inbound_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return now - last < WINDOW


def _still_allowed(session: Session, binding_id: UUID) -> bool:
    """Lock consent through the send, like replies: a STOP or "coach off" that commits first
    blocks it."""
    binding = session.scalar(
        select(WhatsAppBinding)
        .where(WhatsAppBinding.id == binding_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    return bool(
        binding
        and binding.enabled
        and binding.consented_at is not None
        and binding.coach_opt_in_at is not None
    )


def send_nudges(
    factory: sessionmaker[Session],
    settings: Settings,
    config: ChannelConfig,
    client: MetaClient,
    now: datetime,
    *,
    toolbox: ToolboxFactory | None = None,
    model: OpenAI | None = None,
) -> dict[str, int]:
    """Today's nudges, 08:00–20:00 IST, at most one per number. Returns counts only:
    `quiet` households had nothing worth a message."""
    counts = {"sent": 0, "failed": 0, "unknown": 0, "skipped": 0, "quiet": 0}
    local = now.astimezone(reminders.IST)
    if not settings.coach_active or not (
        reminders.DAYTIME[0] <= local.time() < reminders.DAYTIME[1]
    ):
        return counts
    today, template = local.date(), settings.whatsapp_coach_template

    def engine_box(session: Session, user_id: UUID) -> Toolbox:
        return EngineToolbox(session, user_id, settings=settings)

    make = toolbox or engine_box
    with factory() as session:
        for binding, self_serve in due(session, today):
            inside = _inside(binding, now)
            to = checkin.number(settings, config, binding, self_serve)
            if to is None or not (inside or template):
                counts["skipped"] += 1
                session.rollback()
                continue
            started = perf_counter()
            try:
                nudge = pick(session, config, binding, make(session, binding.user_id), today)
            except Exception:
                # One household's records never stop the others' nudges; no detail is logged.
                session.rollback()
                counts["skipped"] += 1
                logger.error("advisor.nudge", extra={"stage": "detect", "outcome": "error"})
                continue
            session.rollback()  # release the engine's read lock before any network call
            if nudge is None:
                counts["quiet"] += 1
                continue
            row = claim(session, config, binding, nudge, today, "message" if inside else "template")
            if row is None:
                counts["skipped"] += 1
                session.rollback()
                continue
            language = next(
                (item for item in (binding.language, binding.last_language) if item in coach.WORDS),
                "en",
            )
            words = coach.WORDS[language]
            stop = prompts.open_prompt(session, binding, "coach_opt_in") if inside else None
            session.commit()
            plain = coach.line(nudge, language)
            if inside:
                worded = coach.compose(
                    session, settings, binding.user_id, nudge, language, today, client=model
                )
                text, wording = worded.text, worded.by
            else:
                text, wording = words.COACH_TEMPLATE.format(line=plain), "template"
            if not _still_allowed(session, binding.id):
                row.state = "failed"
            else:
                client.allow(to)  # this binding's own number, checked against its hash
                try:
                    if stop is not None:
                        buttons = [(prompts.button(stop, "nocoach"), words.COACH_NO)]
                        row.outbound_message_id = client.send_buttons(
                            to, text=text, buttons=buttons
                        )
                    else:
                        row.outbound_message_id = client.send_template(
                            to,
                            name=template or "",
                            language=language,
                            parameters=[plain],
                            quick_replies=[],
                        )
                    row.state = "sent"
                except SendUnknown:
                    row.state = "unknown"
                except MetaUnavailable:
                    row.state = "failed"
            row.updated_at = datetime.now(UTC)
            if row.state in {"sent", "unknown"}:
                # What the household was sent joins its chat, so a reply continues it.
                history.save_nudge(
                    session,
                    user_id=binding.user_id,
                    text=text,
                    language=language,
                    now=row.updated_at,
                )
            session.commit()
            counts[row.state] += 1
            logger.info(
                "advisor.nudge",
                extra={
                    "stage": nudge.kind,
                    "outcome": row.state,
                    "provider": wording,
                    "latency_ms": round((perf_counter() - started) * 1000),
                },
            )
    return counts
