"""Imported payment-app statements: period, own totals and counts, never the file or its header.

docs/statement-round/contract.md. Each statement row becomes an `email_sources` row (source
`gpay_statement`) with its evidence and record; this table keeps what the statement as a whole said,
so the household can see that it matched and a removal knows what it imported. The phone number and
email printed on a statement are never stored; `holder_matches` keeps only the comparison.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Text, func
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from finboy.db.base import Base


class StatementImport(Base):
    __tablename__ = "statement_imports"
    __table_args__ = (
        CheckConstraint("provider = 'gpay'", name="provider"),
        CheckConstraint("period_start <= period_end", name="period"),
        CheckConstraint(
            "pages > 0 AND rows_total >= 0 AND rows_new >= 0 AND rows_linked >= 0 "
            "AND rows_possible_duplicate >= 0 AND rows_already_imported >= 0 "
            "AND rows_not_counted >= 0 AND sent_minor >= 0 AND received_minor >= 0 "
            "AND paid_minor >= 0 AND got_minor >= 0",
            name="counters",
        ),
        Index("ix_statement_imports_user_id_file_sha256", "user_id", "file_sha256"),
    )

    import_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("import_runs.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(Text)
    period_start: Mapped[date] = mapped_column()
    period_end: Mapped[date] = mapped_column()
    pages: Mapped[int] = mapped_column()
    rows_total: Mapped[int] = mapped_column()
    rows_new: Mapped[int] = mapped_column(server_default=sql("0"))
    rows_linked: Mapped[int] = mapped_column(server_default=sql("0"))
    rows_possible_duplicate: Mapped[int] = mapped_column(server_default=sql("0"))
    rows_already_imported: Mapped[int] = mapped_column(server_default=sql("0"))
    rows_not_counted: Mapped[int] = mapped_column(server_default=sql("0"))
    # The statement's own totals (self transfers excluded by Google), and what FinBoy read.
    sent_minor: Mapped[int] = mapped_column(BigInteger)
    received_minor: Mapped[int] = mapped_column(BigInteger)
    paid_minor: Mapped[int] = mapped_column(BigInteger)
    got_minor: Mapped[int] = mapped_column(BigInteger)
    reconciled: Mapped[bool] = mapped_column(Boolean)
    # Bank name and last four digits only, as the statement prints them.
    accounts: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sql("'{}'::text[]"))
    file_sha256: Mapped[str] = mapped_column(Text)
    holder_matches: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
