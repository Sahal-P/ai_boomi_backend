"""Household access: the owner's password and self-serve sign-in (docs/signup-round/contract.md).

Sessions are encrypted claims naming one household; the browser never holds a secret it could
read. Login nonces bind a "Continue with WhatsApp" or Google attempt to the browser that began it.
"""

import hashlib
import hmac
import secrets
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.core.errors import error_response

COOKIE = "__Host-finboy_session"
LOGIN_COOKIE = "__Host-finboy_login"
# Loopback development is plain HTTP, where browsers refuse __Host- and Secure cookies.
DEV_COOKIE = "finboy_session"
DEV_LOGIN_COOKIE = "finboy_login"
SESSION_SECONDS = 12 * 60 * 60  # the owner's household password
LOGIN_SECONDS = 10 * 60
HOUSEHOLD_PAYLOAD = b"finboy:household:v1"
USER_PREFIX = "finboy:user:v2:"
LOGIN_PREFIX = "finboy:login:v1:"
PUBLIC = {
    "/api/v1/health",
    "/api/v1/demo",
    "/api/v1/auth/session",
    "/api/v1/auth/login",
    "/api/v1/auth/google",
    "/api/v1/auth/google/start",
    "/api/v1/auth/whatsapp/start",
    "/api/v1/auth/whatsapp/status",
    "/api/v1/auth/whatsapp/complete",
    "/api/v1/whatsapp/webhook",
    # One-use, expiring OAuth state is validated by the callback, independently of cookies.
    "/api/v1/connections/gmail/callback",
    # A short-lived, single-use capability issued only by authenticated authorization.
    "/api/v1/connections/gmail/handoff",
}
# Small JSON bodies only; an ID token is about 1-2 KB.
BODY_LIMITS = {"/api/v1/auth/login": 4096, "/api/v1/auth/google": 8192}


@dataclass(frozen=True)
class Claim:
    """Whose session this is. `epoch` is None for the owner's household-password session."""

    user_id: UUID
    epoch: int | None


def password_hash(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return "scrypt$" + salt.hex() + "$" + digest.hex()


def valid_password_hash(encoded: str) -> bool:
    try:
        method, salt, digest = encoded.split("$")
        return (
            method == "scrypt"
            and len(bytes.fromhex(salt)) == 16
            and len(bytes.fromhex(digest)) == 64
        )
    except ValueError:
        return False


def check_password(password: str, encoded: str) -> bool:
    if not valid_password_hash(encoded):
        return False
    expected = password_hash(password, salt=bytes.fromhex(encoded.split("$")[1]))
    return hmac.compare_digest(expected, encoded)


def session_key(settings: Settings) -> str:
    """Production requires a configured key; elsewhere a per-process key keeps dev working."""
    if settings.web_session_key is not None:
        return settings.web_session_key.get_secret_value()
    if settings.environment == "production":
        raise RuntimeError("web_session_key is required in production")
    return _DEV_KEY


_DEV_KEY = Fernet.generate_key().decode()


def production(settings: Settings) -> bool:
    return settings.environment == "production"


def cookie_names(settings: Settings) -> tuple[str, str]:
    return (COOKIE, LOGIN_COOKIE) if production(settings) else (DEV_COOKIE, DEV_LOGIN_COOKIE)


def _fernet(app: FastAPI) -> Fernet:
    return Fernet(session_key(app.state.settings))


def read_claim(request: Request) -> Claim | None:
    settings: Settings = request.app.state.settings
    token = request.cookies.get(cookie_names(settings)[0], "")
    if not token or len(token) > 1024:
        return None
    fernet = _fernet(request.app)
    try:
        payload = fernet.decrypt(token.encode(), ttl=settings.session_days * 24 * 60 * 60)
        if payload == HOUSEHOLD_PAYLOAD:
            # The household password keeps its original 12-hour session.
            if fernet.extract_timestamp(token.encode()) < time.time() - SESSION_SECONDS:
                return None
            return Claim(LOCAL_USER_ID, None)
        text = payload.decode("ascii")
        if not text.startswith(USER_PREFIX):
            return None
        user, epoch = text.removeprefix(USER_PREFIX).split(":")
        return Claim(UUID(user), int(epoch))
    except InvalidToken, ValueError, UnicodeError:
        return None


def authenticated(request: Request) -> bool:
    """Whether the browser holds a valid session cookie (the household itself is checked later)."""
    if not production(request.app.state.settings):
        return True
    return getattr(request.state, "claim", None) is not None


def issue_household_session(request: Request, response: Response) -> None:
    _set_session(request, response, HOUSEHOLD_PAYLOAD, SESSION_SECONDS)


def issue_session(request: Request, response: Response, user_id: UUID, epoch: int) -> None:
    payload = f"{USER_PREFIX}{user_id}:{epoch}".encode("ascii")
    settings: Settings = request.app.state.settings
    _set_session(request, response, payload, settings.session_days * 24 * 60 * 60)


def _set_session(request: Request, response: Response, payload: bytes, seconds: int) -> None:
    settings: Settings = request.app.state.settings
    response.set_cookie(
        cookie_names(settings)[0],
        _fernet(request.app).encrypt(payload).decode(),
        max_age=seconds,
        secure=production(settings),
        httponly=True,
        samesite="lax",
        path="/",
    )
    # A finished sign-in attempt leaves nothing behind.
    response.delete_cookie(
        cookie_names(settings)[1],
        path="/",
        secure=production(settings),
        httponly=True,
        samesite="lax",
    )


def clear_session(request: Request, response: Response) -> None:
    settings: Settings = request.app.state.settings
    for name in cookie_names(settings):
        response.delete_cookie(
            name, path="/", secure=production(settings), httponly=True, samesite="lax"
        )


def login_nonce(request: Request) -> str | None:
    """The random value binding a sign-in attempt to this browser, while it is fresh."""
    token = request.cookies.get(cookie_names(request.app.state.settings)[1], "")
    if not token or len(token) > 512:
        return None
    try:
        text = _fernet(request.app).decrypt(token.encode(), ttl=LOGIN_SECONDS).decode("ascii")
    except InvalidToken, ValueError, UnicodeError:
        return None
    return text.removeprefix(LOGIN_PREFIX) if text.startswith(LOGIN_PREFIX) else None


def start_login(request: Request, response: Response) -> str:
    """Reuses a fresh nonce so a WhatsApp attempt survives also trying Google, and vice versa."""
    nonce = login_nonce(request) or secrets.token_urlsafe(32)
    settings: Settings = request.app.state.settings
    response.set_cookie(
        cookie_names(settings)[1],
        _fernet(request.app).encrypt((LOGIN_PREFIX + nonce).encode("ascii")).decode(),
        max_age=LOGIN_SECONDS,
        secure=production(settings),
        httponly=True,
        samesite="lax",
        path="/",
    )
    return nonce


def keyed_digest(settings: Settings, purpose: str, value: str) -> str:
    """HMAC under the session key: lets FinBoy recognise a code or nonce without keeping it."""
    key = session_key(settings).encode("ascii")
    return hmac.new(key, purpose.encode() + b"\0" + value.encode(), hashlib.sha256).hexdigest()


class Throttle:
    """Bounded per-process limit; production intentionally runs a single worker."""

    def __init__(self, limit: int = 10, seconds: float = 60) -> None:
        self.attempts: deque[float] = deque(maxlen=limit)
        self.limit, self.seconds = limit, seconds
        self.lock = Lock()

    def admit(self) -> bool:
        with self.lock:
            now = monotonic()
            while self.attempts and now - self.attempts[0] >= self.seconds:
                self.attempts.popleft()
            if len(self.attempts) >= self.limit:
                return False
            self.attempts.append(now)
            return True


LoginThrottle = Throttle


class HouseholdAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.claim = read_claim(request)
        if not production(request.app.state.settings):
            return await call_next(request)
        path = request.url.path
        if path in BODY_LIMITS:
            length = request.headers.get("content-length", "")
            if not length.isdigit() or int(length) > BODY_LIMITS[path]:
                return error_response(request, 413, "invalid_request", "Request is too large.")
        if path not in PUBLIC and request.method != "OPTIONS" and request.state.claim is None:
            return error_response(request, 401, "authentication_required", "Please sign in.")
        if (
            request.method in {"POST", "PATCH", "DELETE", "PUT"}
            and path != "/api/v1/whatsapp/webhook"
            and request.headers.get("origin") not in request.app.state.settings.allowed_origins
        ):
            return error_response(
                request, 403, "origin_not_allowed", "Request origin is not allowed."
            )
        return await call_next(request)
