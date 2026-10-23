import hashlib
import json

import httpx
import pytest
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.meta import (
    InvalidMedia,
    MetaClient,
    MetaUnavailable,
    SendUnknown,
    safe_media_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://lookaside.fbsbx.com/audio",
        "https://localhost/audio",
        "https://lookaside.fbsbx.com.evil.test/audio",
        "https://user@lookaside.fbsbx.com/a",
        "https://lookaside.fbsbx.com:444/a",
        "https://127.0.0.1/a",
        "https://lookaside.fbsbx.com/a#fragment",
    ],
)
def test_no_arbitrary_media_urls(url: str) -> None:
    assert not safe_media_url(url)


def test_authenticated_media_and_upload(config: ChannelConfig) -> None:
    audio = b"synthetic bounded audio"
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["authorization"] == "Bearer synthetic-access"
        if request.method == "POST":
            assert b"audio/mpeg" in request.content
            return httpx.Response(200, json={"id": "12345"})
        if request.url.host == "graph.facebook.com":
            assert request.url.params["phone_number_id"] == config.phone_id
            return httpx.Response(
                200,
                json={
                    "id": "1234",
                    "url": "https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=1234",
                    "mime_type": "audio/ogg",
                    "file_size": len(audio),
                    "sha256": hashlib.sha256(audio).hexdigest(),
                },
            )
        return httpx.Response(200, content=audio, headers={"content-type": "audio/ogg"})

    client = MetaClient(config, transport=httpx.MockTransport(handler))
    try:
        result = client.download_audio("1234", "audio/ogg; codecs=opus")
        assert result.data == audio and "synthetic bounded audio" not in repr(result)
        assert client.upload_audio(b"synthetic mp3") == "12345"
        assert len(seen) == 3
    finally:
        client.close()


@pytest.mark.parametrize(
    "fault",
    [
        "expired",
        "oversize",
        "bad_mime",
        "redirect",
        "wrong_hash",
        "wrong_host",
        "wrong_id",
        "auth",
        "quota",
    ],
)
def test_media_failures_are_bounded(config: ChannelConfig, fault: str) -> None:
    seen = []
    audio = b"synthetic"

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.host == "graph.facebook.com":
            if fault in {"expired", "auth", "quota"}:
                return httpx.Response(
                    {"expired": 404, "auth": 401, "quota": 429}[fault],
                    json={"error": "private provider error"},
                )
            return httpx.Response(
                200,
                json={
                    "id": "999" if fault == "wrong_id" else "1234",
                    "url": "https://evil.test/a"
                    if fault == "wrong_host"
                    else "https://lookaside.fbsbx.com/a",
                    "mime_type": "image/png" if fault == "bad_mime" else "audio/ogg",
                    "file_size": 4 * 1024 * 1024 if fault == "oversize" else len(audio),
                    "sha256": "0" * 64
                    if fault == "wrong_hash"
                    else hashlib.sha256(audio).hexdigest(),
                },
            )
        if fault == "redirect":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})
        return httpx.Response(200, content=audio, headers={"content-type": "audio/ogg"})

    client = MetaClient(config, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(MetaUnavailable) as error:
            client.download_audio("1234", "audio/ogg")
        assert "private" not in str(error.value)
        assert all(r.url.host in {"graph.facebook.com", "lookaside.fbsbx.com"} for r in seen)
    finally:
        client.close()


@pytest.mark.parametrize("fault", ["timeout", "server", "malformed", "quota", "auth"])
def test_send_has_no_automatic_retry_and_uncertain_outcomes(
    config: ChannelConfig, fault: str
) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert json.loads(request.content)["text"]["preview_url"] is False
        if fault == "timeout":
            raise httpx.ReadTimeout("private text and token")
        if fault == "malformed":
            return httpx.Response(200, json={"messages": []})
        return httpx.Response({"server": 503, "quota": 429, "auth": 401}[fault])

    client = MetaClient(config, transport=httpx.MockTransport(handler))
    try:
        expected = SendUnknown if fault in {"timeout", "server", "malformed"} else MetaUnavailable
        with pytest.raises(expected):
            client.send("919000000001", text="synthetic answer")
        assert len(calls) == 1
    finally:
        client.close()


def test_unknown_recipient_never_reaches_meta(config: ChannelConfig) -> None:
    transport = httpx.MockTransport(lambda _: pytest.fail("not authorized"))
    client = MetaClient(config, transport=transport)
    try:
        with pytest.raises(MetaUnavailable):
            client.send("919000000099", text="answer")
        with pytest.raises(InvalidMedia):
            client.download_audio("https://evil.test/a", "audio/ogg")
    finally:
        client.close()
