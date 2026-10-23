import secrets
from datetime import datetime
from typing import Annotated
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.clock import now_ist
from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.mail import MailConnection
from finboy.db.session import get_session
from finboy.services.imports.locking import import_lock
from finboy.services.imports.runner import create_run, run_import
from finboy.services.mail.http import MailRoute, failure
from finboy.services.mail.oauth import (
    OAuthConfig,
    authorize,
    consume_authorization_handoff,
    consume_state,
    create_authorization_handoff,
    finish_connection,
)
from finboy.services.mail.security import MailError, decrypt
from finboy.services.privacy.audit import audit
from finboy.services.privacy.delete import delete_imported_data

router = APIRouter(prefix="/connections", tags=["connections"], route_class=MailRoute)
DB = Annotated[Session, Depends(get_session)]
STATE_COOKIE = "finboy_oauth_state"
CALLBACK_PATH = "/api/v1/connections/gmail/callback"


class ConnectionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    account_email_masked: str
    status: str
    last_synced_at: datetime | None


def connection_for(session: Session, connection_id: UUID) -> MailConnection:
    connection = session.scalar(
        select(MailConnection)
        .where(
            MailConnection.id == connection_id,
            MailConnection.user_id == LOCAL_USER_ID,
        )
        .with_for_update()
    )
    if connection is None:
        raise HTTPException(404)
    return connection


def web_origin(request: Request) -> str:
    value = request.app.state.settings.web_app_url
    return str(value).rstrip("/") if value else "http://127.0.0.1:3002"


def oauth_redirect(location: str) -> RedirectResponse:
    return RedirectResponse(
        location,
        status_code=307,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


def google_redirect(config: OAuthConfig, url: str, state: str) -> RedirectResponse:
    response = oauth_redirect(url)
    response.set_cookie(
        STATE_COOKIE,
        state,
        httponly=True,
        samesite="lax",
        max_age=600,
        secure=config.redirect_uri.startswith("https:"),
        path=CALLBACK_PATH,
    )
    return response


@router.get("", response_model=list[ConnectionView])
def list_connections(session: DB) -> list[MailConnection]:
    return list(
        session.scalars(
            select(MailConnection)
            .where(MailConnection.user_id == LOCAL_USER_ID)
            .order_by(MailConnection.connected_at.desc())
        )
    )


@router.get("/gmail/authorize", response_model=None)
def gmail_authorize(request: Request, session: DB) -> RedirectResponse:
    try:
        config = OAuthConfig.from_settings(request.app.state.settings)
        callback = urlsplit(config.redirect_uri)
        if callback.hostname != urlsplit(web_origin(request)).hostname:
            ticket = create_authorization_handoff(session, config)
            # Set the host-only state cookie directly on the callback host, after
            # the household-authenticated frontend has issued a one-use handoff.
            return oauth_redirect(
                f"{callback.scheme}://{callback.netloc}/api/v1/connections/gmail/handoff?"
                + urlencode({"ticket": ticket})
            )
        url, state = authorize(session, config)
        return google_redirect(config, url, state)
    except MailError as exc:
        session.rollback()
        return oauth_redirect(f"{web_origin(request)}/connect?error={exc.code}")


@router.get("/gmail/handoff", response_model=None)
def gmail_handoff(request: Request, session: DB, ticket: str = "") -> RedirectResponse:
    try:
        config = OAuthConfig.from_settings(request.app.state.settings)
        url, state = consume_authorization_handoff(session, config, ticket)
        return google_redirect(config, url, state)
    except MailError as exc:
        session.rollback()
        return oauth_redirect(f"{web_origin(request)}/connect?error={exc.code}")


@router.get("/gmail/callback", response_model=None)
def gmail_callback(
    request: Request,
    background: BackgroundTasks,
    session: DB,
    state: str = "",
    code: str = "",
    error: str = "",
) -> RedirectResponse:
    google = None
    try:
        config = OAuthConfig.from_settings(request.app.state.settings)
        cookie = request.cookies.get(STATE_COOKIE, "")
        if not cookie or not state or not secrets.compare_digest(cookie, state):
            raise MailError("invalid_state")
        verifier = consume_state(session, config, state)
        if error:
            raise MailError("consent_denied")
        if not code or len(code) > 4096:
            raise MailError("oauth_failed")
        google = config.google()
        connection = finish_connection(session, config, google, code=code, verifier=verifier)
        audit(session, "gmail.connected", "connection", connection.id)
        audit(session, "gmail.sync_requested", "connection", connection.id)
        run = create_run(session, mode="gmail", connection_id=connection.id)
        background.add_task(
            run_import, request.app.state.engine, request.app.state.settings, run.id
        )
        location = f"{web_origin(request)}/import/{run.id}"
    except Exception as exc:
        session.rollback()
        code_name = exc.code if isinstance(exc, MailError) else "oauth_failed"
        location = f"{web_origin(request)}/connect?error={code_name}"
    finally:
        if google:
            google.close()
    response = oauth_redirect(location)
    response.delete_cookie(STATE_COOKIE, path=CALLBACK_PATH)
    return response


@router.post("/{connection_id}/sync", status_code=202, response_model=None)
def sync(
    connection_id: UUID, request: Request, background: BackgroundTasks, session: DB
) -> dict | JSONResponse:
    try:
        connection = connection_for(session, connection_id)
        if connection.status != "active" or not connection.encrypted_refresh_token:
            raise MailError("connection_inactive")
        audit(session, "gmail.sync_requested", "connection", connection.id)
        run = create_run(session, mode="gmail", connection_id=connection.id)
        background.add_task(
            run_import, request.app.state.engine, request.app.state.settings, run.id
        )
        return {"import_run_id": str(run.id)}
    except MailError as exc:
        session.rollback()
        return failure(request, exc)


def change_status(
    connection_id: UUID, request: Request, session: Session, *, status: str
) -> dict | JSONResponse:
    try:
        connection = connection_for(session, connection_id)
        expected = "active" if status == "paused" else "paused"
        if connection.status != expected:
            raise MailError("connection_inactive")
        connection.status = status
        audit(
            session,
            "gmail.paused" if status == "paused" else "gmail.resumed",
            "connection",
            connection.id,
        )
        session.commit()
        return {"status": "ok"}
    except MailError as exc:
        session.rollback()
        return failure(request, exc)


@router.post("/{connection_id}/pause", response_model=None)
def pause(connection_id: UUID, request: Request, session: DB) -> dict | JSONResponse:
    return change_status(connection_id, request, session, status="paused")


@router.post("/{connection_id}/resume", response_model=None)
def resume(connection_id: UUID, request: Request, session: DB) -> dict | JSONResponse:
    return change_status(connection_id, request, session, status="active")


@router.delete("/{connection_id}", response_model=None)
def disconnect(
    connection_id: UUID, request: Request, session: DB, delete_data: bool = False
) -> dict | JSONResponse:
    google = None
    try:
        # Acquire before touching the grant; a failed deletion must not leave a partial disconnect.
        with import_lock(request.app.state.engine):
            connection = connection_for(session, connection_id)
            if connection.encrypted_refresh_token:
                config = OAuthConfig.from_settings(request.app.state.settings)
                google = config.google()
                token = decrypt(config.encryption_key, connection.encrypted_refresh_token)
                google.revoke(token)
            connection.encrypted_refresh_token = None
            connection.status = "revoked"
            connection.revoked_at = now_ist()
            audit(session, "gmail.revoked", "connection", connection.id)
            if delete_data:
                delete_imported_data(session, connection_id=connection_id)
            session.commit()
        return {"status": "ok"}
    except MailError as exc:
        session.rollback()
        audit(session, "gmail.revoke_failed", "connection", connection_id, result="failure")
        session.commit()
        return failure(request, exc)
    finally:
        if google:
            google.close()
