"""Households as an admin sees them (docs/admin-round/contract.md): kinds, dates, plans, counts.

The owner's stored name is a real first name, so `display_name` is never read here; every
household is its short ID. Phone search compares the typed number's keyed hash with the stored
one, so no number is decrypted or listed.
"""

import re
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, Text, and_, cast, exists, func, select
from sqlalchemy.orm import Session

from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.db.models.accounts import UserIdentity
from finboy.db.models.billing import BillingPayment, Subscription
from finboy.db.models.core import User
from finboy.db.models.ledger import Commitment, Transaction
from finboy.db.models.mail import ImportRun, MailConnection
from finboy.db.models.money import Budget
from finboy.db.models.statements import StatementImport
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.services.accounts import usage
from finboy.services.admin.views import (
    Action,
    GmailState,
    HouseholdDetail,
    HouseholdPage,
    HouseholdRow,
    ImportRow,
    Kind,
    PaymentRow,
    PlanSummary,
    StatementRow,
    Status,
    Usage,
    WhatsAppState,
)
from finboy.services.billing.plans import Plan, State, plan_from
from finboy.services.whatsapp.config import keyed_digest

PAGE = 50
# Households are bounded by SIGNUP_LIMIT and the pending cap, so a page is cut from one query.
MAX_ROWS = 10_000
# Imports an operator follows; each quick add or WhatsApp photo or voice note is its own run and
# already shows as a record.
BULK_IMPORTS = ("gmail", "eml_upload", "gpay_statement", "demo_mailbox")
HEX = re.compile(r"^[0-9a-f-]{4,36}$")


def short(user_id: UUID) -> str:
    return user_id.hex[:8]


def kind_of(user_id: UUID, pilot: bool, joined_via: str | None, agreed: datetime | None) -> Kind:
    if user_id == LOCAL_USER_ID:
        return "owner"
    if pilot:
        return "pilot"
    if joined_via is not None:
        return "self_serve" if agreed is not None else "pending"
    return "former_pilot"  # a pilot household whose records were erased on request


def status_of(deleted_at: datetime | None, suspended_at: datetime | None) -> Status:
    if deleted_at is not None:
        return "deleted"
    return "suspended" if suspended_at is not None else "active"


def sender_digest(settings: Settings, text: str) -> str | None:
    """The stored hash an exact WhatsApp number would have; India's 10 digits gain the 91."""
    digits = re.sub(r"\D", "", text)
    if len(digits) == 10:
        digits = "91" + digits
    if not 7 <= len(digits) <= 20 or settings.token_encryption_key is None:
        return None
    return keyed_digest(settings.token_encryption_key.get_secret_value().encode(), "sender", digits)


def _kind_filter(kind: Kind) -> ColumnElement[bool]:
    not_owner = User.id != LOCAL_USER_ID
    return {
        "owner": User.id == LOCAL_USER_ID,
        "pilot": and_(User.pilot.is_(True), not_owner),
        "self_serve": and_(User.joined_via.is_not(None), User.consented_at.is_not(None)),
        "pending": and_(User.joined_via.is_not(None), User.consented_at.is_(None)),
        "former_pilot": and_(User.joined_via.is_(None), User.pilot.is_(False), not_owner),
    }[kind]


def _status_filter(status: Status) -> ColumnElement[bool]:
    return {
        "active": and_(User.deleted_at.is_(None), User.suspended_at.is_(None)),
        "suspended": and_(User.deleted_at.is_(None), User.suspended_at.is_not(None)),
        "deleted": User.deleted_at.is_not(None),
    }[status]


def household_rows(session: Session, filters: list[ColumnElement[bool]]):
    last_message = (
        select(func.max(WhatsAppBinding.last_inbound_at))
        .where(WhatsAppBinding.user_id == User.id)
        .scalar_subquery()
    )
    last_record = (
        select(func.max(Transaction.created_at))
        .where(Transaction.user_id == User.id, Transaction.dataset == "household")
        .scalar_subquery()
    )
    language = (
        select(func.coalesce(WhatsAppBinding.language, WhatsAppBinding.last_language))
        .where(WhatsAppBinding.user_id == User.id)
        .order_by(WhatsAppBinding.created_at)
        .limit(1)
        .scalar_subquery()
    )
    query = select(
        User.id,
        User.pilot,
        User.joined_via,
        User.created_at,
        User.consented_at,
        User.deleted_at,
        User.suspended_at,
        exists().where(WhatsAppBinding.user_id == User.id).label("whatsapp"),
        exists().where(UserIdentity.user_id == User.id).label("google"),
        last_message.label("last_message"),
        last_record.label("last_record"),
        language.label("language"),
    )
    return session.execute(
        query.where(*filters).order_by(User.created_at.desc(), User.id).limit(MAX_ROWS)
    ).all()


def plans_by_household(
    session: Session, settings: Settings, rows, now: datetime
) -> dict[UUID, Plan]:
    ids = [row.id for row in rows]
    subscriptions = {
        item.user_id: item
        for item in session.scalars(select(Subscription).where(Subscription.user_id.in_(ids)))
    }
    return {
        row.id: plan_from(
            settings,
            row.id,
            pilot=row.pilot,
            joined=row.consented_at or row.created_at,
            subscription=subscriptions.get(row.id),
            now=now,
        )
        for row in rows
    }


def _row(row, plan: Plan) -> HouseholdRow:
    moments = [moment for moment in (row.last_message, row.last_record) if moment is not None]
    return HouseholdRow(
        id=row.id,
        short_id=short(row.id),
        kind=kind_of(row.id, row.pilot, row.joined_via, row.consented_at),
        status=status_of(row.deleted_at, row.suspended_at),
        whatsapp=row.whatsapp,
        google=row.google,
        joined_at=row.created_at,
        agreed_at=row.consented_at,
        last_active_at=max(moments) if moments else None,
        plan=plan.state,
        language=row.language,
    )


def search(
    session: Session,
    settings: Settings,
    *,
    now: datetime,
    query: str = "",
    kind: Kind | None = None,
    status: Status | None = None,
    plan: State | None = None,
    active_since: datetime | None = None,
    offset: int = 0,
) -> HouseholdPage:
    filters: list[ColumnElement[bool]] = []
    text = query.strip().lower()
    if text:
        # Ten or more digits is a phone number; anything else hex-like is a household ID.
        digits = re.sub(r"[\s+()-]", "", text)
        if digits.isdigit() and len(digits) >= 10:
            digest = sender_digest(settings, digits)
            if digest is None:
                return HouseholdPage(items=[], total=0, offset=0, next_offset=None)
            filters.append(
                User.id.in_(
                    select(WhatsAppBinding.user_id).where(WhatsAppBinding.sender_hash == digest)
                )
            )
        elif HEX.fullmatch(text):
            filters.append(cast(User.id, Text).like(text.replace("-", "")[:8] + "%"))
        else:
            return HouseholdPage(items=[], total=0, offset=0, next_offset=None)
    if kind is not None:
        filters.append(_kind_filter(kind))
    if status is not None:
        filters.append(_status_filter(status))
    rows = household_rows(session, filters)
    plans = plans_by_household(session, settings, rows, now)
    items = [_row(row, plans[row.id]) for row in rows]
    if plan is not None:
        items = [item for item in items if item.plan == plan]
    if active_since is not None:
        items = [
            item for item in items if item.last_active_at and item.last_active_at >= active_since
        ]
    page = items[offset : offset + PAGE]
    following = offset + PAGE
    return HouseholdPage(
        items=page,
        total=len(items),
        offset=offset,
        next_offset=following if following < len(items) else None,
    )


def payment_row(payment: BillingPayment) -> PaymentRow:
    return PaymentRow(
        id=payment.id,
        household_id=payment.user_id,
        short_id=short(payment.user_id),
        created_at=payment.created_at,
        amount_minor=payment.amount_minor,
        status=payment.status,
        kind=payment.kind,
        mode=payment.mode,
        txnid=payment.txnid,
        payu_id=payment.payu_id,
        error_code=payment.error_code,
        covers_to=payment.covers_to,
    )


def allowed(kind: Kind, status: Status, plan: Plan, settings: Settings) -> list[Action]:
    """What an admin may do to this household; the API refuses everything else."""
    if kind in {"owner", "former_pilot"} or status == "deleted":
        return []
    if kind == "pending":
        return ["erase"]
    if status == "suspended":
        return ["restore", "erase"]
    actions: list[Action] = ["suspend", "erase"]
    if kind == "self_serve":
        actions.insert(0, "sign_out")
        if settings.billing_enabled:
            actions += ["premium", "pay_link"]
            if plan.renewal == "autopay":
                actions.append("autopay_cancel")
    return actions


def _counts(session: Session, column, *where: ColumnElement[bool]) -> dict[str, int]:
    return {
        str(key): count
        for key, count in session.execute(
            select(column, func.count()).where(*where).group_by(column)
        )
    }


def detail(session: Session, settings: Settings, user_id: UUID, now: datetime) -> HouseholdDetail:
    rows = household_rows(session, [User.id == user_id])
    if not rows:
        raise LookupError(user_id)
    row = rows[0]
    plan = plans_by_household(session, settings, rows, now)[row.id]
    base = _row(row, plan)
    binding = session.scalar(
        select(WhatsAppBinding)
        .where(WhatsAppBinding.user_id == user_id)
        .order_by(WhatsAppBinding.created_at)
        .limit(1)
    )
    gmail = session.scalar(
        select(MailConnection)
        .where(MailConnection.user_id == user_id)
        .order_by(MailConnection.connected_at.desc())
        .limit(1)
    )
    today = usage.today(session, user_id)
    payments = session.scalars(
        select(BillingPayment)
        .where(BillingPayment.user_id == user_id)
        .order_by(BillingPayment.created_at.desc())
        .limit(20)
    ).all()
    imports = session.scalars(
        select(ImportRun)
        .where(ImportRun.user_id == user_id, ImportRun.mode.in_(BULK_IMPORTS))
        .order_by(ImportRun.started_at.desc().nulls_last())
        .limit(10)
    ).all()
    statements = session.scalars(
        select(StatementImport)
        .where(StatementImport.user_id == user_id)
        .order_by(StatementImport.created_at.desc())
        .limit(10)
    ).all()
    goal = session.scalar(select(User.monthly_savings_goal_minor).where(User.id == user_id))
    return HouseholdDetail(
        **base.model_dump(),
        suspended_at=row.suspended_at,
        deleted_at=row.deleted_at,
        last_message_at=row.last_message,
        last_record_at=row.last_record,
        google_email=session.scalar(
            select(UserIdentity.email_masked).where(UserIdentity.user_id == user_id).limit(1)
        ),
        plan_detail=PlanSummary(
            state=plan.state,
            trial_ends_at=plan.trial_ends_at,
            paid_through=plan.paid_through,
            renewal=plan.renewal,
            next_charge_on=plan.next_charge_on,
            grace_until=plan.grace_until,
        ),
        payments=[payment_row(payment) for payment in payments],
        usage=Usage(
            ai=today["ai"],
            voice=today["voice"],
            ai_limit=settings.daily_ai_limit,
            voice_limit=settings.daily_voice_limit,
        ),
        records=_counts(
            session,
            Transaction.status,
            Transaction.user_id == user_id,
            Transaction.dataset == "household",
        ),
        dues=_counts(
            session,
            Commitment.status,
            Commitment.user_id == user_id,
            Commitment.dataset == "household",
        ),
        budgets=session.scalar(
            select(func.count()).select_from(Budget).where(Budget.user_id == user_id)
        )
        or 0,
        goal_set=goal is not None,
        imports=[
            ImportRow(
                mode=run.mode,
                status=run.status,
                error_code=run.error_code,
                started_at=run.started_at,
                finished_at=run.finished_at,
            )
            for run in imports
        ],
        statements=[
            StatementRow(
                period_start=item.period_start,
                period_end=item.period_end,
                pages=item.pages,
                rows_total=item.rows_total,
                reconciled=item.reconciled,
                removed=item.removed_at is not None,
            )
            for item in statements
        ],
        gmail=GmailState(
            status=gmail.status,
            connected_at=gmail.connected_at,
            last_synced_at=gmail.last_synced_at,
            revoked=gmail.revoked_at is not None,
        )
        if gmail
        else None,
        whatsapp_state=WhatsAppState(
            replies_on=binding.enabled,
            agreed_at=binding.consented_at,
            reminders=binding.reminders_opt_in_at is not None,
            checkins=binding.checkin_opt_in_at is not None,
            language=binding.language or binding.last_language,
            last_message_at=binding.last_inbound_at,
        )
        if binding
        else None,
        actions=allowed(base.kind, base.status, plan, settings),
    )
