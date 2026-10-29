"""Resend transport with bounded idempotent retries and redacted operational logging."""

import logging
import re
import time
from uuid import UUID

import httpx
from fastapi import BackgroundTasks

from finboy.core.config import Settings
from finboy.services.outbound_email.templates import Message

logger = logging.getLogger(__name__)
_ENDPOINT = "https://api.resend.com/emails"
_RETRYABLE = {429, 500, 502, 503, 504}


class EmailUnavailable(Exception):
    """Fixed error; never contains message, recipient, provider response, or credentials."""


def send(
    settings: Settings,
    recipient: str,
    message: Message,
    request_id: UUID,
    *,
    transport: httpx.BaseTransport | None = None,
) -> None:
    """Submit one message, reusing its idempotency key for every bounded retry."""
    if not settings.resend_api_key or not settings.resend_api_key.get_secret_value():
        raise EmailUnavailable("email is not configured")
    if len(recipient) > 254 or not re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}", recipient
    ):
        raise ValueError("invalid recipient")
    payload = {
        "from": "FinBoy <noreply@finboy.io>",
        "to": [recipient],
        "reply_to": "support@finboy.io",
        "subject": message.subject,
        "text": message.text,
        "html": message.html,
    }
    headers = {
        "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
        "Idempotency-Key": f"finboy/{request_id}",
    }
    with httpx.Client(
        timeout=10, follow_redirects=False, trust_env=False, transport=transport
    ) as client:
        for attempt in range(3):
            try:
                response = client.post(_ENDPOINT, json=payload, headers=headers)
                if 200 <= response.status_code < 300:
                    logger.info(
                        "email.accepted", extra={"provider": "resend", "outcome": "accepted"}
                    )
                    return
                retryable = response.status_code in _RETRYABLE
            except httpx.TransportError:
                retryable = True
            if not retryable or attempt == 2:
                break
            time.sleep(0.25 * (2**attempt))
    logger.warning("email.failed", extra={"provider": "resend", "outcome": "failed"})
    raise EmailUnavailable("email provider unavailable") from None


def _background_send(
    settings: Settings, recipient: str, message: Message, request_id: UUID
) -> None:
    try:
        send(settings, recipient, message, request_id)
    except EmailUnavailable, ValueError:
        # BackgroundTasks runs after the response; never log exception text or message content.
        logger.warning("email.background_failed", extra={"provider": "resend", "outcome": "failed"})


def enqueue(
    background: BackgroundTasks,
    settings: Settings,
    recipient: str,
    message: Message,
    request_id: UUID,
) -> None:
    """Schedule a best-effort in-process send; callers must handle process loss."""
    background.add_task(_background_send, settings, recipient, message, request_id)
