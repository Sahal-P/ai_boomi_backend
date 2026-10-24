"""Bounded Gmail scans with explicit coverage and encrypted continuation upstream."""

import base64
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from finboy.core.clock import today_ist
from finboy.db.models.ledger import EmailSource
from finboy.services.ingestion.pipeline import InboundMessage
from finboy.services.mail.google import GoogleClient
from finboy.services.mail.security import MailError

MAX_PAGES = 10
MAX_CANDIDATES = 500
MAX_MESSAGE_BYTES = 2 * 1024 * 1024


def financial_query(start: date | None = None, end: date | None = None) -> str:
    start = start or today_ist() - timedelta(days=30)
    # Epoch boundaries are exact IST midnight; Gmail date strings otherwise use PST.
    from datetime import datetime, time

    from finboy.core.clock import IST

    after = int(datetime.combine(start, time.min, IST).timestamp())
    before = int(
        datetime.combine((end or today_ist()) + timedelta(days=1), time.min, IST).timestamp()
    )
    return (
        f"after:{after} before:{before} -category:social -category:promotions "
        "{debited credited transaction payment receipt invoice refund salary EMI bill UPI "
        "from:hdfcbank.net from:hdfcbank.com from:icicibank.com from:sbi.co.in "
        "from:axisbank.com from:amazon.in from:swiggy.in from:zomato.com}"
    )


def fetch_messages(
    google: GoogleClient,
    *,
    refresh_token: str,
    connection_id: UUID,
    on_scan: Callable[[int, int], None],
    ensure_active: Callable[[], None],
    source_ids: list[str] | None = None,
    factory: sessionmaker[Session] | None = None,
    on_coverage: Callable[[date, date, bool, str | None], None] | None = None,
    page_token: str = "",
    window_start: date | None = None,
    window_end: date | None = None,
) -> Iterator[InboundMessage]:
    token = google.refresh(refresh_token)
    start, end = window_start or today_ist() - timedelta(days=30), window_end or today_ist()

    def get(path: str, params: dict[str, str | int] | None = None) -> dict:
        nonlocal token
        ensure_active()
        try:
            return google.get(path, token, params)
        except MailError as exc:
            if exc.code != "reconnect_required":
                raise
            token = google.refresh(refresh_token)
            return google.get(path, token, params)

    def raw_message(message_id: str) -> InboundMessage:
        try:
            metadata = get(f"messages/{message_id}", {"format": "metadata"})
            if not isinstance(metadata.get("payload"), dict):
                raise MailError("gmail_unavailable")
            value = get(f"messages/{message_id}", {"format": "raw"}).get("raw")
            if not isinstance(value, str) or len(value) > MAX_MESSAGE_BYTES * 4 // 3 + 8:
                raise MailError("gmail_unavailable")
            raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
            if len(raw) > MAX_MESSAGE_BYTES:
                raise MailError("gmail_unavailable")
            return InboundMessage(
                source="gmail",
                provider_message_id=message_id,
                raw_rfc822=raw,
                mail_connection_id=connection_id,
            )
        except MailError as exc:
            if exc.code in {"reconnect_required", "import_cancelled", "connection_inactive"}:
                raise
        except ValueError:
            pass
        return InboundMessage(
            source="gmail",
            provider_message_id=message_id,
            raw_rfc822=b"",
            mail_connection_id=connection_id,
            failure_reason="message_unavailable",
        )

    if source_ids:
        if factory is None:
            raise MailError("import_failed")
        with factory() as session:
            rows = list(
                session.scalars(
                    select(EmailSource).where(
                        EmailSource.id.in_([UUID(key) for key in source_ids]),
                        EmailSource.mail_connection_id == connection_id,
                        EmailSource.source == "gmail",
                        EmailSource.processing_status == "failed",
                    )
                )
            )
        for index, row in enumerate(rows, 1):
            ensure_active()
            on_scan(index, index)
            yield raw_message(row.provider_message_id)
        return
    if on_coverage:
        on_coverage(start, end, False, None)
    seen: set[str] = set()
    checked = candidates = 0
    for page_index in range(MAX_PAGES):
        params: dict[str, str | int] = {
            "q": financial_query(start, end),
            "maxResults": min(100, MAX_CANDIDATES - candidates),
        }
        if page_token:
            params["pageToken"] = page_token
        page = get("messages", params)
        entries = page.get("messages", [])
        next_page = page.get("nextPageToken")
        if (
            not isinstance(entries, list)
            or next_page is not None
            and (not isinstance(next_page, str) or len(next_page) > 4096)
        ):
            raise MailError("gmail_unavailable")
        for entry in entries:
            if candidates >= MAX_CANDIDATES:
                if on_coverage:
                    on_coverage(start, end, True, page_token or None)
                return
            if not isinstance(entry, dict):
                raise MailError("gmail_unavailable")
            message_id = entry.get("id")
            if not isinstance(message_id, str) or not message_id.isalnum():
                raise MailError("gmail_unavailable")
            if message_id in seen:
                continue
            seen.add(message_id)
            checked += 1
            candidates += 1
            on_scan(checked, candidates)
            yield raw_message(message_id)
        if not next_page:
            if on_coverage:
                on_coverage(start, end, False, None)
            return
        if candidates >= MAX_CANDIDATES or page_index == MAX_PAGES - 1:
            if on_coverage:
                on_coverage(start, end, True, next_page)
            return
        page_token = next_page
