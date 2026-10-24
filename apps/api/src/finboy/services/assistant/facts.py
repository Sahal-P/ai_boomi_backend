"""Full-scope deterministic aggregation before selecting a bounded evidence sample."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.db.models.ledger import Transaction
from finboy.services.money.engine import (
    PeriodSpec,
    TransactionView,
    _transactions,
    period_dates,
    today_ist,
    transaction_views,
)


@dataclass
class FinancialFacts:
    gross_minor: int
    refunds_minor: int
    net_minor: int
    total: int
    evidence: list[TransactionView]


def financial_facts(
    session: Session,
    *,
    user_id: UUID,
    period: PeriodSpec,
    intent: str,
    category: str | None = None,
    merchant: str | None = None,
) -> FinancialFacts:
    start, end = period_dates(period, today_ist())
    rows = list(
        session.scalars(
            _transactions(user_id, start, end)
            .where(Transaction.status == "confirmed", Transaction.kind != "transfer")
            .order_by(Transaction.occurred_at.desc(), Transaction.id)
        )
    )
    parents = {row.id: row for row in rows}
    linked = {row.linked_transaction_id for row in rows if row.linked_transaction_id}
    if linked:
        parents.update(
            {
                row.id: row
                for row in session.scalars(
                    select(Transaction).where(
                        Transaction.user_id == user_id,
                        Transaction.dataset == "household",
                        Transaction.id.in_(linked),
                    )
                )
            }
        )
    selected = []
    for row in rows:
        parent = parents.get(row.linked_transaction_id)
        effective = parent if row.kind in {"refund", "reversal"} and parent else row
        if category and effective.category != category:
            continue
        if (
            merchant
            and merchant.casefold() not in row.merchant.casefold()
            and merchant.casefold() not in effective.merchant.casefold()
        ):
            continue
        if intent == "income_query":
            if row.direction == "in" and row.kind in {"salary", "income_other"}:
                selected.append(row)
        elif (
            intent == "unallocated_query"
            or row.direction == "out"
            or row.kind in {"refund", "reversal"}
        ):
            selected.append(row)
    gross = sum(row.amount_minor for row in selected if row.direction == "out")
    refunds = sum(
        row.amount_minor
        for row in selected
        if row.direction == "in" and row.kind in {"refund", "reversal"}
    )
    net = sum(row.amount_minor for row in selected) if intent == "income_query" else gross - refunds
    return FinancialFacts(
        gross,
        refunds,
        net,
        len(selected),
        transaction_views(session, selected[:10], user_id=user_id),
    )
