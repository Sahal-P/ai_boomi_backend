"""Sign in by WhatsApp: one-time codes a person sends from their own WhatsApp.

The code is shown once to the browser that asked for it and kept only as an HMAC. A request is
bound to that browser's login nonce, lives ten minutes, needs a button tap in WhatsApp, and is
used once. Wrong browser, expired, declined or reused all fail closed.
"""

import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import quote
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.access import keyed_digest
from finboy.core.config import Settings
from finboy.db.models.accounts import LoginRequest

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O or 1/I to misread
LIFETIME = timedelta(minutes=10)
CODE = re.compile(
    r"^\s*(?:finboy\b[\s:,.-]*)?(?:(?:login|sign[\s-]?in)\s+code|लॉगिन\s+कोड|code|कोड)?"
    r"[\s:,.-]*([2-9a-hj-np-z]{4})[\s-]?([2-9a-hj-np-z]{4})\s*[.!]?\s*$",
    re.IGNORECASE,
)
State = Literal["pending", "confirmed", "declined", "used", "expired"]


@dataclass(frozen=True)
class Started:
    code: str
    link: str | None
    expires_at: datetime


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def new_code() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def read_code(text: str | None) -> str | None:
    """The code in a typed or pasted login message, normalised, or None for anything else."""
    if not text or len(text) > 120:
        return None
    match = CODE.match(text)
    return f"{match[1]}-{match[2]}".upper() if match else None


def code_digest(settings: Settings, code: str) -> str:
    return keyed_digest(settings, "login-code", code)


def nonce_digest(settings: Settings, nonce: str) -> str:
    return keyed_digest(settings, "login-nonce", nonce)


def device_label(user_agent: str) -> str:
    """A short, coarse label for the WhatsApp card ("Chrome · Android"); never stored raw."""
    agent = user_agent[:512]
    browser = next(
        (
            name
            for token, name in (
                ("Edg/", "Edge"),
                ("SamsungBrowser", "Samsung Internet"),
                ("Firefox/", "Firefox"),
                ("CriOS", "Chrome"),
                ("Chrome/", "Chrome"),
                ("Safari/", "Safari"),
            )
            if token in agent
        ),
        "a browser",
    )
    system = next(
        (
            name
            for token, name in (
                ("Android", "Android"),
                ("iPhone", "iPhone"),
                ("iPad", "iPad"),
                ("Windows", "Windows"),
                ("Mac OS X", "Mac"),
                ("Linux", "Linux"),
            )
            if token in agent
        ),
        None,
    )
    return f"{browser} · {system}" if system else browser


def message_link(settings: Settings, code: str) -> str | None:
    if not settings.whatsapp_public_number:
        return None
    return f"https://wa.me/{settings.whatsapp_public_number}?text=" + quote(
        f"FinBoy login code {code}"
    )


def start(
    session: Session,
    settings: Settings,
    *,
    nonce: str,
    device: str,
    purpose: Literal["sign_in", "link"] = "sign_in",
    user_id: UUID | None = None,
) -> Started:
    code = new_code()
    expires = datetime.now(UTC) + LIFETIME
    session.add(
        LoginRequest(
            id=uuid4(),
            code_digest=code_digest(settings, code),
            nonce_digest=nonce_digest(settings, nonce),
            purpose=purpose,
            state="pending",
            user_id=user_id if purpose == "link" else None,
            device=device[:40],
            expires_at=expires,
        )
    )
    session.commit()
    return Started(code=code, link=message_link(settings, code), expires_at=expires)


def latest(session: Session, settings: Settings, nonce: str) -> LoginRequest | None:
    """The newest attempt this browser started (it may have tapped the button twice)."""
    return session.scalar(
        select(LoginRequest)
        .where(LoginRequest.nonce_digest == nonce_digest(settings, nonce))
        .order_by(LoginRequest.created_at.desc())
        .limit(1)
    )


def state_of(request: LoginRequest | None) -> State:
    if request is None:
        return "expired"
    if request.state == "pending" and _aware(request.expires_at) <= datetime.now(UTC):
        return "expired"
    return request.state  # type: ignore[return-value]


def for_code(session: Session, settings: Settings, code: str) -> LoginRequest | None:
    """The open request behind a code sent on WhatsApp, locked for this decision."""
    request = session.scalar(
        select(LoginRequest)
        .where(LoginRequest.code_digest == code_digest(settings, code))
        .with_for_update()
    )
    if request is None or state_of(request) != "pending":
        return None
    return request


def confirm(request: LoginRequest, *, user_id: UUID, binding_id: UUID) -> None:
    request.state = "confirmed"
    request.user_id = user_id
    request.binding_id = binding_id
    request.confirmed_at = datetime.now(UTC)


def decline(request: LoginRequest) -> None:
    request.state = "declined"


def redeem(session: Session, settings: Settings, nonce: str) -> LoginRequest | None:
    """The browser that started a confirmed sign-in takes it, exactly once."""
    request = session.scalar(
        select(LoginRequest)
        .where(
            LoginRequest.nonce_digest == nonce_digest(settings, nonce),
            LoginRequest.state == "confirmed",
        )
        .order_by(LoginRequest.confirmed_at.desc())
        .limit(1)
        .with_for_update()
    )
    # A confirmed request can still be redeemed briefly after the code itself expired.
    if request is None or _aware(request.expires_at) + LIFETIME <= datetime.now(UTC):
        return None
    request.state = "used"
    request.used_at = datetime.now(UTC)
    return request
