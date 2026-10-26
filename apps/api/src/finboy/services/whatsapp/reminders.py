"""Opted-in due reminders for pilot households: daytime only, at most once per due and kind.

`finboy.services.pilot.cli remind` runs this from a systemd timer. With an approved Hindi
utility template (WHATSAPP_REMINDER_TEMPLATE) FinBoy may message first, only to households that
opted in and have not sent STOP. Without a template, a due coming up follows the household's
next reply inside WhatsApp's 24-hour window instead (`fallback_due`).
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from finboy.core.config import Settings
from finboy.db.models.core import User
from finboy.db.models.ledger import Commitment
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppReminder
from finboy.services.assistant.language import money
from finboy.services.whatsapp import hindi, prompts
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.meta import MetaClient, MetaUnavailable, SendUnknown

IST = ZoneInfo("Asia/Kolkata")
DAYTIME = (time(8), time(20))
AHEAD = timedelta(days=2)
OVERDUE = timedelta(days=7)  # the fallback also covers dues the household has not met yet


@dataclass(frozen=True)
class Due:
    binding: WhatsAppBinding
    commitment: Commitment
    kind: str  # "two_days" until the due date, then "due_day"


def due_now(
    session: Session,
    today: date,
    *,
    binding_id: UUID | None = None,
    overdue: timedelta = timedelta(0),
) -> list[Due]:
    """Upcoming dues within two days for opted-in, consented, enabled pilot households."""
    query = (
        select(WhatsAppBinding, Commitment)
        .join(User, User.id == WhatsAppBinding.user_id)
        .join(Commitment, Commitment.user_id == WhatsAppBinding.user_id)
        .where(
            User.pilot.is_(True),
            WhatsAppBinding.enabled.is_(True),
            WhatsAppBinding.consented_at.is_not(None),
            WhatsAppBinding.reminders_opt_in_at.is_not(None),
            Commitment.dataset == "household",
            Commitment.status == "upcoming",
            Commitment.due_date.between(today - overdue, today + AHEAD),
        )
        .order_by(Commitment.due_date, Commitment.id)
    )
    if binding_id is not None:
        query = query.where(WhatsAppBinding.id == binding_id)
    dues = []
    for binding, commitment in session.execute(query).all():
        kind = "due_day" if commitment.due_date <= today else "two_days"
        already = session.scalar(
            select(WhatsAppReminder.id).where(
                WhatsAppReminder.commitment_id == commitment.id, WhatsAppReminder.kind == kind
            )
        )
        if already is None:
            dues.append(Due(binding, commitment, kind))
    return dues


def claim(session: Session, due: Due, state: str) -> WhatsAppReminder | None:
    """The unique (due, kind) row is written before any send, so a crash never repeats it."""
    reminder = WhatsAppReminder(
        id=uuid4(),
        binding_id=due.binding.id,
        commitment_id=due.commitment.id,
        kind=due.kind,
        state=state,
    )
    try:
        with session.begin_nested():
            session.add(reminder)
            session.flush()
    except IntegrityError:
        return None
    return reminder


def recipient(config: ChannelConfig, binding: WhatsAppBinding) -> str | None:
    """The approved number behind a binding; numbers live only in the private allowlist."""
    return next(
        (
            sender
            for sender, user in config.allowlist.items()
            if user == binding.user_id and config.digest("sender", sender) == binding.sender_hash
        ),
        None,
    )


def fallback_due(
    session: Session, settings: Settings, binding: WhatsAppBinding, today: date
) -> Due | None:
    """Without a template, the nearest unreminded due rides along with the next reply."""
    if settings.whatsapp_reminder_template:
        return None
    dues = due_now(session, today, binding_id=binding.id, overdue=OVERDUE)
    return dues[0] if dues else None


def _still_allowed(session: Session, binding_id: UUID) -> bool:
    """Lock consent through the send, like replies: a STOP that commits first blocks it."""
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
        and binding.reminders_opt_in_at is not None
    )


def send_reminders(
    factory: sessionmaker[Session],
    settings: Settings,
    config: ChannelConfig,
    client: MetaClient,
    now: datetime,
) -> dict[str, int]:
    """Template reminders, 08:00–20:00 IST. Returns counts only."""
    counts = {"sent": 0, "failed": 0, "unknown": 0, "skipped": 0}
    local = now.astimezone(IST)
    template = settings.whatsapp_reminder_template
    if not template or not DAYTIME[0] <= local.time() < DAYTIME[1]:
        return counts
    with factory() as session:
        for due in due_now(session, local.date()):
            to = recipient(config, due.binding)
            reminder = claim(session, due, "sending") if to else None
            if to is None or reminder is None:
                counts["skipped"] += 1
                session.rollback()
                continue
            prompt = prompts.open_prompt(
                session,
                due.binding,
                "due_paid",
                commitment_id=due.commitment.id,
                fingerprint=prompts.due_fingerprint(config, due.commitment),
            )
            parameters = [
                due.commitment.label,
                money(due.commitment.amount_minor),
                hindi.date_label(due.commitment.due_date),
            ]
            buttons = [prompts.button(prompt, "paid"), prompts.button(prompt, "later")]
            session.commit()
            if not _still_allowed(session, due.binding.id):
                reminder.state = "failed"
            else:
                try:
                    reminder.outbound_message_id = client.send_template(
                        to,
                        name=template,
                        language="hi",
                        parameters=parameters,
                        quick_replies=buttons,
                    )
                    reminder.state = "sent"
                except SendUnknown:
                    reminder.state = "unknown"
                except MetaUnavailable:
                    reminder.state = "failed"
            reminder.updated_at = datetime.now(UTC)
            session.commit()
            counts[reminder.state] += 1
    return counts
