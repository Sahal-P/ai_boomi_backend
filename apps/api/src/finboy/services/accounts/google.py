"""Sign in with Google: verify an ID token from Google Identity Services. Backend only.

Only the account's subject (hashed) and a masked email are kept. The token itself, the name and
the photo are never stored or logged. Basic sign-in scopes need Google brand verification, not
the restricted-scope review that Gmail access needs.
"""

import hashlib
import hmac
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import Lock

import httpx

from finboy.core.errors import AccessError
from finboy.services.mail.security import MailError, mask_email

CERTS_URL = "https://www.googleapis.com/oauth2/v1/certs"
ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})


@dataclass(frozen=True)
class GoogleAccount:
    subject_sha256: str
    email_masked: str | None


class GoogleCerts:
    """Google's public signing certificates, cached for as long as Google says they're valid."""

    def __init__(self, fetch: Callable[[], httpx.Response] | None = None) -> None:
        self._fetch = fetch or (lambda: httpx.get(CERTS_URL, timeout=10))
        self._certs: dict[str, str] = {}
        self._until = 0.0
        self._lock = Lock()

    def __call__(self) -> Mapping[str, str]:
        with self._lock:
            if self._certs and time.monotonic() < self._until:
                return self._certs
            try:
                response = self._fetch()
                response.raise_for_status()
                certs = response.json()
            except httpx.HTTPError, ValueError:
                raise AccessError("sign_in_unavailable") from None
            if (
                not isinstance(certs, dict)
                or not certs
                or not all(
                    isinstance(key, str) and isinstance(value, str) for key, value in certs.items()
                )
            ):
                raise AccessError("sign_in_unavailable")
            age = re.search(r"max-age=(\d+)", response.headers.get("cache-control", ""))
            self._certs = certs
            self._until = time.monotonic() + min(int(age[1]) if age else 300, 24 * 60 * 60)
            return certs


def verify_id_token(
    token: str, *, client_id: str, nonce: str, certs: Callable[[], Mapping[str, str]]
) -> GoogleAccount:
    """Signature, audience, issuer, expiry, a verified email and this browser's nonce."""
    from google.auth import jwt as google_jwt

    if not token or len(token) > 4096 or not nonce:
        raise AccessError("invalid_sign_in")
    try:
        claims = google_jwt.decode(
            token, certs=dict(certs()), audience=client_id, clock_skew_in_seconds=60
        )
    except AccessError:
        raise
    except Exception:
        # Library errors can quote token content; only a fixed code crosses this boundary.
        raise AccessError("invalid_sign_in") from None
    subject = claims.get("sub")
    if (
        claims.get("iss") not in ISSUERS
        or claims.get("email_verified") is not True
        or not isinstance(subject, str)
        or not subject
        or not hmac.compare_digest(str(claims.get("nonce", "")).encode(), nonce.encode())
    ):
        raise AccessError("invalid_sign_in")
    email = claims.get("email")
    try:
        masked = mask_email(email) if isinstance(email, str) else None
    except MailError:
        masked = None
    digest = hashlib.sha256(("google:" + subject).encode()).hexdigest()
    return GoogleAccount(subject_sha256=digest, email_masked=masked)
