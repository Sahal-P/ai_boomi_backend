import base64
from collections.abc import Callable, Iterator
from datetime import timedelta
from uuid import UUID

from finboy.core.clock import today_ist
from finboy.services.ingestion.pipeline import InboundMessage
from finboy.services.mail.google import GoogleClient
from finboy.services.mail.security import MailError

MAX_PAGES = 10
MAX_CANDIDATES = 500
MAX_MESSAGE_BYTES = 2 * 1024 * 1024


def financial_query() -> str:
    after = (today_ist() - timedelta(days=30)).strftime("%Y/%m/%d")
    return (
        f"after:{after} -category:social -category:promotions "
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
) -> Iterator[InboundMessage]:
    token = google.refresh(refresh_token)

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

    page_token = ""
    checked = candidates = 0
    seen: set[str] = set()
    for _ in range(MAX_PAGES):
        params: dict[str, str | int] = {"q": financial_query(), "maxResults": 100}
        if page_token:
            params["pageToken"] = page_token
        page = get("messages", params)
        entries = page.get("messages", [])
        if not isinstance(entries, list):
            raise MailError("gmail_unavailable")
        for entry in entries:
            if not isinstance(entry, dict):
                raise MailError("gmail_unavailable")
            message_id = entry.get("id")
            if not isinstance(message_id, str) or not message_id.isalnum():
                raise MailError("gmail_unavailable")
            if message_id in seen:
                continue
            seen.add(message_id)
            metadata = get(f"messages/{message_id}", {"format": "metadata"})
            checked += 1
            if not isinstance(metadata.get("payload"), dict):
                raise MailError("gmail_unavailable")
            candidates += 1
            on_scan(checked, candidates)
            raw_value = get(f"messages/{message_id}", {"format": "raw"}).get("raw")
            if not isinstance(raw_value, str) or len(raw_value) > MAX_MESSAGE_BYTES * 4 // 3 + 8:
                raise MailError("gmail_unavailable")
            try:
                raw = base64.b64decode(
                    raw_value + "=" * (-len(raw_value) % 4), altchars=b"-_", validate=True
                )
            except ValueError:
                raise MailError("gmail_unavailable") from None
            if len(raw) > MAX_MESSAGE_BYTES:
                raise MailError("gmail_unavailable")
            yield InboundMessage(
                source="gmail",
                provider_message_id=message_id,
                raw_rfc822=raw,
                mail_connection_id=connection_id,
            )
            if candidates >= MAX_CANDIDATES:
                return
        next_page = page.get("nextPageToken")
        if not next_page:
            return
        if not isinstance(next_page, str):
            raise MailError("gmail_unavailable")
        page_token = next_page
