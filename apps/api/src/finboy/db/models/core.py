from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("joined_via IN ('whatsapp','google')", name="joined_via"),
        CheckConstraint(
            "monthly_savings_goal_minor > 0 AND monthly_savings_goal_minor <= 1000000000",
            name="savings_goal",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    data_version: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    display_name: Mapped[str] = mapped_column(Text)
    # Village pilot households reach FinBoy only through WhatsApp (docs/pilot/contract.md).
    pilot: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Self-serve households (docs/signup-round/contract.md); NULL for the owner and pilots.
    joined_via: Mapped[str | None] = mapped_column(Text)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Every session carries this number; bumping it signs the household out everywhere.
    session_epoch: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # How much the household wants to keep each month (docs/money-manager-round/contract.md).
    monthly_savings_goal_minor: Mapped[int | None] = mapped_column(BigInteger)
