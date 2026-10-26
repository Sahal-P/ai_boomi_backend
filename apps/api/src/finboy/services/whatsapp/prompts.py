"""Pending button choices: opaque IDs, a keyed record fingerprint and an expiry. Never text."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from finboy.db.models.ledger import Commitment, Transaction
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppPrompt
from finboy.services.whatsapp.config import ChannelConfig

CHOICES = frozenset(
    {"yes", "no", "change", "undo", "agree", "decline", "paid", "later", "again", "remind", "skip"}
)
LIFETIME = {
    "consent": timedelta(days=7),
    "confirm": timedelta(days=7),
    "change_amount": timedelta(minutes=10),
    "undo": timedelta(days=1),
    "due_paid": timedelta(days=7),
    "due_repeat": timedelta(days=7),
    "reminder_opt_in": timedelta(days=7),
}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def button(prompt: WhatsAppPrompt, choice: str) -> str:
    if choice not in CHOICES:
        raise ValueError("unknown_choice")
    return f"fb1:{prompt.id.hex}:{choice}"


def parse(button_id: str) -> tuple[UUID, str] | None:
    try:
        prefix, key, choice = button_id.split(":")
        if prefix != "fb1" or choice not in CHOICES:
            return None
        return UUID(hex=key), choice
    except ValueError:
        return None


def record_fingerprint(config: ChannelConfig, row: Transaction) -> str:
    """A tap only acts on the record exactly as the household saw it on the card."""
    when = row.occurred_at.isoformat() if row.occurred_at else ""
    parts = (row.id, row.amount_minor, when, row.direction, row.kind, row.category, row.status)
    return config.digest("record", "|".join(map(str, parts)) + "|" + (row.merchant or ""))


def due_fingerprint(config: ChannelConfig, row: Commitment) -> str:
    parts = (row.id, row.amount_minor, row.due_date.isoformat(), row.kind, row.status)
    return config.digest("due", "|".join(map(str, parts)) + "|" + row.label)


def open_prompt(
    session: Session,
    binding: WhatsAppBinding,
    purpose: str,
    *,
    transaction_id: UUID | None = None,
    commitment_id: UUID | None = None,
    decision_id: UUID | None = None,
    fingerprint: str | None = None,
) -> WhatsAppPrompt:
    """Open a choice; an older open card for the same purpose and record stops working."""
    now = datetime.now(UTC)
    stale = update(WhatsAppPrompt).where(
        WhatsAppPrompt.binding_id == binding.id,
        WhatsAppPrompt.purpose == purpose,
        WhatsAppPrompt.state == "open",
    )
    if purpose != "change_amount":
        # Only one amount question is ever pending: the next message answers the newest one.
        stale = stale.where(
            WhatsAppPrompt.transaction_id.is_not_distinct_from(transaction_id),
            WhatsAppPrompt.commitment_id.is_not_distinct_from(commitment_id),
        )
    session.execute(stale.values(state="superseded"))
    prompt = WhatsAppPrompt(
        id=uuid4(),
        binding_id=binding.id,
        user_id=binding.user_id,
        purpose=purpose,
        transaction_id=transaction_id,
        commitment_id=commitment_id,
        decision_id=decision_id,
        fingerprint=fingerprint,
        state="open",
        created_at=now,
        expires_at=now + LIFETIME[purpose],
    )
    session.add(prompt)
    session.flush()
    return prompt


def claim(session: Session, binding: WhatsAppBinding, prompt_id: UUID) -> WhatsAppPrompt | None:
    """The open, unexpired prompt behind a tap, only for the binding that received it."""
    prompt = session.scalar(
        select(WhatsAppPrompt)
        .where(
            WhatsAppPrompt.id == prompt_id,
            WhatsAppPrompt.binding_id == binding.id,
            WhatsAppPrompt.user_id == binding.user_id,
        )
        .with_for_update()
    )
    if prompt is None or prompt.state != "open":
        return None
    if _aware(prompt.expires_at) <= datetime.now(UTC):
        prompt.state = "expired"
        session.commit()
        return None
    return prompt


def pending_change(session: Session, binding: WhatsAppBinding) -> WhatsAppPrompt | None:
    """The newest unexpired "say the right amount" question, if the household is answering it."""
    prompt = session.scalar(
        select(WhatsAppPrompt)
        .where(
            WhatsAppPrompt.binding_id == binding.id,
            WhatsAppPrompt.purpose == "change_amount",
            WhatsAppPrompt.state == "open",
        )
        .order_by(WhatsAppPrompt.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if prompt is None or _aware(prompt.expires_at) <= datetime.now(UTC):
        return None
    return prompt


def answer(prompt: WhatsAppPrompt) -> None:
    prompt.state = "answered"
    prompt.answered_at = datetime.now(UTC)
