"""What an imported statement said and found, for its import's result and history."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from finboy.db.models.mail import ImportRun
from finboy.db.models.statements import StatementImport


class StatementView(BaseModel):
    provider: Literal["gpay"]
    period_start: date
    period_end: date
    pages: int
    rows: int
    new: int
    linked: int
    possible_duplicates: int
    already_imported: int
    not_counted: int
    # The statement's own totals, and what FinBoy read from its rows.
    sent_minor: int
    received_minor: int
    paid_minor: int
    got_minor: int
    reconciled: bool
    accounts: list[str]
    holder_matches: bool | None
    removed_at: datetime | None


class RemovalPreview(BaseModel):
    records_removed: int
    records_kept: int
    data_version: str


def statement_view(session: Session, run: ImportRun) -> StatementView | None:
    record = session.get(StatementImport, run.id)
    if record is None or record.user_id != run.user_id:
        return None
    return StatementView(
        provider="gpay",
        period_start=record.period_start,
        period_end=record.period_end,
        pages=record.pages,
        rows=record.rows_total,
        new=record.rows_new,
        linked=record.rows_linked,
        possible_duplicates=record.rows_possible_duplicate,
        already_imported=record.rows_already_imported,
        not_counted=record.rows_not_counted,
        sent_minor=record.sent_minor,
        received_minor=record.received_minor,
        paid_minor=record.paid_minor,
        got_minor=record.got_minor,
        reconciled=record.reconciled,
        accounts=list(record.accounts),
        holder_matches=record.holder_matches,
        removed_at=record.removed_at,
    )
