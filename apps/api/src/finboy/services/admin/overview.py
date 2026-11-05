"""The admin overview, sign-ups, system status and audit log (docs/admin-round/contract.md).

Counts, fixed codes and dates only. Household kinds and plans come from the same rows the
Households page lists, so the two always agree.
"""

import re
from collections import Counter
from datetime import datetime, time, timedelta
from uuid import UUID

from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from finboy.core.clock import IST, today_ist
from finboy.core.config import API_ROOT, Settings
from finboy.db.models.accounts import SignupWaitlist, UsageCounter
from finboy.db.models.admin import AdminEvent, AdminSession, AdminUser
from finboy.db.models.billing import BillingPayment
from finboy.db.models.core import User
from finboy.db.models.mail import ImportRun
from finboy.db.models.whatsapp import WhatsAppDelivery
from finboy.services import providers
from finboy.services.accounts import households as accounts
from finboy.services.admin.audit import DETAIL
from finboy.services.admin.households import (
    BULK_IMPORTS,
    PAGE,
    household_rows,
    kind_of,
    plans_by_household,
    short,
    status_of,
)
from finboy.services.admin.views import (
    AdminRow,
    AuditPage,
    AuditRow,
    Overview,
    SessionRow,
    SignupCounts,
    SystemStatus,
)
from finboy.services.billing import renewals

SCHEMA_HEAD = ScriptDirectory(str(API_ROOT / "alembic")).get_current_head()
RELEASE = re.compile(r"^[0-9a-f]{7,40}$")


def signups(session: Session, settings: Settings, now: datetime) -> SignupCounts:
    waiting = session.execute(
        select(SignupWaitlist.language, func.count(), func.min(SignupWaitlist.joined_at)).group_by(
            SignupWaitlist.language
        )
    ).all()
    stale = session.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.joined_via.is_not(None),
            User.consented_at.is_(None),
            User.deleted_at.is_(None),
            User.created_at < now - accounts.STALE_PENDING,
        )
    )
    oldest = [since for _language, _count, since in waiting if since is not None]
    return SignupCounts(
        enabled=settings.signup_enabled,
        open=accounts.signup_open(session, settings),
        agreed=accounts.agreed_count(session),
        pending=accounts.pending_count(session),
        limit=settings.signup_limit,
        waitlist=sum(count for _language, count, _since in waiting),
        waitlist_languages={language or "unknown": count for language, count, _since in waiting},
        oldest_waiting_since=min(oldest) if oldest else None,
        stale_pending=stale or 0,
    )


def overview(session: Session, settings: Settings, now: datetime) -> Overview:
    rows = household_rows(session, [])
    plans = plans_by_household(session, settings, rows, now)
    kinds: Counter[str] = Counter()
    states: Counter[str] = Counter()
    active = {"today": 0, "week": 0, "month": 0}
    since = {
        "today": datetime.combine(today_ist(), time(), IST),
        "week": now - timedelta(days=7),
        "month": now - timedelta(days=30),
    }
    for row in rows:
        status = status_of(row.deleted_at, row.suspended_at)
        if status != "active":
            kinds[status] += 1
            continue
        kinds[kind_of(row.id, row.pilot, row.joined_via, row.consented_at)] += 1
        states[plans[row.id].state] += 1
        moments = [moment for moment in (row.last_message, row.last_record) if moment]
        for window, start in since.items():
            if moments and max(moments) >= start:
                active[window] += 1
    month_start = datetime.combine(today_ist().replace(day=1), time(), IST)
    paid = session.execute(
        select(func.count(), func.coalesce(func.sum(BillingPayment.amount_minor), 0)).where(
            BillingPayment.status == "paid", BillingPayment.settled_at >= month_start
        )
    ).one()
    week = now - timedelta(days=7)
    return Overview(
        billing_enabled=settings.billing_enabled,
        households=dict(kinds),
        signups=signups(session, settings, now),
        active=active,
        plans=dict(states),
        paid_this_month=paid[0],
        received_this_month_minor=paid[1],
        open_payments=renewals.open_payments(session),
        usage_today={
            kind: count
            for kind, count in session.execute(
                select(UsageCounter.kind, func.sum(UsageCounter.count))
                .where(UsageCounter.day == today_ist())
                .group_by(UsageCounter.kind)
            )
        },
        deliveries_week={
            status: count
            for status, count in session.execute(
                select(
                    func.coalesce(WhatsAppDelivery.provider_status, WhatsAppDelivery.state),
                    func.count(),
                )
                .where(WhatsAppDelivery.created_at >= week)
                .group_by(func.coalesce(WhatsAppDelivery.provider_status, WhatsAppDelivery.state))
            )
        },
        imports_week={
            status: count
            for status, count in session.execute(
                select(ImportRun.status, func.count())
                .where(ImportRun.started_at >= week, ImportRun.mode.in_(BULK_IMPORTS))
                .group_by(ImportRun.status)
            )
        },
    )


def release_name() -> str | None:
    """Releases are unpacked into /opt/finboy/releases/<commit>; elsewhere this is unknown."""
    name = API_ROOT.resolve().parents[1].name
    return name if RELEASE.fullmatch(name) else None


def system(session: Session, settings: Settings) -> SystemStatus:
    database, schema, active, open_payments = "connected", "unavailable", None, None
    try:
        revision = session.scalar(text("SELECT version_num FROM alembic_version"))
        schema = "current" if revision == SCHEMA_HEAD else "behind"
        active = session.scalar(
            select(func.count())
            .select_from(ImportRun)
            .where(ImportRun.status.in_(["queued", "running"]))
        )
        open_payments = renewals.open_payments(session)
    except SQLAlchemyError:
        session.rollback()
        database = "unavailable"

    def configured(ready: bool) -> str:
        return "configured" if ready else "missing"

    return SystemStatus(
        environment=settings.environment,
        release=release_name(),
        database=database,
        schema_status=schema,
        schema_head=SCHEMA_HEAD or "",
        flags={
            "signup_enabled": settings.signup_enabled,
            "whatsapp_enabled": settings.whatsapp_enabled,
            "billing_enabled": settings.billing_enabled,
            "payu_autopay_enabled": settings.payu_autopay_enabled,
            "billing_owner_included": settings.billing_owner_included,
            "triage_enabled": settings.triage_enabled,
            "statement_import_enabled": settings.statement_import_enabled,
            "gmail_for_new_accounts": settings.gmail_for_new_accounts,
        },
        limits={
            "signup_limit": settings.signup_limit,
            "session_days": settings.session_days,
            "daily_ai_limit": settings.daily_ai_limit,
            "daily_voice_limit": settings.daily_voice_limit,
            "admin_session_hours": settings.admin_session_hours,
        },
        providers={
            "assistant": configured(
                bool(settings.openai_api_key and settings.openai_assistant_model)
            ),
            "transcription": configured(providers.transcription(settings)),
            "english_hindi_speech": configured(providers.english_hindi_tts(settings)),
            "malayalam_speech": configured(providers.malayalam_tts(settings)),
            "gmail": configured(providers.gmail(settings)),
            "whatsapp": providers.whatsapp(settings),
            "fast_decisions": providers.triage(settings),
            "payu": configured(bool(settings.payu_merchant_key and settings.payu_merchant_salt)),
            "email": configured(settings.resend_api_key is not None),
        },
        payu_environment=settings.payu_environment,
        active_imports=active,
        open_payments=open_payments,
    )


def audit_page(session: Session, offset: int) -> AuditPage:
    found = session.execute(
        select(AdminEvent, AdminUser.email)
        .outerjoin(AdminUser, AdminUser.id == AdminEvent.admin_id)
        .order_by(AdminEvent.created_at.desc(), AdminEvent.id)
        .offset(offset)
        .limit(PAGE)
    ).all()
    total = session.scalar(select(func.count()).select_from(AdminEvent)) or 0
    following = offset + PAGE
    return AuditPage(
        items=[
            AuditRow(
                id=event.id,
                created_at=event.created_at,
                action=event.action,
                admin_email=email,
                household_id=event.household_id,
                short_id=short(event.household_id) if event.household_id else None,
                detail={key: value for key, value in event.detail.items() if key in DETAIL},
            )
            for event, email in found
        ],
        total=total,
        offset=offset,
        next_offset=following if following < total else None,
    )


def admins(session: Session, me: UUID) -> list[AdminRow]:
    return [
        AdminRow(
            id=admin.id,
            email=admin.email,
            active=admin.disabled_at is None,
            must_change_password=admin.must_change_password,
            last_login_at=admin.last_login_at,
            created_at=admin.created_at,
            you=admin.id == me,
        )
        for admin in session.scalars(select(AdminUser).order_by(AdminUser.created_at))
    ]


def sessions(session: Session, admin_id: UUID, current: UUID, now: datetime) -> list[SessionRow]:
    return [
        SessionRow(
            id=row.id,
            device=row.device,
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            expires_at=row.expires_at,
            current=row.id == current,
        )
        for row in session.scalars(
            select(AdminSession)
            .where(
                AdminSession.admin_id == admin_id,
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > now,
            )
            .order_by(AdminSession.last_seen_at.desc())
        )
    ]
