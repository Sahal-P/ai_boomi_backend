"""Signing in: WhatsApp first, Google as the backup, and the owner's household password.

docs/signup-round/contract.md. Codes, ID tokens and passwords are read once and never stored or
logged; sessions name one household.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from finboy.api.deps import DB, CurrentUser, current_user_id
from finboy.core.access import (
    check_password,
    clear_session,
    issue_household_session,
    issue_session,
    keyed_digest,
    login_nonce,
    production,
    start_login,
)
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.core.errors import AccessError, error_response
from finboy.db.models.accounts import UserIdentity
from finboy.db.models.core import User
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.services.accounts import login
from finboy.services.accounts.google import verify_id_token
from finboy.services.accounts.households import lock_signups, new_household, signup_open
from finboy.services.mail.security import decrypt

router = APIRouter(prefix="/auth", tags=["household access"])


class LoginInput(BaseModel):
    password: SecretStr = Field(min_length=1, max_length=256)


class GoogleInput(BaseModel):
    credential: SecretStr = Field(min_length=20, max_length=4096)
    link: bool = False


class WhatsAppStart(BaseModel):
    purpose: Literal["sign_in", "link"] = "sign_in"


class Household(BaseModel):
    owner: bool
    joined_via: Literal["whatsapp", "google"] | None
    whatsapp: str | None  # masked number, or "linked" when only the private allowlist knows it
    google: str | None  # masked email


class SignInOptions(BaseModel):
    whatsapp: bool
    whatsapp_number: str | None
    google_client_id: str | None
    password: bool
    signup_open: bool
    gmail: bool


class SessionView(BaseModel):
    required: bool
    authenticated: bool
    household: Household | None
    sign_in: SignInOptions


class Started(BaseModel):
    code: str
    link: str | None
    expires_at: datetime


class Progress(BaseModel):
    state: Literal["pending", "confirmed", "declined", "used", "expired"]
    signup_open: bool


def whatsapp_ready(settings: Settings) -> bool:
    return settings.whatsapp_enabled and settings.whatsapp_public_number is not None


def _household(session: Session, settings: Settings, user_id: UUID) -> Household:
    user = session.get(User, user_id)
    binding = session.scalar(
        select(WhatsAppBinding).where(WhatsAppBinding.user_id == user_id).limit(1)
    )
    number = None
    if binding is not None:
        number = "linked"
        if binding.encrypted_sender and settings.token_encryption_key:
            digits = decrypt(
                settings.token_encryption_key.get_secret_value(), binding.encrypted_sender
            )
            number = "•••• " + digits[-4:]
    google = session.scalar(
        select(UserIdentity.email_masked).where(UserIdentity.user_id == user_id).limit(1)
    )
    return Household(
        owner=user_id == LOCAL_USER_ID,
        joined_via=user.joined_via if user else None,  # type: ignore[arg-type]
        whatsapp=number,
        google=google,
    )


@router.get("/session")
def session_view(request: Request, session: DB) -> SessionView:
    settings: Settings = request.app.state.settings
    try:
        user_id: UUID | None = current_user_id(request, session)
    except AccessError, SQLAlchemyError:
        session.rollback()
        user_id = None
    try:
        open_now = signup_open(session, settings)
        household = _household(session, settings, user_id) if user_id else None
    except SQLAlchemyError:
        # The sign-in page still works while the database is briefly unavailable.
        session.rollback()
        open_now = False
        household = (
            Household(owner=user_id == LOCAL_USER_ID, joined_via=None, whatsapp=None, google=None)
            if user_id
            else None
        )
    options = SignInOptions(
        whatsapp=whatsapp_ready(settings),
        whatsapp_number=settings.whatsapp_public_number if whatsapp_ready(settings) else None,
        google_client_id=settings.google_signin_client_id,
        password=production(settings) and settings.household_password_hash is not None,
        signup_open=open_now,
        gmail=user_id == LOCAL_USER_ID or settings.gmail_for_new_accounts,
    )
    return SessionView(
        required=production(settings),
        authenticated=user_id is not None,
        household=household,
        sign_in=options,
    )


@router.post("/login")
def password_login(body: LoginInput, request: Request) -> JSONResponse:
    settings = request.app.state.settings
    if settings.environment != "production":
        return JSONResponse({"authenticated": True})
    if not request.app.state.login_throttle.admit():
        return error_response(request, 429, "try_later", "Please try again in a minute.")
    if not check_password(
        body.password.get_secret_value(), settings.household_password_hash.get_secret_value()
    ):
        return error_response(request, 401, "invalid_credentials", "Unable to sign in.")
    response = JSONResponse({"authenticated": True})
    issue_household_session(request, response)
    return response


@router.post("/logout")
def logout(request: Request) -> JSONResponse:
    response = JSONResponse({"authenticated": False})
    clear_session(request, response)
    return response


@router.post("/logout-everywhere")
def logout_everywhere(request: Request, session: DB, user_id: CurrentUser) -> JSONResponse:
    """Every browser signed in to this household has to sign in again."""
    user = session.get(User, user_id, with_for_update=True)
    if user is not None:
        user.session_epoch += 1
        session.commit()
    response = JSONResponse({"authenticated": False})
    clear_session(request, response)
    return response


def _signed_in(request: Request, user: User) -> JSONResponse:
    response = JSONResponse({"authenticated": True})
    issue_session(request, response, user.id, user.session_epoch)
    return response


def _usable(user: User | None) -> User:
    if user is None or user.deleted_at is not None:
        raise AccessError("invalid_sign_in")
    if user.pilot and user.id != LOCAL_USER_ID:
        raise AccessError("web_not_available")
    return user


@router.post("/google/start")
def google_start(request: Request, response: Response) -> dict[str, str]:
    """The nonce Google puts inside the ID token, bound to this browser's login cookie."""
    settings: Settings = request.app.state.settings
    if not settings.google_signin_client_id:
        raise AccessError("sign_in_unavailable")
    nonce = start_login(request, response)
    return {"nonce": keyed_digest(settings, "google-nonce", nonce)}


@router.post("/google")
def google_sign_in(body: GoogleInput, request: Request, session: DB) -> JSONResponse:
    settings: Settings = request.app.state.settings
    if not settings.google_signin_client_id:
        raise AccessError("sign_in_unavailable")
    if not request.app.state.signin_throttle.admit():
        raise AccessError("try_later")
    nonce = login_nonce(request)
    if nonce is None:
        raise AccessError("invalid_sign_in")
    account = verify_id_token(
        body.credential.get_secret_value(),
        client_id=settings.google_signin_client_id,
        nonce=keyed_digest(settings, "google-nonce", nonce),
        certs=request.app.state.google_certs,
    )
    identity = session.scalar(
        select(UserIdentity)
        .where(
            UserIdentity.provider == "google",
            UserIdentity.subject_sha256 == account.subject_sha256,
        )
        .with_for_update()
    )
    if body.link:
        user_id = current_user_id(request, session)
        if identity is not None and identity.user_id != user_id:
            raise AccessError("already_linked")
        if identity is None:
            session.add(
                UserIdentity(
                    user_id=user_id,
                    provider="google",
                    subject_sha256=account.subject_sha256,
                    email_masked=account.email_masked,
                )
            )
        session.commit()
        return JSONResponse({"linked": True})
    if identity is not None:
        user = _usable(session.get(User, identity.user_id))
        session.commit()
        return _signed_in(request, user)
    # A new Google account is a new household, while there is room.
    lock_signups(session)
    if not settings.signup_enabled:
        raise AccessError("signup_unavailable")
    if not signup_open(session, settings):
        raise AccessError("signups_closed")
    user = new_household(session, joined_via="google", agreed=True)
    session.add(
        UserIdentity(
            user_id=user.id,
            provider="google",
            subject_sha256=account.subject_sha256,
            email_masked=account.email_masked,
        )
    )
    session.commit()
    return _signed_in(request, user)


@router.post("/whatsapp/start")
def whatsapp_start(
    body: WhatsAppStart, request: Request, response: Response, session: DB
) -> Started:
    settings: Settings = request.app.state.settings
    if not whatsapp_ready(settings):
        raise AccessError("sign_in_unavailable")
    if not request.app.state.signin_throttle.admit():
        raise AccessError("try_later")
    # Linking adds this WhatsApp to the household that is signed in here.
    user_id = current_user_id(request, session) if body.purpose == "link" else None
    nonce = start_login(request, response)
    started = login.start(
        session,
        settings,
        nonce=nonce,
        device=login.device_label(request.headers.get("user-agent", "")),
        purpose=body.purpose,
        user_id=user_id,
    )
    return Started(code=started.code, link=started.link, expires_at=started.expires_at)


@router.get("/whatsapp/status")
def whatsapp_status(request: Request, response: Response, session: DB) -> Progress:
    response.headers["Cache-Control"] = "no-store"
    settings: Settings = request.app.state.settings
    nonce = login_nonce(request)
    state = login.state_of(login.latest(session, settings, nonce) if nonce else None)
    return Progress(state=state, signup_open=signup_open(session, settings))


@router.post("/whatsapp/complete")
def whatsapp_complete(request: Request, session: DB) -> JSONResponse:
    settings: Settings = request.app.state.settings
    nonce = login_nonce(request)
    attempt = login.redeem(session, settings, nonce) if nonce else None
    if attempt is None or attempt.user_id is None:
        session.rollback()
        raise AccessError("login_expired")
    if attempt.purpose == "link":
        session.commit()
        return JSONResponse({"linked": True})
    user = _usable(session.get(User, attempt.user_id))
    session.commit()
    return _signed_in(request, user)
