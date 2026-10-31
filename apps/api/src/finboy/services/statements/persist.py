"""Save a checked Google Pay statement as records, in one database transaction.

docs/statement-round/contract.md. Every row keeps its evidence: the name exactly as Google Pay
shows it, the UPI transaction ID, the bank and last four digits, and its page and row. A row already
in FinBoy (the same UPI transaction ID, or the same payment from another source) joins that record
as evidence. A row that may repeat a payment the household said or typed (same direction and amount
within 36 hours) is saved for review beside it and never merged automatically. Every other row is a
confirmed record. The household's lock is held throughout and links are refreshed once at the end.
"""

import hashlib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import get_args
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.db.models.ledger import EmailSource, SourceEvent, Transaction
from finboy.db.models.money import MerchantCategory
from finboy.db.models.statements import StatementImport
from finboy.services.ingestion.pipeline import _user_lock
from finboy.services.ingestion.types import Category, Event
from finboy.services.ledger.categories import INCOME_CATEGORIES, category_for, normalize_merchant
from finboy.services.ledger.confidence import confidence_for
from finboy.services.ledger.matching import choose_match, direction, kind
from finboy.services.ledger.persist import _fingerprint, as_event, attach_evidence, refresh_links
from finboy.services.money.merchants import merchant_key
from finboy.services.statements.gpay import Row, Statement

SOURCE = "gpay_statement"
EXTRACTOR = "gpay-statement-v1"
# A marker, never a mail domain: statement rows are trusted by their source, not by this value.
SENDER_DOMAIN = "google-pay.invalid"
DIARY = frozenset({"whatsapp_voice", "manual_entry"})
DIARY_WINDOW = timedelta(hours=36)
FIELDS = ("account_last4", "amount_minor", "merchant", "occurred_at", "reference_id")
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
# Which remembered payee categories each direction may take; anything else falls back to rules.
RECEIVED = frozenset({"salary", "other_income", "transfer", *INCOME_CATEGORIES})
NOT_SPENDING = frozenset({"salary", "other_income", "wages", "farm_sales", "govt_benefit"})


def row_keys(rows: Sequence[Row]) -> list[str]:
    """`gpay:<UPI ID>:<direction>:<paise>`; a repeat inside one statement gets `:2`, `:3`…

    The same payment in an overlapping statement has the same key, so it is never saved twice.
    """
    seen: Counter[str] = Counter()
    keys = []
    for row in rows:
        base = f"gpay:{row.upi_id}:{row.direction}:{row.amount_minor}"
        seen[base] += 1
        keys.append(base if seen[base] == 1 else f"{base}:{seen[base]}")
    return keys


def row_event(row: Row, category: Category | None) -> Event:
    return Event(
        event_type={"out": "debit", "in": "credit", "other": "transfer"}[row.direction],
        amount_minor=row.amount_minor,
        merchant=row.name[:160],
        occurred_at=row.occurred_at,
        reference_id=row.upi_id,
        payment_instrument="UPI",
        account_last4=row.last4,
        category=category,
        payment_proof=True,
        evidence={
            "payment_proof": "Google Pay statement",
            "statement": "gpay",
            "detail": row.detail[:80],
            "bank": row.bank[:80],
            "page": str(row.page),
            "row": str(row.position),
        },
        field_confidence=dict.fromkeys(FIELDS, 1.0),
        extraction_method="rule",
        extractor_id=EXTRACTOR,
        rule_fields=list(FIELDS),
    )


def row_category(row: Row, remembered: str | None) -> Category:
    """The household's choice for this payee first, then FinBoy's rules."""
    if row.direction == "other":
        return "transfer"
    if remembered in get_args(Category):
        if row.direction == "in" and remembered in RECEIVED:
            return remembered  # type: ignore[return-value]
        if row.direction == "out" and remembered not in NOT_SPENDING:
            return remembered  # type: ignore[return-value]
    return category_for(row_event(row, None))


@dataclass
class _Ledger:
    """The household's records with the evidence each is matched on, loaded once."""

    transactions: list[Transaction]
    events: list[Event]
    diary: list[bool]
    excluded: set[int]
    claimed: set[int] = field(default_factory=set)

    @classmethod
    def load(cls, session: Session, user_id: UUID) -> _Ledger:
        transactions = list(
            session.scalars(
                select(Transaction)
                .where(
                    Transaction.user_id == user_id,
                    Transaction.dataset == "household",
                    Transaction.status != "merged",
                )
                .order_by(Transaction.created_at, Transaction.id)
            )
        )
        evidence: dict[UUID, list[tuple[SourceEvent, str]]] = {}
        for item, source in session.execute(
            select(SourceEvent, EmailSource.source)
            .join(EmailSource, EmailSource.id == SourceEvent.email_source_id)
            .where(SourceEvent.user_id == user_id, SourceEvent.transaction_id.is_not(None))
            .order_by(SourceEvent.created_at, SourceEvent.id)
        ):
            if item.transaction_id is not None:
                evidence.setdefault(item.transaction_id, []).append((item, source))
        events, diary = [], []
        for transaction in transactions:
            rows = evidence.get(transaction.id, [])
            # Matching uses provider evidence even if the user corrected the ledger's amount.
            chosen = next(
                (item for item, _ in rows if "payment_proof" in item.evidence),
                rows[0][0] if rows else None,
            )
            events.append(
                as_event(chosen)
                if chosen
                else Event(
                    event_type="debit",
                    amount_minor=transaction.amount_minor,
                    merchant=transaction.merchant,
                    occurred_at=transaction.occurred_at,
                )
            )
            diary.append(bool(rows) and all(source in DIARY for _, source in rows))
        excluded = {
            index
            for index, transaction in enumerate(transactions)
            if "dedupe" in (transaction.user_locked_fields or [])
        }
        return cls(transactions, events, diary, excluded)

    def match(self, event: Event) -> tuple[int | None, int | None]:
        """(record to join, record this may repeat). Said or typed entries are never joined."""
        indices = [i for i, is_diary in enumerate(self.diary) if not is_diary]
        found = choose_match(
            event,
            [self.events[i] for i in indices],
            excluded={k for k, i in enumerate(indices) if i in self.excluded or i in self.claimed},
        )
        if found.index is not None:
            index = indices[found.index]
            # A record this statement already joined can't take a second row: review instead.
            return (None, index) if index in self.claimed else (index, None)
        if found.possible_index is not None:
            return None, indices[found.possible_index]
        when = event.occurred_at
        spoken = [
            i
            for i, is_diary in enumerate(self.diary)
            if is_diary
            and i not in self.claimed
            and when is not None
            and self.transactions[i].status in {"confirmed", "needs_review"}
            and self.transactions[i].direction == direction(event)
            and self.transactions[i].amount_minor == event.amount_minor
            and abs(self.transactions[i].occurred_at - when) <= DIARY_WINDOW
        ]
        if not spoken or when is None:
            return None, None
        return None, min(spoken, key=lambda i: abs(self.transactions[i].occurred_at - when))


def _new_transaction(
    user_id: UUID, event: Event, category: Category, possible: Transaction | None
) -> Transaction:
    confidence = confidence_for(event, trusted=True, statement=True)
    status, reason = confidence.status, confidence.review_reason
    if event.event_type == "transfer":
        # Google leaves self transfers out of its totals; the household checks them instead.
        status, reason = "needs_review", "low_confidence"
    if possible is not None:
        status, reason = "needs_review", "possible_duplicate"
    return Transaction(
        id=uuid4(),
        user_id=user_id,
        dataset="household",
        direction=direction(event),
        kind=kind(event),
        amount_minor=event.amount_minor,
        currency="INR",
        merchant=normalize_merchant(event.merchant) or "Unknown",
        category=category,
        occurred_at=event.occurred_at,
        reference_id=event.reference_id,
        payment_instrument=event.payment_instrument,
        account_last4=event.account_last4,
        confidence=Decimal(str(confidence.value)),
        confidence_factors=confidence.factors,
        status=status,
        review_reason=reason,
        possible_duplicate_of_id=possible.id if possible else None,
        fingerprint=_fingerprint(event),
        user_locked_fields=[],
    )


def _digest(row: Row) -> str:
    parts = (row.occurred_at.isoformat(), row.detail, row.upi_id, row.bank, row.last4 or "")
    return hashlib.sha256("|".join((*parts, str(row.amount_minor))).encode()).hexdigest()


def statement_record(
    *,
    user_id: UUID,
    run_id: UUID,
    statement: Statement,
    file_sha256: str,
    holder_matches: bool | None,
) -> StatementImport:
    """What the statement said; the row counts are filled in once rows are saved."""
    return StatementImport(
        import_run_id=run_id,
        user_id=user_id,
        provider="gpay",
        period_start=statement.period_start,
        period_end=statement.period_end,
        pages=statement.pages,
        rows_total=len(statement.rows),
        rows_new=0,
        rows_linked=0,
        rows_possible_duplicate=0,
        rows_already_imported=0,
        rows_not_counted=0,
        sent_minor=statement.sent_minor,
        received_minor=statement.received_minor,
        paid_minor=statement.paid_minor,
        got_minor=statement.got_minor,
        reconciled=statement.reconciled,
        accounts=list(statement.accounts),
        file_sha256=file_sha256,
        holder_matches=holder_matches,
    )


def save_statement(
    session: Session, *, user_id: UUID, run_id: UUID, record: StatementImport, statement: Statement
) -> StatementImport:
    """Save every row of a reconciled statement; the caller commits once."""
    if not statement.reconciled:
        raise ValueError("statement_not_reconciled")
    _user_lock(session, user_id)
    keys = row_keys(statement.rows)
    known = (
        set(
            session.scalars(
                select(EmailSource.provider_message_id).where(
                    EmailSource.user_id == user_id,
                    EmailSource.source == SOURCE,
                    EmailSource.provider_message_id.in_(keys),
                )
            )
        )
        if keys
        else set()
    )
    memory = dict(
        session.execute(
            select(MerchantCategory.merchant_key, MerchantCategory.category).where(
                MerchantCategory.user_id == user_id
            )
        ).all()
    )
    ledger = _Ledger.load(session, user_id)
    counts: Counter[str] = Counter()
    sources: list[EmailSource] = []
    events: list[SourceEvent] = []
    created: list[Transaction] = []
    joins: list[tuple[Transaction, SourceEvent, Event, bool]] = []
    first: dict[str, Transaction] = {}
    for row, key in zip(statement.rows, keys, strict=True):
        if key in known:
            counts["already"] += 1
            continue
        category = row_category(row, memory.get(merchant_key(row.name) or ""))
        event = row_event(row, category)
        source = EmailSource(
            id=uuid4(),
            user_id=user_id,
            import_run_id=run_id,
            last_attempt_run_id=run_id,
            source=SOURCE,
            provider_message_id=key,
            content_sha256=_digest(row),
            sender_domain=SENDER_DOMAIN,
            subject_sha256=EMPTY_SHA256,
            received_at=row.occurred_at,
            classification="upi_alert",
            processing_status="extracted",
            attempts=1,
        )
        source_event = SourceEvent(
            id=uuid4(),
            user_id=user_id,
            email_source_id=source.id,
            event_type=event.event_type,
            amount_minor=event.amount_minor,
            currency="INR",
            merchant_raw=row.name,
            merchant_normalized=normalize_merchant(row.name),
            occurred_at=row.occurred_at,
            reference_id=row.upi_id,
            payment_instrument="UPI",
            account_last4=row.last4,
            extraction_method="rule",
            extractor_id=f"{EXTRACTOR};fields={','.join(sorted(FIELDS))}",
            evidence=dict(event.evidence),
            field_confidence=dict(event.field_confidence),
        )
        sources.append(source)
        events.append(source_event)
        join, repeat = ledger.match(event)
        if join is not None:
            target = ledger.transactions[join]
            if category == "other" and target.category != "other":
                event = event.model_copy(update={"category": target.category})
            joins.append((target, source_event, event, ledger.events[join].payment_proof))
            ledger.events[join] = event
            ledger.claimed.add(join)
            counts["linked"] += 1
            continue
        if repeat is not None:
            ledger.claimed.add(repeat)
        base = key.split(":", 4)
        possible = (
            ledger.transactions[repeat] if repeat is not None else first.get(":".join(base[:4]))
        )
        transaction = _new_transaction(user_id, event, category, possible)
        first.setdefault(":".join(base[:4]), transaction)
        source_event.transaction_id = transaction.id
        source_event.origin_transaction_id = transaction.id
        created.append(transaction)
        if row.direction == "other":
            counts["not_counted"] += 1
        elif possible is not None:
            counts["possible"] += 1
        else:
            counts["new"] += 1
    # Parents before children: sources, then records, then the evidence that points at both.
    session.add_all(sources)
    session.flush()
    session.add_all(created)
    session.flush()
    session.add_all(events)
    session.flush()
    for target, source_event, event, had_proof in joins:
        attach_evidence(
            session,
            transaction=target,
            source_event=source_event,
            event=event,
            had_proof=had_proof,
            fallback_time=source_event.occurred_at or target.occurred_at,
        )
    session.flush()
    refresh_links(session, user_id)
    record.rows_new = counts["new"]
    record.rows_linked = counts["linked"]
    record.rows_possible_duplicate = counts["possible"]
    record.rows_already_imported = counts["already"]
    record.rows_not_counted = counts["not_counted"]
    session.add(record)
    session.flush()
    return record
