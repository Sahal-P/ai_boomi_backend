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
from finboy.services.whatsapp.events import BUTTON_ID

AUDIO_TYPES = {"audio/aac", "audio/amr", "audio/mpeg", "audio/mp4", "audio/ogg"}
IMAGE_TYPES = {"image/jpeg", "image/png"}
MEDIA_HOSTS = {"lookaside.fbsbx.com", "mmg.whatsapp.net"}
MAX_AUDIO_BYTES = 3 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
BUTTON_PATTERN = re.compile(BUTTON_ID)
TEMPLATE_NAME = re.compile(r"[a-z0-9_]{1,64}")


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
    # The per-kind limit is checked by the caller before any media bytes are read.
    file_size: int = Field(gt=0, le=MAX_IMAGE_BYTES, strict=True)
    sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")


@dataclass(frozen=True)
class DownloadedMedia:
    data: bytes = field(repr=False)
    content_type: str


@dataclass(frozen=True)
class Listing:
    """A list message's menu: the button that opens it, one section title and its rows."""

    button: str
    section: str
    rows: list[tuple[str, str]]  # (our opaque ID, title)


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
        # Self-serve numbers the caller matched to their own binding for this message.
        self.vouched: set[str] = set()

    def allow(self, recipient: str) -> None:
        """A self-serve household's own number, only after its binding was checked."""
        if re.fullmatch(r"[0-9]{7,20}", recipient):
            self.vouched.add(recipient)

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

    def download_audio(self, media_id: str, webhook_mime: str) -> DownloadedMedia:
        return self._download(media_id, webhook_mime, AUDIO_TYPES, MAX_AUDIO_BYTES)

    def download_image(self, media_id: str, webhook_mime: str) -> DownloadedMedia:
        return self._download(media_id, webhook_mime, IMAGE_TYPES, MAX_IMAGE_BYTES)

    def _download(
        self, media_id: str, webhook_mime: str, allowed: set[str], limit: int
    ) -> DownloadedMedia:
        webhook = webhook_mime.split(";")[0].strip().lower()
        if not re.fullmatch(r"[0-9]{1,64}", media_id) or webhook not in allowed:
            raise InvalidMedia
        try:
            raw, _ = self._read(
                "GET", f"{self.base}/{media_id}", params={"phone_number_id": self.config.phone_id}
            )
            info = MediaInfo.model_validate_json(raw)
            mime = info.mime_type.split(";")[0].strip().lower()
            if info.id != media_id or mime not in allowed or not safe_media_url(info.url):
                raise InvalidMedia
            if mime != webhook or info.file_size > limit:
                raise InvalidMedia
            data, content_type = self._read("GET", info.url, limit=limit)
            if content_type != mime or len(data) != info.file_size:
                raise InvalidMedia
            if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), info.sha256.lower()):
                raise InvalidMedia
            return DownloadedMedia(data, mime)
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
        if (text is None) == (media_id is None):
            raise MetaUnavailable
        if text is not None:
            if not 1 <= len(text) <= 4096:
                raise MetaUnavailable
            return self._send(
                recipient, {"type": "text", "text": {"body": text, "preview_url": False}}
            )
        return self._send(recipient, {"type": "audio", "audio": {"id": media_id}})

    def send_buttons(self, recipient: str, *, text: str, buttons: list[tuple[str, str]]) -> str:
        """Reply buttons only: at most 3 with titles of 20 characters or fewer and our own IDs."""
        if not 1 <= len(text) <= 1024 or not 1 <= len(buttons) <= 3:
            raise MetaUnavailable
        if len({key for key, _ in buttons}) != len(buttons) or any(
            not BUTTON_PATTERN.fullmatch(key) or not 1 <= len(title) <= 20 for key, title in buttons
        ):
            raise MetaUnavailable
        replies = [
            {"type": "reply", "reply": {"id": key, "title": title}} for key, title in buttons
        ]
        return self._send(
            recipient,
            {
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": text},
                    "action": {"buttons": replies},
                },
            },
        )

    def send_list(
        self,
        recipient: str,
        *,
        text: str,
        button: str,
        section: str,
        rows: list[tuple[str, str]],
    ) -> str:
        """A list message: at most 10 rows with titles of 24 characters or fewer and our IDs."""
        if (
            not 1 <= len(text) <= 1024
            or not 1 <= len(button) <= 20
            or not 1 <= len(section) <= 24
            or not 1 <= len(rows) <= 10
            or len({key for key, _ in rows}) != len(rows)
            or any(
                not BUTTON_PATTERN.fullmatch(key) or not 1 <= len(title) <= 24
                for key, title in rows
            )
        ):
            raise MetaUnavailable
        return self._send(
            recipient,
            {
                "type": "interactive",
                "interactive": {
                    "type": "list",
                    "body": {"text": text},
                    "action": {
                        "button": button,
                        "sections": [
                            {
                                "title": section,
                                "rows": [{"id": key, "title": title} for key, title in rows],
                            }
                        ],
                    },
                },
            },
        )

    def send_template(
        self,
        recipient: str,
        *,
        name: str,
        language: str,
        parameters: list[str],
        quick_replies: list[str],
    ) -> str:
        """An approved template (reminders, check-ins): text parameters plus our quick replies."""
        if (
            not TEMPLATE_NAME.fullmatch(name)
            or language not in {"hi", "en", "ml"}
            or len(parameters) > 10
            or len(quick_replies) > 3
            or any(not 1 <= len(item) <= 1024 or re.search(r"[\n\t]", item) for item in parameters)
            or any(not BUTTON_PATTERN.fullmatch(item) for item in quick_replies)
        ):
            raise MetaUnavailable
        components: list[dict[str, object]] = []
        if parameters:
            components.append(
                {"type": "body", "parameters": [{"type": "text", "text": p} for p in parameters]}
            )
        for index, payload in enumerate(quick_replies):
            components.append(
                {
                    "type": "button",
                    "sub_type": "quick_reply",
                    "index": str(index),
                    "parameters": [{"type": "payload", "payload": payload}],
                }
            )
        return self._send(
            recipient,
            {
                "type": "template",
                "template": {
                    "name": name,
                    "language": {"code": language},
                    "components": components,
                },
            },
        )

    def _send(self, recipient: str, message: dict[str, object]) -> str:
        if recipient not in self.config.allowlist and recipient not in self.vouched:
            raise MetaUnavailable
        payload: dict[str, object] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": "+" + recipient,
            **message,
        }
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
