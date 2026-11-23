"""The admin panel's API (docs/admin-round/contract.md).

Every route except sign-in needs a live admin session (`CurrentAdmin`), in every environment, and
answers only with the models in services/admin/views.py: activity, never money.
"""

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import update

from finboy.api.deps import DB, AdminAccess, CurrentAdmin
from finboy.core.errors import AccessError
from finboy.db.models.admin import AdminSession, AdminUser
from finboy.services.accounts.login import device_label
from finboy.services.admin import actions, audit, growth, households, messages, overview
from finboy.services.admin import auth as admin_auth
from finboy.services.admin import feedback as feedback_admin
from finboy.services.admin.actions import Actor
from finboy.services.admin.views import (
    AdminRow,
    AuditPage,
    CreatedAdmin,
    Done,
    EraseInput,
    Growth,
    GrowthPeriod,
    HouseholdDetail,
    HouseholdPage,
    Kind,
    LoginInput,
    MessagePage,
    NewAdmin,
    Overview,
    PasswordInput,
    PayLink,
    PaymentPage,
    PaymentRow,
    PremiumInput,
    SessionRow,
    SignupCounts,
    Status,
    SystemStatus,
)
from finboy.services.admin.views import AdminSession as AdminSessionView
from finboy.services.billing.plans import State
from finboy.services.conversations import r2

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)
Offset = Annotated[int, Query(ge=0, le=households.MAX_ROWS)]
# A messages page's `next_before`: the oldest message shown, as "<ISO time>|<UUID>".
CURSOR = r"^\d{4}-\d{2}-\d{2}T[0-9:.]{8,15}(Z|[+-]\d{2}:\d{2})\|[0-9a-f-]{36}$"


def _now() -> datetime:
    return datetime.now(UTC)


def _actor(request: Request, admin: AdminAccess) -> Actor:
    return Actor(admin.id, getattr(request.state, "request_id", None))


def _admit(request: Request, *keys: str) -> None:
    throttle = request.app.state.admin_throttle
    if not all([throttle.admit(key) for key in keys]):
        raise AccessError("try_later")


@router.post("/login")
def login(body: LoginInput, request: Request, session: DB) -> JSONResponse:
    address = request.client.host if request.client else "unknown"
    email_key = hashlib.sha256(body.email.strip().lower().encode()).hexdigest()
    _admit(request, f"address:{address}", f"email:{email_key}")
    attempt = admin_auth.sign_in(
        session,
        request.app.state.settings,
        email=body.email,
        password=body.password,
        device=device_label(request.headers.get("user-agent", "")),
        now=_now(),
    )
    request_id = getattr(request.state, "request_id", None)
    if attempt.token is None or attempt.admin is None:
        audit.record(
            session,
            "login_failed",
            admin_id=attempt.admin.id if attempt.admin else None,
            request_id=request_id,
        )
        session.commit()  # keeps the failure count and any lock
        logger.info("admin.login", extra={"outcome": "failed"})
        raise AccessError("admin_login_failed")
    audit.record(session, "login", admin_id=attempt.admin.id, request_id=request_id)
    session.commit()
    logger.info("admin.login", extra={"outcome": "signed_in"})
    response = JSONResponse(
        AdminSessionView(
            email=attempt.admin.email, must_change_password=attempt.admin.must_change_password
        ).model_dump()
    )
    admin_auth.set_cookie(request, response, attempt.token)
    return response


@router.post("/logout")
def logout(request: Request, session: DB, admin: CurrentAdmin) -> JSONResponse:
    session.execute(
        update(AdminSession).where(AdminSession.id == admin.session_id).values(revoked_at=_now())
    )
    audit.record(session, "logout", admin_id=admin.id, request_id=_actor(request, admin).request_id)
    session.commit()
    response = JSONResponse(Done().model_dump())
    admin_auth.clear_cookie(request, response)
    return response


@router.get("/session", response_model=AdminSessionView)
def session_view(admin: CurrentAdmin) -> AdminSessionView:
    return AdminSessionView(email=admin.email, must_change_password=admin.must_change_password)


@router.post("/password", response_model=AdminSessionView)
def change_password(
    body: PasswordInput, request: Request, session: DB, admin: CurrentAdmin
) -> AdminSessionView:
    _admit(request, f"password:{admin.id}")
    row = session.get(AdminUser, admin.id, with_for_update=True)
    if row is None:
        raise AccessError("admin_required")
    admin_auth.change_password(
        session, row, current=body.current, new=body.new, keep=admin.session_id, now=_now()
    )
    audit.record(
        session, "password_changed", admin_id=admin.id, request_id=_actor(request, admin).request_id
    )
    session.commit()
    return AdminSessionView(email=row.email, must_change_password=False)


@router.get("/overview", response_model=Overview)
def overview_view(request: Request, session: DB, _admin: CurrentAdmin) -> Overview:
    return overview.overview(session, request.app.state.settings, _now())


@router.get("/system", response_model=SystemStatus)
def system_view(request: Request, session: DB, _admin: CurrentAdmin) -> SystemStatus:
    return overview.system(session, request.app.state.settings)


@router.get("/households", response_model=HouseholdPage)
def household_list(
    request: Request,
    session: DB,
    _admin: CurrentAdmin,
    q: Annotated[str, Query(max_length=64)] = "",
    kind: Kind | None = None,
    status: Status | None = None,
    plan: State | None = None,
    # Query values arrive as text, which an integer Literal refuses ("30" is not 30).
    active: Annotated[int | None, Query(ge=1, le=30)] = None,
    offset: Offset = 0,
) -> HouseholdPage:
    now = _now()
    return households.search(
        session,
        request.app.state.settings,
        now=now,
        query=q,
        kind=kind,
        status=status,
        plan=plan,
        active_since=now - timedelta(days=active) if active else None,
        offset=offset,
    )


def _detail(request: Request, session: DB, household_id: UUID) -> HouseholdDetail:
    try:
        return households.detail(session, request.app.state.settings, household_id, _now())
    except LookupError:
        raise AccessError("not_found") from None


@router.get("/households/{household_id}", response_model=HouseholdDetail)
def household_view(
    household_id: UUID, request: Request, session: DB, _admin: CurrentAdmin
) -> HouseholdDetail:
    return _detail(request, session, household_id)


@router.get("/households/{household_id}/messages", response_model=MessagePage)
def household_messages(
    household_id: UUID,
    request: Request,
    session: DB,
    admin: CurrentAdmin,
    before: Annotated[str | None, Query(max_length=100, pattern=CURSOR)] = None,
) -> MessagePage:
    """Kept messages, newest first (docs/conversation-round/contract.md). Opening the first page
    is recorded in the audit log."""
    try:
        found = messages.page(session, household_id, before)
    except LookupError:
        raise AccessError("not_found") from None
    if before is None:
        audit.record(
            session,
            "messages_viewed",
            admin_id=admin.id,
            household_id=household_id,
            request_id=_actor(request, admin).request_id,
        )
        session.commit()
    return found


@router.get("/messages/{message_id}/media", include_in_schema=False)
def message_media(message_id: UUID, request: Request, session: DB, admin: CurrentAdmin) -> Response:
    """A kept voice note or photo, through the API so each open is an admin's and recorded."""
    found = messages.media(session, request.app.state.settings, message_id)
    audit.record(
        session,
        "media_opened",
        admin_id=admin.id,
        household_id=found.user_id,
        request_id=_actor(request, admin).request_id,
    )
    session.commit()
    name = f"finboy-{message_id}.{r2.EXTENSIONS[found.content_type]}"
    return Response(
        content=found.data,
        media_type=found.content_type,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{name}"',
        },
    )


class FeedbackStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: feedback_admin.Status


@router.get("/feedback", response_model=feedback_admin.FeedbackPage)
def feedback_list(
    session: DB,
    _admin: CurrentAdmin,
    status: Annotated[feedback_admin.Status | None, Query()] = None,
    offset: Offset = 0,
) -> feedback_admin.FeedbackPage:
    """Reports, newest first, without their words (docs/feedback-round/contract.md)."""
    found = feedback_admin.page(session, status, offset)
    session.rollback()
    return found


@router.get("/feedback/{feedback_id}", response_model=feedback_admin.FeedbackDetail)
def feedback_view(
    feedback_id: UUID, request: Request, session: DB, admin: CurrentAdmin
) -> feedback_admin.FeedbackDetail:
    """One report with its words; each open is recorded in the audit log."""
    found = feedback_admin.detail(session, feedback_id)
    audit.record(
        session,
        "feedback_viewed",
        admin_id=admin.id,
        household_id=found.household_id,
        request_id=_actor(request, admin).request_id,
    )
    session.commit()
    return found


@router.patch("/feedback/{feedback_id}", response_model=feedback_admin.FeedbackDetail)
def feedback_status(
    feedback_id: UUID, body: FeedbackStatus, request: Request, session: DB, admin: CurrentAdmin
) -> feedback_admin.FeedbackDetail:
    """New, Planned or Done; the household sees it on its feedback page."""
    found = feedback_admin.set_status(session, feedback_id, body.status)
    audit.record(
        session,
        "feedback_status_changed",
        admin_id=admin.id,
        household_id=found.household_id,
        request_id=_actor(request, admin).request_id,
    )
    session.commit()
    return found


@router.get("/feedback/{feedback_id}/screenshot", include_in_schema=False)
def feedback_screenshot(
    feedback_id: UUID, request: Request, session: DB, admin: CurrentAdmin
) -> Response:
    """A report's screenshot, through the API so each open is an admin's and recorded."""
    household_id, content_type, data = feedback_admin.screenshot(
        session, request.app.state.settings, feedback_id
    )
    audit.record(
        session,
        "feedback_screenshot_opened",
        admin_id=admin.id,
        household_id=household_id,
        request_id=_actor(request, admin).request_id,
    )
    session.commit()
    name = f"finboy-feedback-{feedback_id}.{r2.EXTENSIONS[content_type]}"
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{name}"',
        },
    )


@router.post("/households/{household_id}/sign-out", response_model=HouseholdDetail)
def household_sign_out(
    household_id: UUID, request: Request, session: DB, admin: CurrentAdmin
) -> HouseholdDetail:
    settings = request.app.state.settings
    actions.sign_out(session, settings, _actor(request, admin), household_id, _now())
    return _detail(request, session, household_id)


@router.post("/households/{household_id}/suspend", response_model=HouseholdDetail)
def household_suspend(
    household_id: UUID, request: Request, session: DB, admin: CurrentAdmin
) -> HouseholdDetail:
    settings = request.app.state.settings
    actions.suspend(session, settings, _actor(request, admin), household_id, _now())
    return _detail(request, session, household_id)


@router.post("/households/{household_id}/restore", response_model=HouseholdDetail)
def household_restore(
    household_id: UUID, request: Request, session: DB, admin: CurrentAdmin
) -> HouseholdDetail:
    settings = request.app.state.settings
    actions.restore(session, settings, _actor(request, admin), household_id, _now())
    return _detail(request, session, household_id)


@router.post("/households/{household_id}/erase", response_model=Done)
def household_erase(
    household_id: UUID, body: EraseInput, request: Request, session: DB, admin: CurrentAdmin
) -> Done:
    actions.erase(
        session,
        request.app.state.settings,
        request.app.state.engine,
        _actor(request, admin),
        household_id,
        confirm=body.confirm,
        now=_now(),
    )
    logger.info("admin.action", extra={"code": "household_erased", "outcome": "erased"})
    return Done()


@router.post("/households/{household_id}/premium", response_model=HouseholdDetail)
def household_premium(
    household_id: UUID, body: PremiumInput, request: Request, session: DB, admin: CurrentAdmin
) -> HouseholdDetail:
    settings = request.app.state.settings
    actions.grant(session, settings, _actor(request, admin), household_id, body.days, _now())
    return _detail(request, session, household_id)


@router.post("/households/{household_id}/autopay/cancel", response_model=HouseholdDetail)
def household_autopay_cancel(
    household_id: UUID, request: Request, session: DB, admin: CurrentAdmin
) -> HouseholdDetail:
    settings = request.app.state.settings
    actions.cancel_autopay(session, settings, _actor(request, admin), household_id, _now())
    return _detail(request, session, household_id)


@router.post("/households/{household_id}/pay-link", response_model=PayLink)
def household_pay_link(
    household_id: UUID, request: Request, session: DB, admin: CurrentAdmin
) -> PayLink:
    settings = request.app.state.settings
    return PayLink(
        url=actions.pay_link(session, settings, _actor(request, admin), household_id, _now())
    )


@router.get("/payments", response_model=PaymentPage)
def payment_list(
    session: DB,
    _admin: CurrentAdmin,
    status: Literal["started", "scheduled", "pending", "paid", "failed", "abandoned"] | None = None,
    offset: Offset = 0,
) -> PaymentPage:
    return actions.payments(session, status=status, offset=offset)


@router.post("/payments/{payment_id}/reconcile", response_model=PaymentRow)
def payment_reconcile(
    payment_id: UUID, request: Request, session: DB, admin: CurrentAdmin
) -> PaymentRow:
    return actions.reconcile(
        session, request.app.state.settings, _actor(request, admin), payment_id
    )


# How far back "Where sign-ups came from" looks (docs/ad-journey-round/contract.md); the panel
# offers 7, 30 and 90 days.
SourceDays = Annotated[int, Query(ge=1, le=90)]


@router.get("/signups", response_model=SignupCounts)
def signup_view(
    request: Request, session: DB, _admin: CurrentAdmin, days: SourceDays = 30
) -> SignupCounts:
    return overview.signups(session, request.app.state.settings, _now(), days)


@router.post("/signups/tidy", response_model=SignupCounts)
def signup_tidy(
    request: Request, session: DB, admin: CurrentAdmin, days: SourceDays = 30
) -> SignupCounts:
    actions.tidy(session, _actor(request, admin))
    return overview.signups(session, request.app.state.settings, _now(), days)


@router.get("/growth", response_model=Growth)
def growth_view(session: DB, _admin: CurrentAdmin, period: GrowthPeriod = "30d") -> Growth:
    """How self-serve households joined, stayed and used FinBoy (docs/admin-growth)."""
    return growth.growth(session, period, _now())


@router.get("/admins", response_model=list[AdminRow])
def admin_list(session: DB, admin: CurrentAdmin) -> list[AdminRow]:
    return overview.admins(session, admin.id)


@router.post("/admins", response_model=CreatedAdmin)
def admin_create(
    body: NewAdmin, request: Request, session: DB, admin: CurrentAdmin
) -> CreatedAdmin:
    temporary = admin_auth.temporary_password()
    created = admin_auth.create_admin(
        session,
        email=body.email,
        password=temporary,
        created_by=admin.id,
        must_change_password=True,
    )
    audit.record(
        session,
        "admin_created",
        admin_id=admin.id,
        request_id=_actor(request, admin).request_id,
        admin=str(created.id),
    )
    session.commit()
    return CreatedAdmin(email=created.email, temporary_password=temporary)


@router.post("/admins/{admin_id}/disable", response_model=list[AdminRow])
def admin_disable(
    admin_id: UUID, request: Request, session: DB, admin: CurrentAdmin
) -> list[AdminRow]:
    target = session.get(AdminUser, admin_id, with_for_update=True)
    if target is None:
        raise AccessError("not_found")
    admin_auth.disable_admin(session, target, actor=admin.id, now=_now())
    audit.record(
        session,
        "admin_disabled",
        admin_id=admin.id,
        request_id=_actor(request, admin).request_id,
        admin=str(target.id),
    )
    session.commit()
    return overview.admins(session, admin.id)


@router.get("/sessions", response_model=list[SessionRow])
def session_list(session: DB, admin: CurrentAdmin) -> list[SessionRow]:
    return overview.sessions(session, admin.id, admin.session_id, _now())


@router.post("/sessions/sign-out-others", response_model=list[SessionRow])
def sign_out_others(request: Request, session: DB, admin: CurrentAdmin) -> list[SessionRow]:
    now = _now()
    ended = admin_auth.revoke_all(session, admin.id, now, keep=admin.session_id)
    audit.record(
        session,
        "sessions_revoked",
        admin_id=admin.id,
        request_id=_actor(request, admin).request_id,
        removed=ended,
    )
    session.commit()
    return overview.sessions(session, admin.id, admin.session_id, now)


@router.get("/audit", response_model=AuditPage)
def audit_view(session: DB, _admin: CurrentAdmin, offset: Offset = 0) -> AuditPage:
    return overview.audit_page(session, offset)
