import json
import logging
from uuid import uuid4

import httpx
import pytest
from finboy.core.logging import JsonFormatter
from finboy.services.outbound_email import resend, templates
from pydantic import SecretStr


def test_send_retries_same_request_and_keeps_secrets_out_of_logs(settings, monkeypatch, caplog):
    settings.resend_api_key = SecretStr("secret-for-test")
    caplog.set_level(logging.INFO, logger="finboy.services.outbound_email.resend")
    calls = []
    monkeypatch.setattr(resend.time, "sleep", lambda _: None)

    def handler(request):
        calls.append(request)
        return httpx.Response(503 if len(calls) == 1 else 200, json={"id": "test"})

    message = templates.Message("Test", "private notification", "<p>private notification</p>")
    resend.send(
        settings, "person@example.test", message, uuid4(), transport=httpx.MockTransport(handler)
    )
    assert len(calls) == 2
    assert calls[0].headers["Idempotency-Key"] == calls[1].headers["Idempotency-Key"]
    payload = json.loads(calls[0].content)
    assert payload["from"] == "FinBoy <noreply@finboy.io>"
    assert payload["reply_to"] == "support@finboy.io"
    assert "private notification" in payload["text"]
    assert any(record.msg == "email.accepted" for record in caplog.records)
    for record in caplog.records:
        rendered = JsonFormatter().format(record)
        assert all(
            value not in rendered
            for value in ("secret-for-test", "person@example.test", "private notification")
        )


def test_failure_is_redacted_and_non_retryable(settings):
    settings.resend_api_key = SecretStr("secret-for-test")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(400, text="secret-for-test person@example.test 123456")

    with pytest.raises(resend.EmailUnavailable) as exc:
        resend.send(
            settings,
            "person@example.test",
            templates.Message("Test", "private notification", "<p>private notification</p>"),
            uuid4(),
            transport=httpx.MockTransport(handler),
        )
    assert len(calls) == 1
    assert str(exc.value) == "email provider unavailable"


def test_network_failure_retries_only_three_times(settings, monkeypatch):
    settings.resend_api_key = SecretStr("test-key")
    calls = []
    monkeypatch.setattr(resend.time, "sleep", lambda _: None)

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("sensitive details", request=request)

    with pytest.raises(resend.EmailUnavailable):
        resend.send(
            settings,
            "person@example.test",
            templates.Message("Test", "private notification", "<p>private notification</p>"),
            uuid4(),
            transport=httpx.MockTransport(handler),
        )
    assert len(calls) == 3
    assert len({request.headers["Idempotency-Key"] for request in calls}) == 1


def test_message_repr_hides_body():
    message = templates.Message("Test", "private content", "<p>private content</p>")
    assert "private content" not in repr(message)
