"""Changes FinBoy's advisor proposed and the household applied (docs/advisor-edits-round).

A change set is what one answer offered: categories, own-account transfers, payee names, budgets
or the savings goal. Nothing changes until the household taps Apply. Applying stores each touched
field's value before and after, so one Undo can put back everything that hasn't changed since.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base


class RecordChangeSet(Base):
    __tablename__ = "record_change_sets"
    __table_args__ = (
        CheckConstraint(
            "state IN ('proposed','applied','undone','declined','expired')", name="state"
        ),
        CheckConstraint("channel IN ('web','whatsapp')", name="channel"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # The advisor answer that offered it, so a reloaded chat shows its state.
    message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("advisor_messages.id", ondelete="SET NULL"), index=True
    )
    channel: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, server_default="proposed")
    # The validated changes, as `services/advisor/changes.Change` dumps them.
    changes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    # What the household is shown: the proposal, then what applying actually changed.
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # What applying touched: {"records": {id: {field: value}}, "payees": {...}, ...}.
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
