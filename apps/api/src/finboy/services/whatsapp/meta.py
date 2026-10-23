"""Bounded official Graph transport; no automatic outbound retries."""

import hashlib
import hmac
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field, ValidationError

from finboy.services.whatsapp.config import ChannelConfig

AUDIO_TYPES = {"audio/aac", "audio/amr", "audio/mpeg", "audio/mp4", "audio/ogg"}
MEDIA_HOSTS = {"lookaside.fbsbx.com", "mmg.whatsapp.net"}
MAX_AUDIO_BYTES = 3 * 1024 * 1024


class MetaUnavailable(Exception):
    """A fixed failure outcome; never includes provider body or exception text."""


class SendUnknown(MetaUnavailable):
    """Request may have reached Meta. Require a new inbound message; never retry."""


class InvalidMedia(MetaUnavailable):
    pass


class MediaInfo(BaseModel):
    id: str = Field(pattern=r"^[0-9]{1,64}$")
    url: str = Field(max_length=4096, repr=False)
    mime_type: str = Field(max_length=100)
    file_size: int = Field(gt=0, le=MAX_AUDIO_BYTES, strict=True)
    sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")


@dataclass(frozen=True)
class DownloadedAudio:
    data: bytes = field(repr=False)
    content_type: str


def safe_media_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname in MEDIA_HOSTS
            and parsed.port in {None, 443}
            and parsed.username is None
            and parsed.password is None
            and not parsed.fragment
        )
    except ValueError:
        return False


class MetaClient:
    def __init__(
        self, config: ChannelConfig, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.config = config
        self.base = f"https://graph.facebook.com/{config.version}"
        self.client = httpx.Client(
            headers={
                "Authorization": f"Bearer {config.access_token}",
                "Accept-Encoding": "identity",
            },
            timeout=config.timeout,
            follow_redirects=False,
            transport=transport,
            trust_env=False,
        )

    def close(self) -> None:
        self.client.close()

    def _read(
        self, method: str, url: str, *, limit: int = 32768, **kwargs: object
    ) -> tuple[bytes, str]:
        deadline = time.monotonic() + self.config.timeout
        try:
            with self.client.stream(method, url, **kwargs) as response:
                if response.status_code >= 300:
                    raise MetaUnavailable
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise InvalidMedia
                length = response.headers.get("content-length")
                if length and (not length.isdigit() or int(length) > limit):
                    raise InvalidMedia
                chunks = bytearray()
                for chunk in response.iter_bytes():
                    if len(chunks) + len(chunk) > limit or time.monotonic() > deadline:
                        raise InvalidMedia
                    chunks.extend(chunk)
                return bytes(chunks), response.headers.get("content-type", "").split(";")[
                    0
                ].strip().lower()
        except httpx.HTTPError:
            raise MetaUnavailable from None

    def download_audio(self, media_id: str, webhook_mime: str) -> DownloadedAudio:
        if (
            not re.fullmatch(r"[0-9]{1,64}", media_id)
            or webhook_mime.split(";")[0] not in AUDIO_TYPES
        ):
            raise InvalidMedia
        try:
            raw, _ = self._read(
                "GET", f"{self.base}/{media_id}", params={"phone_number_id": self.config.phone_id}
            )
            info = MediaInfo.model_validate_json(raw)
            mime = info.mime_type.split(";")[0].strip().lower()
            if info.id != media_id or mime not in AUDIO_TYPES or not safe_media_url(info.url):
                raise InvalidMedia
            if mime != webhook_mime.split(";")[0]:
                raise InvalidMedia
            data, content_type = self._read("GET", info.url, limit=MAX_AUDIO_BYTES)
            if content_type != mime or len(data) != info.file_size:
                raise InvalidMedia
            if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), info.sha256.lower()):
                raise InvalidMedia
            return DownloadedAudio(data, mime)
        except ValidationError:
            raise InvalidMedia from None

    def upload_audio(self, audio: bytes) -> str:
        if not audio or len(audio) > MAX_AUDIO_BYTES:
            raise InvalidMedia
        raw, _ = self._read(
            "POST",
            f"{self.base}/{self.config.phone_id}/media",
            data={"messaging_product": "whatsapp", "type": "audio/mpeg"},
            files={"file": ("reply.mp3", audio, "audio/mpeg")},
        )
        try:
            media_id = MediaId.model_validate_json(raw).id
        except ValidationError:
            raise MetaUnavailable from None
        return media_id

    def send(self, recipient: str, *, text: str | None = None, media_id: str | None = None) -> str:
        if recipient not in self.config.allowlist:
            raise MetaUnavailable
        if (text is None) == (media_id is None):
            raise MetaUnavailable
        payload: dict[str, object] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": "+" + recipient,
        }
        if text is not None:
            if not 1 <= len(text) <= 4096:
                raise MetaUnavailable
            payload.update(type="text", text={"body": text, "preview_url": False})
        else:
            payload.update(type="audio", audio={"id": media_id})
        # Unlike read/upload failures, a transport/5xx failure after send may be ambiguous.
        try:
            with self.client.stream(
                "POST", f"{self.base}/{self.config.phone_id}/messages", json=payload
            ) as response:
                if response.status_code >= 500 or 300 <= response.status_code < 400:
                    raise SendUnknown
                if response.status_code >= 400:
                    raise MetaUnavailable
                body = bytearray()
                deadline = time.monotonic() + self.config.timeout
                for chunk in response.iter_bytes():
                    if len(body) + len(chunk) > 32768 or time.monotonic() > deadline:
                        raise SendUnknown
                    body.extend(chunk)
                result = SendResult.model_validate_json(body)
                return result.messages[0].id
        except httpx.HTTPError, ValidationError:
            raise SendUnknown from None


class MediaId(BaseModel):
    id: str = Field(pattern=r"^[0-9]{1,64}$")


class MessageId(BaseModel):
    id: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_.=+/-]+$")


class SendResult(BaseModel):
    messages: list[MessageId] = Field(min_length=1, max_length=1)
