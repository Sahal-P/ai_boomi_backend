import hashlib
import hmac
import json
from unittest.mock import MagicMock

import pytest
from finboy.api.v1 import whatsapp as routes
from finboy.core.config import Settings
from finboy.main import create_app
from finboy.services.whatsapp.config import ChannelConfig, ChannelUnavailable, channel_config
from finboy.services.whatsapp.events import InvalidWebhook, parse_events, verify_signature
from httpx import ASGITransport, AsyncClient

from .conftest import payload


def signed(raw: bytes, config: ChannelConfig) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": "sha256="
        + hmac.new(config.app_secret.encode(), raw, hashlib.sha256).hexdigest(),
    }


@pytest.mark.parametrize(
    "text",
    [
        "Food this month?",
        "इस महीने खाने पर कितना खर्च हुआ?",
        "ഈ മാസം ഭക്ഷണത്തിന് എത്ര?",
        "khane pe kitna?",
        "ee masam foodinu ethra poyi?",
    ],
)
def test_language_input_is_passed_without_channel_reasoning(
    config: ChannelConfig, text: str
) -> None:
    raw = json.dumps(payload(text=text)).encode()
    questions, statuses = parse_events(raw, config)
    assert questions[0].text == text
    assert not statuses
    assert text not in repr(questions)
    assert verify_signature(raw, signed(raw, config)["X-Hub-Signature-256"], config)
    assert not verify_signature(raw + b" ", signed(raw, config)["X-Hub-Signature-256"], config)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(object="other"),
        lambda d: d["entry"][0].update(id="wrong"),
        lambda d: d["entry"][0]["changes"][0]["value"]["metadata"].update(phone_number_id="wrong"),
        lambda d: d["entry"][0]["changes"][0]["value"]["messages"][0].update(
            timestamp="999999999999"
        ),
    ],
)
def test_context_validation(config: ChannelConfig, mutate) -> None:
    data = payload()
    mutate(data)
    with pytest.raises(InvalidWebhook):
        parse_events(json.dumps(data).encode(), config)


def test_image_messages_use_only_media_id_and_mime(config: ChannelConfig) -> None:
    questions, _ = parse_events(json.dumps(payload(kind="image")).encode(), config)
    assert len(questions) == 1
    image = questions[0]
    assert (image.kind, image.media_id, image.mime_type) == ("image", "5678", "image/jpeg")
    # The caption is never treated as a question, command or instruction.
    assert image.text == "" and image.command is None
    assert "ignore" not in repr(image) and "evil.test" not in repr(image)


@pytest.mark.parametrize("image", [{"id": "not-digits", "mime_type": "image/png"}, {"id": "1"}])
def test_malformed_image_messages_fail_closed(config: ChannelConfig, image: dict) -> None:
    data = payload(kind="image")
    data["entry"][0]["changes"][0]["value"]["messages"][0]["image"] = image
    with pytest.raises(InvalidWebhook):
        parse_events(json.dumps(data).encode(), config)


def test_status_only_and_unsupported_events(config: ChannelConfig) -> None:
    data = payload()
    value = data["entry"][0]["changes"][0]["value"]
    value["messages"] = [
        {"type": kind, kind: {"id": "private"}} for kind in ("sticker", "video", "document")
    ]
    value["statuses"] = [
        {"id": "wamid.synthetic", "status": "delivered", "recipient_id": "919000000001"}
    ]
    questions, statuses = parse_events(json.dumps(data).encode(), config)
    assert not questions and statuses[0].status == "delivered"


@pytest.mark.parametrize(
    "override",
    [
        {"whatsapp_enabled": False},
        {"whatsapp_app_id": "another-app"},
        {"whatsapp_sender_allowlist_json": "{}"},
        {
            "whatsapp_sender_allowlist_json": (
                '{"919000000001":"00000000-0000-0000-0000-000000000002"}'
            )
        },
        {"whatsapp_graph_api_version": "../../attack"},
        {"whatsapp_access_token": None},
    ],
)
def test_configuration_fails_closed(wa_settings: Settings, override: dict) -> None:
    from pydantic import SecretStr

    if isinstance(override.get("whatsapp_sender_allowlist_json"), str):
        override["whatsapp_sender_allowlist_json"] = SecretStr(
            override["whatsapp_sender_allowlist_json"]
        )
    with pytest.raises(ChannelUnavailable):
        channel_config(wa_settings.model_copy(update=override))


@pytest.mark.anyio
async def test_challenge_and_fixed_failures(wa_settings: Settings) -> None:
    app = create_app(wa_settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "synthetic-verify",
            "hub.challenge": "12345",
        }
        good = await client.get("/api/v1/whatsapp/webhook", params=params)
        assert good.status_code == 200 and good.text == "12345"
        for change in [
            {"hub.mode": "invalid"},
            {"hub.verify_token": "wrong"},
            {"hub.challenge": "x" * 129},
        ]:
            bad = await client.get("/api/v1/whatsapp/webhook", params={**params, **change})
            assert bad.status_code == 403
            assert "synthetic-verify" not in bad.text
        duplicate = await client.get(
            "/api/v1/whatsapp/webhook", params=[*params.items(), ("hub.challenge", "123")]
        )
        assert duplicate.status_code == 403


@pytest.mark.anyio
async def test_signature_before_parse_and_body_limits(
    wa_settings: Settings, config: ChannelConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    parse = MagicMock(side_effect=AssertionError("must not parse"))
    monkeypatch.setattr(routes, "parse_events", parse)
    app = create_app(wa_settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        invalid = await client.post(
            "/api/v1/whatsapp/webhook", content=b"not-json", headers=signed(b"other", config)
        )
        assert invalid.status_code == 403
        too_big = await client.post(
            "/api/v1/whatsapp/webhook",
            content=b"x" * (config.max_body + 1),
            headers=signed(b"x", config),
        )
        assert too_big.status_code == 413
        mime = await client.post(
            "/api/v1/whatsapp/webhook", content=b"x", headers={"content-type": "text/plain"}
        )
        assert mime.status_code == 415
        assert not parse.called


@pytest.mark.anyio
async def test_durable_admission_failure_returns_retryable_fixed_error(
    wa_settings: Settings, config: ChannelConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = MagicMock()
    monkeypatch.setattr(routes, "sessionmaker", factory)
    monkeypatch.setattr(
        routes, "admit", MagicMock(side_effect=RuntimeError("private question and credential"))
    )
    process = MagicMock()
    monkeypatch.setattr(routes, "process_question", process)
    app = create_app(wa_settings)
    raw = json.dumps(payload()).encode()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/whatsapp/webhook", content=raw, headers=signed(raw, config)
        )
    assert response.status_code == 503 and "private" not in response.text
    assert not process.called
