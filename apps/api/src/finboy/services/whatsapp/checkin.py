"""The opt-in monthly check-in (docs/money-manager-round/contract.md).

`finboy.services.pilot.cli checkin` runs this from a systemd timer. On the 1st of a month (or the
next two days, if the server was down), 08:00–20:00 IST, FinBoy sends one approved utility template
(WHATSAPP_CHECKIN_TEMPLATE) with last month's totals to each household that tapped "Monthly
check-in" and has not sent STOP. A unique row per household number and month is written before the
send, so a check-in is never sent twice. Counts only; no figures are logged.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from finboy.core.config import Settings
from finboy.db.models.core import User
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppCheckin
from finboy.services.assistant.language import money
from finboy.services.mail.security import MailError, decrypt
from finboy.services.money import budgets
from finboy.services.money.engine import PeriodSpec
from finboy.services.whatsapp import english, hindi, malayalam, reminders
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.meta import MetaClient, MetaUnavailable, SendUnknown

SEND_DAYS = 3
WORDS = {"en": english, "hi": hindi, "ml": malayalam}


def due(session: Session, month: date) -> list[tuple[WhatsAppBinding, bool]]:
    """Opted-in, consented, enabled diary households without this month's check-in yet, each
    with whether it joined by itself."""
    rows = session.execute(
        select(WhatsAppBinding, User.joined_via.is_not(None))
        .join(User, User.id == WhatsAppBinding.user_id)
        .where(
            User.deleted_at.is_(None),
            or_(User.pilot.is_(True), User.joined_via.is_not(None)),
            WhatsAppBinding.enabled.is_(True),
            WhatsAppBinding.consented_at.is_not(None),
            WhatsAppBinding.checkin_opt_in_at.is_not(None),
            ~exists().where(
                WhatsAppCheckin.binding_id == WhatsAppBinding.id, WhatsAppCheckin.month == month
            ),
        )
        .order_by(WhatsAppBinding.id)
    ).all()
    return [(binding, bool(self_serve)) for binding, self_serve in rows]


def number(
    settings: Settings, config: ChannelConfig, binding: WhatsAppBinding, self_serve: bool
) -> str | None:
    """The number behind a binding: the private allowlist's, or a self-serve household's own
    encrypted copy, which must still hash to this binding."""
    allowlisted = reminders.recipient(config, binding)
    if allowlisted is not None or not self_serve:
        return allowlisted
    if binding.encrypted_sender is None or settings.token_encryption_key is None:
        return None
    try:
        sender = decrypt(settings.token_encryption_key.get_secret_value(), binding.encrypted_sender)
    except MailError:
        return None
    return sender if config.digest("sender", sender) == binding.sender_hash else None


def claim(session: Session, binding: WhatsAppBinding, month: date) -> WhatsAppCheckin | None:
    """The unique (number, month) row is written before any send, so a crash never repeats it."""
    checkin = WhatsAppCheckin(id=uuid4(), binding_id=binding.id, month=month, state="sending")
    try:
        with session.begin_nested():
            session.add(checkin)
            session.flush()
    except IntegrityError:
        return None
    return checkin


def parameters(session: Session, binding: WhatsAppBinding, month: date, language: str) -> list[str]:
    """{{1}} the month, {{2}} money in, {{3}} money out, {{4}} where most of it went."""
    words = WORDS[language]
    plan = budgets.month_plan(
        session, binding.user_id, PeriodSpec(kind="month", year=month.year, month=month.month)
    )
    top = words.label(plan.top[0][0]) if plan.top else "—"
    return [words.MONTHS[month.month - 1], money(plan.income_minor), money(plan.spent_minor), top]


def _still_allowed(session: Session, binding_id: object) -> bool:
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
        and binding.checkin_opt_in_at is not None
    )


def send_checkins(
    factory: sessionmaker[Session],
    settings: Settings,
    config: ChannelConfig,
    client: MetaClient,
    now: datetime,
) -> dict[str, int]:
    """Check-ins for last month, from the 1st to the 3rd, 08:00–20:00 IST. Counts only."""
    counts = {"sent": 0, "failed": 0, "unknown": 0, "skipped": 0}
    local = now.astimezone(reminders.IST)
    template = settings.whatsapp_checkin_template
    if (
        not template
        or local.day > SEND_DAYS
        or not reminders.DAYTIME[0] <= local.time() < reminders.DAYTIME[1]
    ):
        return counts
    month = (local.date().replace(day=1) - timedelta(days=1)).replace(day=1)
    with factory() as session:
        for binding, self_serve in due(session, month):
            to = number(settings, config, binding, self_serve)
            checkin = claim(session, binding, month) if to else None
            if to is None or checkin is None:
                counts["skipped"] += 1
                session.rollback()
                continue
            language = next(
                (item for item in (binding.language, binding.last_language) if item in WORDS), "en"
            )
            values = parameters(session, binding, month, language)
            session.commit()
            if not _still_allowed(session, binding.id):
                checkin.state = "failed"
            else:
                client.allow(to)  # this binding's own number, checked against its hash above
                try:
                    checkin.outbound_message_id = client.send_template(
                        to, name=template, language=language, parameters=values, quick_replies=[]
                    )
                    checkin.state = "sent"
                except SendUnknown:
                    checkin.state = "unknown"
                except MetaUnavailable:
                    checkin.state = "failed"
            checkin.updated_at = datetime.now(UTC)
            session.commit()
            counts[checkin.state] += 1
    return counts
