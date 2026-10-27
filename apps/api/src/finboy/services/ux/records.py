"""Counted history and independent merge discovery over a single financial snapshot."""

from datetime import datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finboy.core.clock import IST, today_ist
from finboy.db.models.ledger import EmailSource, SourceEvent, Transaction
from finboy.services.money.engine import TransactionView, period_dates, transaction_views
from finboy.services.money.models import PeriodQuery
from finboy.services.ux.state import TaskError, data_version, lock_snapshot


class PageQuery(PeriodQuery):
    scope: Literal["all", "month", "unresolved"] = "month"
    status: Literal["confirmed", "needs_review", "rejected", "merged", "failed"] | None = None
    category: str | None = Field(default=None, max_length=40)
    source: (
        Literal["gmail", "eml_upload", "whatsapp_image", "whatsapp_voice", "manual_entry"] | None
    ) = None
    kind: (
        Literal[
            "purchase",
            "salary",
            "income_other",
            "refund",
            "reversal",
            "fee",
            "bill_payment",
            "emi",
            "investment",
            "transfer",
        ]
        | None
    ) = None
    q: str | None = Field(default=None, min_length=1, max_length=160)
    dataset: Literal["household", "quarantined"] = "household"
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0, le=1000000)
    data_version: str | None = Field(default=None, min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_filters(self) -> PageQuery:
        from typing import get_args

        from finboy.db.models.ledger import Category

        if self.category is not None and self.category not in get_args(Category):
            raise ValueError("invalid_category")
        if self.q is not None and not self.q.strip():
            raise ValueError("invalid_query")
        if self.scope == "unresolved" and self.status not in {None, "needs_review"}:
            raise ValueError("conflicting_status")
        return self


class TransactionPage(BaseModel):
    items: list[TransactionView]
    total: int
    unresolved_total: int
    limit: int
    offset: int
    next_offset: int | None
    data_version: str
    dataset: Literal["household", "quarantined"]


def transaction_page(session: Session, *, user_id: UUID, query: PageQuery) -> TransactionPage:
    version = lock_snapshot(session, user_id)
    if query.data_version is not None and query.data_version != version:
        raise TaskError("version_conflict")
    conditions = [Transaction.user_id == user_id, Transaction.dataset == query.dataset]
    if query.scope == "month" or query.period == "month":
        start, end = period_dates(query.to_period(), today_ist())
        conditions += [
            Transaction.occurred_at >= datetime.combine(start, time.min, IST),
            Transaction.occurred_at <= datetime.combine(end, time.max, IST),
        ]
    if query.scope == "unresolved":
        conditions.append(Transaction.status == "needs_review")
    elif query.status:
        conditions.append(Transaction.status == query.status)
    for field, value in [(Transaction.category, query.category), (Transaction.kind, query.kind)]:
        if value is not None:
            conditions.append(field == value)
    if query.q:
        conditions.append(Transaction.merchant.icontains(query.q.strip(), autoescape=True))
    if query.source:
        conditions.append(
            Transaction.id.in_(
                select(SourceEvent.transaction_id)
                .join(EmailSource, EmailSource.id == SourceEvent.email_source_id)
                .where(EmailSource.user_id == user_id, EmailSource.source == query.source)
            )
        )
    total = session.scalar(select(func.count()).select_from(Transaction).where(*conditions)) or 0
    unresolved = (
        session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.dataset == "household",
                Transaction.status == "needs_review",
            )
        )
        or 0
    )
    rows = list(
        session.scalars(
            select(Transaction)
            .where(*conditions)
            .order_by(Transaction.occurred_at.desc(), Transaction.id)
            .limit(query.limit)
            .offset(query.offset)
        )
    )
    return TransactionPage(
        items=transaction_views(session, rows, user_id=user_id),
        total=total,
        unresolved_total=unresolved,
        limit=query.limit,
        offset=query.offset,
        next_offset=query.offset + len(rows) if query.offset + len(rows) < total else None,
        data_version=version,
        dataset=query.dataset,
    )


class MergeCandidates(BaseModel):
    items: list[TransactionView]
    suggested_id: UUID | None
    data_version: str


def merge_candidates(session: Session, *, user_id: UUID, transaction_id: UUID) -> MergeCandidates:
    item = session.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
            Transaction.dataset == "household",
        )
    )
    if item is None:
        raise TaskError("not_found")
    conditions = [
        Transaction.user_id == user_id,
        Transaction.dataset == "household",
        Transaction.id != item.id,
        Transaction.status.not_in(["merged", "rejected", "failed"]),
        Transaction.direction == item.direction,
        Transaction.currency == item.currency,
    ]
    if item.kind in {"refund", "reversal"}:
        conditions.append(Transaction.kind == item.kind)
    else:
        conditions.append(Transaction.kind.not_in(["refund", "reversal"]))
    rows = list(
        session.scalars(
            select(Transaction)
            .where(*conditions)
            .order_by(
                (Transaction.id == item.possible_duplicate_of_id).desc(),
                func.abs(Transaction.amount_minor - item.amount_minor),
                Transaction.occurred_at.desc(),
                Transaction.id,
            )
            .limit(100)
        )
    )
    return MergeCandidates(
        items=transaction_views(session, rows, user_id=user_id),
        suggested_id=item.possible_duplicate_of_id
        if any(row.id == item.possible_duplicate_of_id for row in rows)
        else None,
        data_version=data_version(session, user_id),
    )
