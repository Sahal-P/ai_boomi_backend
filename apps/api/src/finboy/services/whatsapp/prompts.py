"""Pending button choices: opaque IDs, a keyed record fingerprint and an expiry. Never text."""

from datetime import UTC, datetime, timedelta
from typing import get_args
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from finboy.db.models.ledger import Commitment, Transaction
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppPrompt
from finboy.services.ingestion.types import Category
from finboy.services.whatsapp.config import ChannelConfig

CHOICES = frozenset(
    {"yes", "no", "change", "undo", "agree", "decline", "paid", "later", "again", "remind", "skip"}
    # Saved entries (docs/money-manager-round/contract.md); a category list row is its category.
    | {"amount", "category", "putback", "undoall", "fixone", "fix", "checkin", "nocheckin"}
    | set(get_args(Category))
)
LIFETIME = {
    "consent": timedelta(days=7),
    "confirm": timedelta(days=7),
    "change_amount": timedelta(minutes=10),
    "undo": timedelta(days=1),
    "due_paid": timedelta(days=7),
    "due_repeat": timedelta(days=7),
    "reminder_opt_in": timedelta(days=7),
    # Sign-in cards live as long as the login code behind them (docs/signup-round/contract.md).
    "web_login": timedelta(minutes=10),
    "link": timedelta(minutes=10),
    "saved": timedelta(days=2),
    "pick_item": timedelta(days=2),
    "pick_category": timedelta(hours=1),
    "checkin_opt_in": timedelta(days=30),
}
# Several messages of saved items may be open at once; each keeps its own Undo all / Fix one.
KEEP_OLDER = {"pick_item"}


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
    login_request_id: UUID | None = None,
    group_id: UUID | None = None,
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
    if purpose not in KEEP_OLDER:
        session.execute(stale.values(state="superseded"))
    prompt = WhatsAppPrompt(
        id=uuid4(),
        binding_id=binding.id,
        user_id=binding.user_id,
        purpose=purpose,
        transaction_id=transaction_id,
        commitment_id=commitment_id,
        decision_id=decision_id,
        login_request_id=login_request_id,
        group_id=group_id,
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
    return pending(session, binding, "change_amount")


def pending(session: Session, binding: WhatsAppBinding, purpose: str) -> WhatsAppPrompt | None:
    """The newest unexpired open prompt of one purpose: a typed answer may belong to it."""
    prompt = session.scalar(
        select(WhatsAppPrompt)
        .where(
            WhatsAppPrompt.binding_id == binding.id,
            WhatsAppPrompt.purpose == purpose,
            WhatsAppPrompt.state == "open",
        )
        .order_by(WhatsAppPrompt.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if prompt is None or _aware(prompt.expires_at) <= datetime.now(UTC):
        return None
    return prompt


def group(session: Session, binding: WhatsAppBinding, group_id: UUID) -> list[WhatsAppPrompt]:
    """The open per-item prompts of one message of several saved items, oldest first."""
    return list(
        session.scalars(
            select(WhatsAppPrompt)
            .where(
                WhatsAppPrompt.binding_id == binding.id,
                WhatsAppPrompt.group_id == group_id,
                WhatsAppPrompt.state == "open",
                WhatsAppPrompt.expires_at > datetime.now(UTC),
            )
            .order_by(WhatsAppPrompt.created_at, WhatsAppPrompt.id)
            .with_for_update()
        )
    )


def answer(prompt: WhatsAppPrompt) -> None:
    prompt.state = "answered"
    prompt.answered_at = datetime.now(UTC)
