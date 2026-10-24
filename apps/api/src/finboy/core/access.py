"""Single-household access. No sign-up, shared browser secrets, or user-data claims."""

import hashlib
import hmac
import secrets
from collections import deque
from threading import Lock
from time import monotonic

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from finboy.core.errors import error_response

COOKIE = "__Host-finboy_session"
SESSION_SECONDS = 12 * 60 * 60
PUBLIC = {
    "/api/v1/health",
    "/api/v1/demo",
    "/api/v1/auth/session",
    "/api/v1/auth/login",
    "/api/v1/whatsapp/webhook",
    # One-use, expiring OAuth state is validated by the callback, independently of cookies.
    "/api/v1/connections/gmail/callback",
    # A short-lived, single-use capability issued only by authenticated authorization.
    "/api/v1/connections/gmail/handoff",
}


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


def authenticated(request: Request) -> bool:
    settings = request.app.state.settings
    if settings.environment != "production":
        return True
    token = request.cookies.get(COOKIE, "")
    if len(token) > 1024 or not token:
        return False
    try:
        payload = Fernet(settings.web_session_key.get_secret_value()).decrypt(
            token.encode(), ttl=SESSION_SECONDS
        )
        return payload == b"finboy:household:v1"
    except InvalidToken, ValueError, UnicodeError:
        return False


class LoginThrottle:
    """Bounded per-process limit; production intentionally runs a single worker."""

    def __init__(self) -> None:
        self.attempts: deque[float] = deque(maxlen=10)
        self.lock = Lock()

    def admit(self) -> bool:
        with self.lock:
            now = monotonic()
            while self.attempts and now - self.attempts[0] >= 60:
                self.attempts.popleft()
            if len(self.attempts) >= 10:
                return False
            self.attempts.append(now)
            return True


class HouseholdAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.app.state.settings.environment != "production":
            return await call_next(request)
        path = request.url.path
        if path == "/api/v1/auth/login":
            length = request.headers.get("content-length", "")
            if not length.isdigit() or int(length) > 4096:
                return error_response(request, 413, "invalid_request", "Request is too large.")
        if path not in PUBLIC and request.method != "OPTIONS" and not authenticated(request):
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
