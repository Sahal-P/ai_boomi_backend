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
    # The coach's opt-in and stop (docs/advisor-round/contract.md, phase 3).
    | {"coach", "nocoach"}
    # Changes Ask proposed (docs/advisor-edits-round/contract.md); their Undo is "undo".
    | {"apply", "notnow"}
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
    "coach_opt_in": timedelta(days=30),
    # As long as the proposal itself; Undo works for a day, like a saved entry's.
    "advisor_changes": timedelta(days=1),
    "advisor_undo": timedelta(days=1),
}
# Several messages of saved items may be open at once; each keeps its own Undo all / Fix one.
# Every coach nudge's "Stop coaching" keeps working too, so stopping never says "expired".
KEEP_OLDER = {"pick_item", "coach_opt_in"}


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
    change_set_id: UUID | None = None,
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
        change_set_id=change_set_id,
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


# Cards a typed reply can answer (docs/whatsapp.md, "Dates and card replies").
CARDS = frozenset({"confirm", "change_amount", "saved", "undo"})
SAME_MESSAGE = timedelta(seconds=5)
# Other open choices: when one of these is newer, a typed reply is not for an older card.
_CHOICES = frozenset(
    {"due_paid", "due_repeat", "reminder_opt_in", "pick_item", "pick_category"}
    | {"checkin_opt_in", "coach_opt_in", "advisor_changes", "advisor_undo"}
)


def find(session: Session, binding: WhatsAppBinding, prompt_id: UUID) -> WhatsAppPrompt | None:
    """A prompt in any state, only for its own binding: to say why a tap did nothing."""
    return session.scalar(
        select(WhatsAppPrompt).where(
            WhatsAppPrompt.id == prompt_id, WhatsAppPrompt.binding_id == binding.id
        )
    )


def target(
    session: Session, binding: WhatsAppBinding, context_id: str | None, within: timedelta
) -> WhatsAppPrompt | None:
    """The open card a typed reply answers: the one the person swiped to reply to, else the
    newest open card from the last `within`, unless a newer choice of another kind is open."""
    now = datetime.now(UTC)
    usable = select(WhatsAppPrompt).where(
        WhatsAppPrompt.binding_id == binding.id,
        WhatsAppPrompt.state == "open",
        WhatsAppPrompt.expires_at > now,
    )
    if context_id:
        quoted = session.scalars(
            usable.where(
                WhatsAppPrompt.outbound_message_id == context_id,
                WhatsAppPrompt.purpose.in_(CARDS),
                WhatsAppPrompt.group_id.is_(None),
            ).order_by(WhatsAppPrompt.created_at.desc())
        ).all()
        if quoted:
            # A correction opened from that card is newer than the card itself.
            change = pending_change(session, binding)
            records = {(quoted[0].transaction_id, quoted[0].commitment_id)}
            if change is not None and (change.transaction_id, change.commitment_id) in records:
                return change
            return quoted[0]
    card = session.scalar(
        usable.where(
            WhatsAppPrompt.purpose.in_(CARDS),
            WhatsAppPrompt.group_id.is_(None),
            WhatsAppPrompt.created_at >= now - within,
        )
        .order_by(WhatsAppPrompt.created_at.desc())
        .limit(1)
    )
    if card is None:
        return None
    # A choice sent with the same message (a due's Undo with "remind me") doesn't hide the
    # card; one from a later message means the reply may be for that instead.
    later = session.scalar(
        usable.where(
            WhatsAppPrompt.purpose.in_(_CHOICES),
            WhatsAppPrompt.created_at > _aware(card.created_at) + SAME_MESSAGE,
        ).limit(1)
    )
    return None if later is not None else card


def card_for(session: Session, binding: WhatsAppBinding, prompt: WhatsAppPrompt):
    """The open confirm card of the record a correction belongs to, if it is still open."""
    if prompt.purpose == "confirm":
        return prompt
    return session.scalar(
        select(WhatsAppPrompt)
        .where(
            WhatsAppPrompt.binding_id == binding.id,
            WhatsAppPrompt.purpose == "confirm",
            WhatsAppPrompt.state == "open",
            WhatsAppPrompt.expires_at > datetime.now(UTC),
            WhatsAppPrompt.transaction_id.is_not_distinct_from(prompt.transaction_id),
            WhatsAppPrompt.commitment_id.is_not_distinct_from(prompt.commitment_id),
        )
        .order_by(WhatsAppPrompt.created_at.desc())
        .limit(1)
    )


def close_changes(
    session: Session,
    binding: WhatsAppBinding,
    *,
    transaction_id: UUID | None = None,
    commitment_id: UUID | None = None,
) -> None:
    """End an open correction of one record: it was answered on its card instead."""
    session.execute(
        update(WhatsAppPrompt)
        .where(
            WhatsAppPrompt.binding_id == binding.id,
            WhatsAppPrompt.purpose == "change_amount",
            WhatsAppPrompt.state == "open",
            WhatsAppPrompt.transaction_id.is_not_distinct_from(transaction_id),
            WhatsAppPrompt.commitment_id.is_not_distinct_from(commitment_id),
        )
        .values(state="answered", answered_at=datetime.now(UTC))
    )


def stamp(session: Session, binding: WhatsAppBinding, ids: set[UUID], outbound_id: str) -> None:
    """Remember which WhatsApp message carried these cards, so a swipe-reply finds them."""
    if ids:
        session.execute(
            update(WhatsAppPrompt)
            .where(WhatsAppPrompt.binding_id == binding.id, WhatsAppPrompt.id.in_(ids))
            .values(outbound_message_id=outbound_id)
        )
