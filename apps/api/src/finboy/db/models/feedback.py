"""Problems and ideas households send from the web app (docs/feedback-round/contract.md).

The household wrote the message for the FinBoy team, which reads it in the admin panel. A
screenshot sits in the private R2 bucket under a key built from IDs. Rows go with the item or the
account.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base

KINDS = ("problem", "idea", "other")
STATUSES = ("new", "planned", "done")
SCREENSHOT_TYPES = ("image/jpeg", "image/png", "image/webp")
MAX_MESSAGE = 2000
MAX_PAGE = 200


def _within(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_within(KINDS)})", name="kind"),
        CheckConstraint(f"status IN ({_within(STATUSES)})", name="status"),
        CheckConstraint(
            f"screenshot_type IN ({_within(SCREENSHOT_TYPES)})", name="screenshot_type"
        ),
        CheckConstraint(
            f"length(message) BETWEEN 1 AND {MAX_MESSAGE} AND length(page) <= {MAX_PAGE}",
            name="length",
        ),
        Index("ix_feedback_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    # The app screen it was sent from, like "/transactions"; never a query string.
    page: Mapped[str] = mapped_column(Text, server_default="")
    # `<feedback prefix><household id>/<feedback id>.<ext>`, built from IDs only.
    screenshot_key: Mapped[str | None] = mapped_column(Text)
    screenshot_type: Mapped[str | None] = mapped_column(Text)
    screenshot_bytes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When the owner's email about it went out.
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
