"""Long-term memory, like ChatGPT's saved memories (docs/advisor-round/contract.md).

The advisor saves lasting facts the household shares (family, work and income, goals, plans,
preferences, people and their roles) and every saved memory goes back into its prompt. The
household sees, edits and deletes them on the Memory page or by WhatsApp command, and can turn
memory off. Memories are written in English; account numbers, OTPs and PINs are never kept.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finboy.db.models.advisor import HouseholdMemory
from finboy.db.models.core import User
from finboy.services.assistant.models import MemoryChange
from finboy.services.whatsapp.statement import mask

Kind = Literal["about", "goal", "plan", "preference", "person", "note"]
Source = Literal["web", "whatsapp", "user"]
MAX_TEXT = 300
MAX_UPDATES = 5
# Secrets are never remembered, even when someone asks.
SECRET = re.compile(
    r"\b(?:otp|o\.t\.p|pin|m-?pin|upi\s*pin|cvv|password|passcode|passwd)\b"
    r"|ओटीपी|पिन|पासवर्ड|ഒടിപി|പിൻ|പാസ്‌?വേഡ്",
    re.IGNORECASE,
)
PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)


class MemoryUpdate(BaseModel):
    """One change the model asks for: add a new memory, update or forget a listed one."""

    model_config = ConfigDict(extra="forbid")
    action: Literal["add", "update", "forget"]
    ref: str | None = Field(description='For update/forget: the listed reference, like "m2"')
    kind: Kind | None = Field(description="For add/update")
    text: str | None = Field(description="For add/update: one short fact in English")


class MemoryView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    kind: Kind
    text: str
    source: Source
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Listed:
    """The memories in the prompt, each with the short reference the model uses."""

    block: str
    refs: dict[str, UUID]
    texts: dict[UUID, str]


def text_key(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return " ".join("".join(c if c.isalnum() or c.isspace() else " " for c in folded).split())


def clean(text: str | None) -> str | None:
    """A memory as it may be kept, or None when it is empty, too long or holds a secret."""
    value = " ".join(unicodedata.normalize("NFC", text or "").split())
    if not value or len(value) > MAX_TEXT or SECRET.search(value):
        return None
    value = PAN.sub("[id]", mask(value))
    return value if text_key(value) else None


def enabled(session: Session, user_id: UUID) -> bool:
    return session.scalar(select(User.memory_enabled).where(User.id == user_id)) is not False


def set_enabled(session: Session, user_id: UUID, value: bool) -> None:
    session.execute(update(User).where(User.id == user_id).values(memory_enabled=value))


def listed(session: Session, user_id: UUID) -> list[HouseholdMemory]:
    return list(
        session.scalars(
            select(HouseholdMemory)
            .where(HouseholdMemory.user_id == user_id)
            .order_by(HouseholdMemory.updated_at.desc(), HouseholdMemory.id)
        )
    )


def view(row: HouseholdMemory) -> MemoryView:
    return MemoryView.model_validate(row, from_attributes=True)


def prompt_block(rows: list[HouseholdMemory]) -> Listed:
    refs = {f"m{index}": row.id for index, row in enumerate(rows, start=1)}
    lines = [f"[m{index}] ({row.kind}) {row.text}" for index, row in enumerate(rows, start=1)]
    return Listed(
        "\n".join(lines) or "(nothing saved yet)", refs, {row.id: row.text for row in rows}
    )


def remember(
    session: Session, user_id: UUID, kind: Kind, text: str | None, source: Source, limit: int
) -> MemoryChange | None:
    value = clean(text)
    if value is None:
        return None
    now = datetime.now(UTC)
    key = text_key(value)
    existing = session.scalar(
        select(HouseholdMemory).where(
            HouseholdMemory.user_id == user_id, HouseholdMemory.text_key == key
        )
    )
    if existing is not None:
        # Said again: keep one copy and move it to the top.
        existing.kind, existing.updated_at = kind, now
        return MemoryChange(action="saved", text=existing.text, id=existing.id)
    count = session.scalar(select(func.count()).where(HouseholdMemory.user_id == user_id)) or 0
    if count >= limit:
        # Full: the memory updated longest ago makes room, as an old note would.
        oldest = session.scalar(
            select(HouseholdMemory.id)
            .where(HouseholdMemory.user_id == user_id)
            .order_by(HouseholdMemory.updated_at, HouseholdMemory.id)
            .limit(1)
        )
        session.execute(delete(HouseholdMemory).where(HouseholdMemory.id == oldest))
    row = HouseholdMemory(
        id=uuid4(),
        user_id=user_id,
        kind=kind,
        text=value,
        text_key=key,
        source=source,
        created_at=now,
        updated_at=now,
    )
    try:
        with session.begin_nested():
            session.add(row)
    except IntegrityError:
        return None  # the same fact was saved at the same moment by another reply
    return MemoryChange(action="saved", text=value, id=row.id)


def edit(
    session: Session, user_id: UUID, memory_id: UUID, text: str, kind: Kind | None = None
) -> HouseholdMemory | None:
    row = session.scalar(
        select(HouseholdMemory).where(
            HouseholdMemory.id == memory_id, HouseholdMemory.user_id == user_id
        )
    )
    value = clean(text)
    if row is None:
        return None
    if value is None:
        raise ValueError("invalid_memory")
    key = text_key(value)
    duplicate = session.scalar(
        select(HouseholdMemory.id).where(
            HouseholdMemory.user_id == user_id,
            HouseholdMemory.text_key == key,
            HouseholdMemory.id != memory_id,
        )
    )
    if duplicate is not None:
        session.execute(delete(HouseholdMemory).where(HouseholdMemory.id == duplicate))
    row.text, row.text_key, row.updated_at = value, key, datetime.now(UTC)
    if kind is not None:
        row.kind = kind
    return row


def forget(session: Session, user_id: UUID, memory_id: UUID) -> bool:
    removed = session.execute(
        delete(HouseholdMemory).where(
            HouseholdMemory.id == memory_id, HouseholdMemory.user_id == user_id
        )
    )
    return bool(removed.rowcount)


def forget_all(session: Session, user_id: UUID) -> int:
    removed = session.execute(delete(HouseholdMemory).where(HouseholdMemory.user_id == user_id))
    return removed.rowcount or 0


def apply(
    session: Session,
    user_id: UUID,
    updates: list[MemoryUpdate],
    listing: Listed,
    source: Source,
    limit: int,
) -> list[MemoryChange]:
    """The model's memory changes, checked: references must be listed, secrets are refused."""
    changes: list[MemoryChange] = []
    for update_ in updates[:MAX_UPDATES]:
        target = listing.refs.get(update_.ref or "")
        if update_.action == "add" and update_.kind is not None:
            change = remember(session, user_id, update_.kind, update_.text, source, limit)
            if change is not None:
                changes.append(change)
        elif update_.action == "update" and target is not None and update_.text:
            try:
                row = edit(session, user_id, target, update_.text, update_.kind)
            except ValueError:
                continue
            if row is not None:
                changes.append(MemoryChange(action="updated", text=row.text, id=row.id))
        elif update_.action == "forget" and target is not None:
            if forget(session, user_id, target):
                changes.append(
                    MemoryChange(action="forgotten", text=listing.texts.get(target, ""), id=target)
                )
    return changes
