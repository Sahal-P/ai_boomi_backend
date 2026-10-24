import base64
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from finboy.services.mail.fetch import fetch_messages, financial_query
from finboy.services.mail.google import GoogleClient
from finboy.services.mail.security import MailError
from finboy.services.mail.seed_demo_inbox import seed_messages


def test_fetch_paginates_refreshes_and_counts(eml, monkeypatch):
    from datetime import date

    monkeypatch.setattr("finboy.services.mail.fetch.today_ist", lambda: date(2026, 10, 28))
    calls, scans, waits = [], [], []
    token_calls = 0
    retries = 0

    def handler(request):
        nonlocal token_calls, retries
        calls.append(request)
        if request.url.path == "/token":
            token_calls += 1
            return httpx.Response(200, json={"access_token": f"access{token_calls}"})
        if request.url.path.endswith("/messages"):
            if not request.url.params.get("pageToken"):
                retries += 1
                if retries < 3:
                    return httpx.Response(429 if retries == 1 else 503)
                return httpx.Response(
                    200, json={"messages": [{"id": "abc"}], "nextPageToken": "page2"}
                )
            return httpx.Response(200, json={"messages": [{"id": "def"}]})
        if request.headers["authorization"] == "Bearer access1":
            return httpx.Response(401)
        if request.url.params["format"] == "metadata":
            return httpx.Response(200, json={"payload": {"headers": []}})
        return httpx.Response(200, json={"raw": base64.urlsafe_b64encode(eml).decode()})

    google = GoogleClient(
        "client",
        "secret",
        "http://localhost",
        sleep=waits.append,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    messages = list(
        fetch_messages(
            google,
            refresh_token="refresh",
            connection_id=uuid4(),
            on_scan=lambda *counts: scans.append(counts),
            ensure_active=lambda: None,
        )
    )
    assert [message.provider_message_id for message in messages] == ["abc", "def"]
    assert messages[0].raw_rfc822 == eml
    assert scans == [(1, 1), (2, 2)]
    assert waits == [1, 2]
    assert token_calls == 2
    assert "after:1790533800 before:1793212200" in financial_query()
    assert "-category:social -category:promotions" in financial_query()
    assert all("refresh" not in str(call.url) for call in calls)
    google.close()


def test_invalid_grant_is_fixed():
    google = GoogleClient(
        "id",
        "secret",
        "http://localhost",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    400, json={"error": "invalid_grant", "error_description": "SENSITIVE_DETAILS"}
                )
            )
        ),
    )
    with pytest.raises(MailError, match="^reconnect_required$"):
        google.refresh("SENSITIVE_REFRESH")
    google.close()


def test_revoke_posts_body_and_accepts_already_revoked():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(400, json={"error": "invalid_token"})

    google = GoogleClient(
        "id",
        "secret",
        "http://localhost",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    google.revoke("SENSITIVE_REFRESH")
    assert calls[0].method == "POST"
    assert calls[0].content == b"token=SENSITIVE_REFRESH"
    assert "SENSITIVE_REFRESH" not in str(calls[0].url)
    google.close()


def test_fetch_caps_candidates(eml, monkeypatch):
    monkeypatch.setattr("finboy.services.mail.fetch.MAX_CANDIDATES", 2)
    google = GoogleClient(
        "id",
        "secret",
        "http://localhost",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={"access_token": "token"}
                    if request.url.path == "/token"
                    else {
                        "messages": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
                        "nextPageToken": "again",
                    }
                    if request.url.path.endswith("/messages")
                    else {"payload": {}}
                    if request.url.params.get("format") == "metadata"
                    else {"raw": base64.urlsafe_b64encode(eml).decode()},
                )
            )
        ),
    )
    assert (
        len(
            list(
                fetch_messages(
                    google,
                    refresh_token="token",
                    connection_id=uuid4(),
                    on_scan=lambda *_: None,
                    ensure_active=lambda: None,
                )
            )
        )
        == 2
    )
    google.close()


def test_seed_is_insert_only_and_idempotent(tmp_path: Path, eml):
    for number in range(3):
        (tmp_path / f"{number}.eml").write_bytes(eml.replace(b"<one@", f"<{number}@".encode()))
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"id": "synthetic"})

    google = GoogleClient(
        "id",
        "secret",
        "http://localhost",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    manifest = tmp_path / "manifest.json"
    kwargs = {"directory": tmp_path, "manifest_path": manifest, "mailbox_label": "demo"}
    assert seed_messages(google, "SENSITIVE_ACCESS", **kwargs) == (3, 0)
    assert seed_messages(google, "SENSITIVE_ACCESS", **kwargs) == (0, 3)
    assert all(call.method == "POST" for call in calls)
    assert all(call.url.params["internalDateSource"] == "dateHeader" for call in calls)
    assert "SENSITIVE_ACCESS" not in manifest.read_text()
    assert "example.test" not in manifest.read_text()
    assert manifest.stat().st_mode & 0o777 == 0o600
    google.close()
