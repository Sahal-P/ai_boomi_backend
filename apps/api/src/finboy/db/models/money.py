"""Household money settings: monthly budgets and the categories it chose for payees.

docs/money-manager-round/contract.md. Both are set by the household itself; neither stores message
text. Erasure removes them with the household's records (services/accounts/households.py).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base

# The spending categories of the closed list (services/ingestion/types.py) plus "total" for all
# spending. Income categories have no budget.
BUDGET_CATEGORIES = (
    "'total','rent','food_dining','groceries','transport','shopping','utilities',"
    "'subscriptions','travel','health','education','investments','loan_emi','fees','farming',"
    "'livestock','phone_recharge','family_events','remittance','other'"
)
CATEGORIES = (
    "'salary','other_income','rent','food_dining','groceries','transport','shopping','utilities',"
    "'subscriptions','travel','health','education','investments','loan_emi','fees','transfer',"
    "'farming','livestock','phone_recharge','family_events','remittance','wages','farm_sales',"
    "'govt_benefit','other'"
)


class Budget(Base):
    """A monthly spending limit for one category, or for all spending ("total")."""

    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint(f"category IN ({BUDGET_CATEGORIES})", name="category"),
        CheckConstraint("limit_minor > 0 AND limit_minor <= 1000000000", name="limit_minor"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    category: Mapped[str] = mapped_column(Text, primary_key=True)
    limit_minor: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MerchantCategory(Base):
    """The category a household last chose for a payee, applied to that payee's next entries."""

    __tablename__ = "merchant_categories"
    __table_args__ = (CheckConstraint(f"category IN ({CATEGORIES})", name="category"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # services/money/merchants.py: case-folded, spaces collapsed, at most 80 characters.
    merchant_key: Mapped[str] = mapped_column(Text, primary_key=True)
    category: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
