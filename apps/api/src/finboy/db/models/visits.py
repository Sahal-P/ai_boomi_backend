"""Where a sign-up came from (docs/ad-journey-round/contract.md).

One row per visit to a page with FinBoy's WhatsApp button, with the times along the way: the page
opened, the button tapped, and the first message of the new household it led to. The page's own
random ref travels in the prefilled WhatsApp greeting. No IP address, cookie, device ID, raw
User-Agent or click ID is kept.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base

REF_PATTERN = "^[2-9A-HJ-NP-Z]{6}$"
TAG_PATTERN = "^[a-z0-9._-]{1,64}$"
LANDING_PATTERN = "^/[a-z0-9/-]{0,63}$"
TAGS = ("source", "medium", "campaign", "content")  # the utm_* tags kept


class SignupVisit(Base):
    __tablename__ = "signup_visits"
    # Migration 0023 also checks `ref`, the tags and `landing` against these patterns with
    # PostgreSQL's regex operator, which the SQLite unit-test schema lacks; the code checks them
    # before every write.
    __table_args__ = (
        CheckConstraint("language IN ('en','hi','ml')", name="language"),
        CheckConstraint("browser IN ('instagram','facebook','other')", name="browser"),
        CheckConstraint("platform IN ('android','ios','desktop','other')", name="platform"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # Random, made by the page; it says nothing about the person.
    ref: Mapped[str] = mapped_column(Text, unique=True)
    # The link's utm_* tags, cleaned; "meta"/"click" for a Meta click without tags.
    source: Mapped[str | None] = mapped_column(Text)
    medium: Mapped[str | None] = mapped_column(Text)
    campaign: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    landing: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    # Coarse classes read from the User-Agent, which is never stored.
    browser: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    tapped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The household it led to; unlinked when that household is erased or never agreed.
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
