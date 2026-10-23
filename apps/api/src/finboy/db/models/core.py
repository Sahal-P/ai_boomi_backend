from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    display_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
