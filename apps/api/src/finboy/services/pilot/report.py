"""Weekly pilot measures per household, for the operator and the week-9 review.

Counts and yes/no flags only (docs/pilot/contract.md, metrics allowlist): never amounts, names,
labels, phone numbers or message content. Households appear as "Pilot household N" or "owner".
"""

from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.core import User
from finboy.db.models.ledger import Commitment, EmailSource, ReviewDecision, Transaction
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppReceipt, WhatsAppReminder

IST = ZoneInfo("Asia/Kolkata")
MESSAGES = ("audio", "text", "image", "button", "command")
DECISIONS = ("confirm", "correct", "reject")
FAILURES = (
    "invalid_audio",
    "statement_unavailable",
    "amount_unclear",
    "assistant_unavailable",
    "provider_unavailable",
    "capture_unavailable",
    "capture_busy",
    "invalid_image",
    "prompt_expired",
    "record_changed",
)


def _aware(value: datetime | None) -> datetime | None:
    return value if value is None or value.tzinfo else value.replace(tzinfo=UTC)


def _within(value: datetime | None, start: datetime, end: datetime) -> bool:
    value = _aware(value)
    return value is not None and start <= value < end


def _before(value: datetime | None, end: datetime) -> bool:
    value = _aware(value)
    return value is not None and value < end


def weekly(session: Session, *, today: date, weeks: int = 4) -> list[dict[str, object]]:
    """One row per pilot household and IST week (from Monday), oldest week first."""
    first = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    since = datetime.combine(first, time(), IST)
    households = session.execute(
        select(User.id, User.display_name)
        .where(User.pilot.is_(True))
        .order_by(User.created_at, User.id)
    ).all()
    rows = []
    for user_id, name in households:
        bindings = session.scalars(
            select(WhatsAppBinding).where(WhatsAppBinding.user_id == user_id)
        ).all()
        binding_ids = [binding.id for binding in bindings]
        receipts = session.execute(
            select(
                WhatsAppReceipt.kind, WhatsAppReceipt.error_code, WhatsAppReceipt.received_at
            ).where(
                WhatsAppReceipt.binding_id.in_(binding_ids),
                WhatsAppReceipt.received_at >= since,
            )
        ).all()
        sources = session.execute(
            select(EmailSource.source, EmailSource.received_at).where(
                EmailSource.user_id == user_id,
                EmailSource.source.in_(["whatsapp_voice", "whatsapp_image"]),
                EmailSource.received_at >= since,
            )
        ).all()
        decisions = session.execute(
            select(
                ReviewDecision.action, ReviewDecision.created_at, ReviewDecision.undone_at
            ).where(ReviewDecision.user_id == user_id)
        ).all()
        dues = session.execute(
            select(Commitment.created_at, Commitment.due_date, Transaction.occurred_at)
            .outerjoin(Transaction, Transaction.id == Commitment.paid_transaction_id)
            .where(Commitment.user_id == user_id, Commitment.kind == "loan")
        ).all()
        sent_reminders = session.scalars(
            select(WhatsAppReminder.created_at).where(
                WhatsAppReminder.binding_id.in_(binding_ids), WhatsAppReminder.state == "sent"
            )
        ).all()
        for index in range(weeks):
            monday = first + timedelta(days=7 * index)
            start = datetime.combine(monday, time(), IST)
            end = start + timedelta(days=7)
            week = [row for row in receipts if _within(row.received_at, start, end)]
            kinds = Counter(row.kind for row in week)
            failures = Counter(row.error_code for row in week if row.error_code in FAILURES)
            captured = Counter(
                row.source for row in sources if _within(row.received_at, start, end)
            )
            actions = Counter(
                row.action for row in decisions if _within(row.created_at, start, end)
            )
            paid = [row for row in dues if _within(row.occurred_at, start, end)]
            rows.append(
                {
                    "household": "owner" if user_id == LOCAL_USER_ID else name,
                    "week": monday.isoformat(),
                    "active_days": len(
                        {_aware(row.received_at).astimezone(IST).date() for row in week}
                    ),
                    "messages": {kind: kinds[kind] for kind in MESSAGES},
                    "records": {
                        "voice_or_text": captured["whatsapp_voice"],
                        "screenshot": captured["whatsapp_image"],
                    },
                    "decisions": {action: actions[action] for action in DECISIONS}
                    | {"undone": sum(_within(row.undone_at, start, end) for row in decisions)},
                    "dues": {
                        "spoken": sum(_within(row.created_at, start, end) for row in dues),
                        "paid": len(paid),
                        "paid_by_due_date": sum(
                            _aware(row.occurred_at).astimezone(IST).date() <= row.due_date
                            for row in paid
                        ),
                        "reminded": sum(_within(sent, start, end) for sent in sent_reminders),
                    },
                    "failures": dict(sorted(failures.items())),
                    "consented": any(_before(b.consented_at, end) for b in bindings),
                    "reminders_opted_in": any(
                        _before(b.reminders_opt_in_at, end) for b in bindings
                    ),
                    "stopped_now": any(not binding.enabled for binding in bindings),
                }
            )
    return rows
