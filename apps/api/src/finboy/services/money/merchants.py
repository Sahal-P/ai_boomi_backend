"""Merchant memory: what a household chose for a payee (money-manager contract).

The category is learned when the household changes a record's category (WhatsApp or the website)
and applied when the same payee's next entry is saved. Since the advisor edits round a payee can
also keep the name the household gave it, so its next entries arrive under that name; a renamed
payee takes the new name's own category first, then the one remembered for the old name. Names are
compared case-folded; unknown or masked payees are never remembered.
"""

import unicodedata
from dataclasses import dataclass
from typing import get_args
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from finboy.db.models.money import MerchantCategory
from finboy.services.ingestion.types import Category


def merchant_key(name: str | None) -> str | None:
    clean = " ".join(unicodedata.normalize("NFC", name or "").casefold().split())
    if not clean or clean.startswith("unknown") or "[" in clean or len(clean) > 80:
        return None
    return clean


@dataclass(frozen=True)
class Memory:
    """A household's remembered payees, for code that saves many entries at once."""

    categories: dict[str, str]
    names: dict[str, str]

    def name(self, merchant: str | None) -> str | None:
        """The name the household gave this payee, or None."""
        key = merchant_key(merchant)
        return self.names.get(key) if key is not None else None

    def category(self, merchant: str | None) -> Category | None:
        key = merchant_key(merchant)
        if key is None:
            return None
        renamed = merchant_key(self.names.get(key))
        found = (self.categories.get(renamed) if renamed else None) or self.categories.get(key)
        return found if found in get_args(Category) else None  # type: ignore[return-value]


def memory(session: Session, user_id: UUID) -> Memory:
    rows = session.execute(
        select(
            MerchantCategory.merchant_key, MerchantCategory.category, MerchantCategory.display_name
        ).where(MerchantCategory.user_id == user_id)
    ).all()
    return Memory(
        categories={key: category for key, category, _ in rows if category is not None},
        names={key: name for key, _, name in rows if name},
    )


def _for(session: Session, user_id: UUID, merchant: str | None) -> Memory:
    """Only the rows one payee needs: its own and, when renamed, its new name's."""
    key = merchant_key(merchant)
    if key is None:
        return Memory({}, {})
    own = session.execute(
        select(MerchantCategory.category, MerchantCategory.display_name).where(
            MerchantCategory.user_id == user_id, MerchantCategory.merchant_key == key
        )
    ).first()
    categories = {key: own.category} if own and own.category else {}
    names = {key: own.display_name} if own and own.display_name else {}
    renamed = merchant_key(names.get(key))
    if renamed and renamed != key:
        other = session.scalar(
            select(MerchantCategory.category).where(
                MerchantCategory.user_id == user_id, MerchantCategory.merchant_key == renamed
            )
        )
        if other:
            categories[renamed] = other
    return Memory(categories, names)


def remembered(session: Session, user_id: UUID, merchant: str | None) -> Category | None:
    return _for(session, user_id, merchant).category(merchant)


def remembered_name(session: Session, user_id: UUID, merchant: str | None) -> str | None:
    return _for(session, user_id, merchant).name(merchant)


def learn(session: Session, user_id: UUID, merchant: str | None, category: Category) -> None:
    """Remember (or replace) a payee's category, keeping any remembered name; the caller
    commits."""
    key = merchant_key(merchant)
    if key is None or category not in get_args(Category):
        return
    session.execute(
        insert(MerchantCategory)
        .values(user_id=user_id, merchant_key=key, category=category)
        .on_conflict_do_update(
            index_elements=[MerchantCategory.user_id, MerchantCategory.merchant_key],
            set_={"category": category, "updated_at": func.now()},
        )
    )
