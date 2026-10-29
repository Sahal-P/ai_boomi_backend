"""Quick add: one typed or spoken sentence becomes a record or a due, saved with one tap.

docs/signup-round/contract.md. The sentence is read once and never stored. Save is the explicit
confirmation, it goes through the same pipeline and versioned decision as everything else, and it
can be undone.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update

from finboy.api.deps import DB, CurrentUser
from finboy.core.clock import now_ist, today_ist
from finboy.core.errors import error_response
from finboy.db.models.core import User
from finboy.db.models.ledger import Commitment, Transaction
from finboy.services.accounts import usage
from finboy.services.ingestion.types import Category
from finboy.services.money import merchants
from finboy.services.money.models import Correction
from finboy.services.ux.decisions import DecisionRequest, decide
from finboy.services.ux.state import data_version
from finboy.services.whatsapp import capture, statement

router = APIRouter(prefix="/entries", tags=["entries"])


class EntryText(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=500)


class EntryPreview(BaseModel):
    kind: Literal["spent", "received", "due", "question", "unclear"]
    amount_minor: int | None
    counterparty: str | None
    category: Category
    day: date | None
    due_date: date | None
    label: str | None


class EntrySave(BaseModel):
    """What the person saw on the preview, possibly edited. Every field is checked again."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["spent", "received", "due"]
    amount_minor: int = Field(gt=0, le=10**9, strict=True)  # at most ₹1 crore
    counterparty: str | None = Field(default=None, min_length=1, max_length=60)
    category: Category = "other"
    day: date | None = None
    due_date: date | None = None
    label: str | None = Field(default=None, min_length=1, max_length=60)

    @model_validator(mode="after")
    def dates_make_sense(self) -> EntrySave:
        today = today_ist()
        for text in (self.counterparty, self.label):
            if text is not None and (not text.strip() or any(ord(c) < 32 for c in text)):
                raise ValueError("Names must be plain text")
        if self.kind == "due":
            if self.due_date is None or not today <= self.due_date <= today + timedelta(days=366):
                raise ValueError("A due needs a date within the next year")
        elif self.day is None or not today - timedelta(days=366) <= self.day <= today:
            raise ValueError("Money moved on a day within the last year")
        return self


class EntrySaved(BaseModel):
    kind: Literal["record", "due"]
    transaction_id: UUID | None = None
    decision_id: UUID | None = None
    obligation_id: UUID | None = None
    data_version: str


@router.post("/preview")
def preview(body: EntryText, request: Request, session: DB, user_id: CurrentUser) -> EntryPreview:
    settings = request.app.state.settings
    usage.use(session, settings, user_id, "ai")
    reading = statement.read_statement(body.text, settings, today_ist())
    if reading.kind in {"budget", "goal"}:
        # Budgets and the savings goal are set on the Overview, not through quick add.
        reading = statement.Statement("unclear")
    # The category this household last chose for the payee comes first (merchant memory).
    remembered = merchants.remembered(session, user_id, reading.counterparty)
    return EntryPreview(
        kind=reading.kind,  # type: ignore[arg-type]
        amount_minor=reading.amount_minor,
        counterparty=reading.counterparty,
        category=remembered if remembered and reading.kind != "due" else reading.category,
        day=reading.day,
        due_date=reading.due_date,
        label=reading.label,
    )


@router.post("", response_model=EntrySaved)
def save(
    body: EntrySave, request: Request, session: DB, user_id: CurrentUser
) -> EntrySaved | JSONResponse:
    if body.kind == "due":
        row = Commitment(
            id=uuid4(),
            user_id=user_id,
            kind="loan",
            label=(body.label or body.counterparty or "Payment").strip(),
            amount_minor=body.amount_minor,
            due_date=body.due_date,
            status="upcoming",
            confidence=Decimal("1.000"),
            user_resolved=False,
        )
        session.add(row)
        session.execute(
            update(User).where(User.id == user_id).values(data_version=User.data_version + 1)
        )
        session.commit()
        return EntrySaved(
            kind="due", obligation_id=row.id, data_version=data_version(session, user_id)
        )
    session.rollback()  # the import pipeline commits through its own sessions
    now = now_ist()
    line = statement.payment_line(
        statement.Statement(
            body.kind, body.amount_minor, body.counterparty, "unknown", body.day, body.category
        ),
        now,
    )
    result = capture.record_entry(
        request.app.state.engine,
        request.app.state.settings,
        user_id=user_id,
        entry_id="entry:" + uuid4().hex,
        line=line,
        received_at=now,
        category=body.category,
    )
    if result.outcome == "busy":
        return error_response(
            request, 409, "entry_busy", "FinBoy is still saving your last entry. Try again."
        )
    row = (
        session.scalar(
            select(Transaction).where(
                Transaction.id == result.transaction_id, Transaction.user_id == user_id
            )
        )
        if result.transaction_id
        else None
    )
    if row is None or row.status != "needs_review":
        return error_response(
            request, 503, "entry_unavailable", "This entry couldn't be saved. Nothing was added."
        )
    # Save is the person's confirmation; keep their category if the pipeline chose another.
    correction = Correction(category=body.category) if row.category != body.category else None
    decided = decide(
        session,
        user_id=user_id,
        transaction_id=row.id,
        request=DecisionRequest(
            action="confirm",
            correction=correction,
            expected_version=data_version(session, user_id),
        ),
    )
    return EntrySaved(
        kind="record",
        transaction_id=row.id,
        decision_id=decided.decision_id,
        data_version=decided.data_version,
    )
