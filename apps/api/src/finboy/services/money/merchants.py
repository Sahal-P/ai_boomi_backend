"""Merchant memory: the category a household last chose for a payee (money-manager contract).

Learned when the household changes a record's category (WhatsApp or the website) and applied when
the same payee's next WhatsApp entry is saved. Names are compared case-folded; unknown or masked
payees are never remembered.
"""

import unicodedata
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


def remembered(session: Session, user_id: UUID, merchant: str | None) -> Category | None:
    key = merchant_key(merchant)
    if key is None:
        return None
    category = session.scalar(
        select(MerchantCategory.category).where(
            MerchantCategory.user_id == user_id, MerchantCategory.merchant_key == key
        )
    )
    return category if category in get_args(Category) else None  # type: ignore[return-value]


def learn(session: Session, user_id: UUID, merchant: str | None, category: Category) -> None:
    """Remember (or replace) a payee's category; the caller commits."""
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
