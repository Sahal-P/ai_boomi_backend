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
from fastapi.responses import JSONResponse
from sqlalchemy import update

from finboy.api.deps import DB, AdminAccess, CurrentAdmin
from finboy.core.errors import AccessError
from finboy.db.models.admin import AdminSession, AdminUser
from finboy.services.accounts.login import device_label
from finboy.services.admin import actions, audit, households, overview
from finboy.services.admin import auth as admin_auth
from finboy.services.admin.actions import Actor
from finboy.services.admin.views import (
    AdminRow,
    AuditPage,
    CreatedAdmin,
    Done,
    EraseInput,
    HouseholdDetail,
    HouseholdPage,
    Kind,
    LoginInput,
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

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)
Offset = Annotated[int, Query(ge=0, le=households.MAX_ROWS)]


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
    active: Literal[7, 30] | None = None,
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


@router.get("/signups", response_model=SignupCounts)
def signup_view(request: Request, session: DB, _admin: CurrentAdmin) -> SignupCounts:
    return overview.signups(session, request.app.state.settings, _now())


@router.post("/signups/tidy", response_model=SignupCounts)
def signup_tidy(request: Request, session: DB, admin: CurrentAdmin) -> SignupCounts:
    actions.tidy(session, _actor(request, admin))
    return overview.signups(session, request.app.state.settings, _now())


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
