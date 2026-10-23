"""Mockable HTTP adapters. No request/response bodies, secrets, or provider errors logged."""

import base64
import binascii
import re
from html import escape

import httpx
from pydantic import BaseModel, Field, ValidationError

from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import Language
from finboy.services.speech.media import MAX_PROVIDER_AUDIO_BYTES, pcm_to_wav

MAX_JSON_BYTES = 18 * 1024 * 1024


def provider_client(settings: Settings) -> httpx.Client:
    # Retry connection establishment only; never repeat a potentially processed synthesis POST.
    return httpx.Client(
        timeout=settings.speech_timeout_seconds,
        follow_redirects=False,
        transport=httpx.HTTPTransport(retries=settings.provider_max_retries),
    )


def bounded_request(
    client: httpx.Client, method: str, url: str, *, limit: int = MAX_JSON_BYTES, **kwargs: object
) -> bytes:
    with client.stream(method, url, **kwargs) as response:
        if not response.is_success:
            raise ProviderUnavailable("speech_unavailable")
        output = bytearray()
        for part in response.iter_bytes():
            if len(output) + len(part) > limit:
                raise ProviderUnavailable("speech_unavailable")
            output.extend(part)
        return bytes(output)


def decode_base64(value: str) -> bytes:
    if len(value) > MAX_JSON_BYTES:
        raise ProviderUnavailable("speech_unavailable")
    try:
        data = base64.b64decode(re.sub(r"[ \t\r\n]", "", value), validate=True)
    except ValueError, binascii.Error:
        raise ProviderUnavailable("speech_unavailable") from None
    if not data or len(data) > MAX_PROVIDER_AUDIO_BYTES:
        raise ProviderUnavailable("speech_unavailable")
    return data


class GeminiAudio(BaseModel):
    type: str
    data: str | None = Field(default=None, repr=False)
    mime_type: str | None = None


class GeminiStep(BaseModel):
    type: str
    content: list[GeminiAudio] = Field(default_factory=list)


class GeminiResult(BaseModel):
    status: str | None = None
    steps: list[GeminiStep]


def gemini_synthesize(text: str, settings: Settings) -> tuple[bytes, str]:
    if (
        not settings.gemini_api_key
        or not settings.gemini_tts_model
        or not settings.gemini_tts_voice
    ):
        raise ProviderUnavailable("configuration_missing")
    # Current documented interactions schema; no automatic fallback to an older/different model.
    if settings.gemini_tts_model not in {"gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"}:
        raise ProviderUnavailable("configuration_missing")
    with provider_client(settings) as client:
        raw = bounded_request(
            client,
            "POST",
            str(settings.gemini_tts_base_url).rstrip("/") + "/interactions",
            headers={"x-goog-api-key": settings.gemini_api_key.get_secret_value()},
            json={
                "model": settings.gemini_tts_model,
                "store": False,
                "input": [
                    {
                        "type": "user_input",
                        "content": [
                            {
                                "type": "text",
                                "text": text,
                                "annotations": [
                                    {
                                        "type": "speech_metadata",
                                        "style": "Clear Malayalam, measured pace.",
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "response_format": {"type": "audio"},
                "generation_config": {"speech_config": [{"voice": settings.gemini_tts_voice}]},
            },
        )
    result = GeminiResult.model_validate_json(raw)
    blocks = [
        b
        for step in result.steps
        if step.type == "model_output"
        for b in step.content
        if b.type == "audio" and b.data
    ]
    if len(blocks) != 1:
        raise ProviderUnavailable("speech_unavailable")
    block = blocks[0]
    data = decode_base64(block.data)
    mime = block.mime_type or ""
    if mime == "audio/wav":
        return data, mime
    # Raw PCM requires explicit 16-bit rate metadata; do not guess endianness/rate.
    match = re.fullmatch(r"audio/L16;codec=pcm;rate=(\d+)", mime, flags=re.I)
    if match:
        return pcm_to_wav(data, int(match[1])), "audio/wav"
    raise ProviderUnavailable("speech_unavailable")


class ResembleResult(BaseModel):
    success: bool
    audio_content: str = Field(repr=False)
    output_format: str


def resemble_synthesize(text: str, language: Language, settings: Settings) -> tuple[bytes, str]:
    """Transient Ultra synthesis, explicitly approved by the human on 24 October."""
    voice = settings.resemble_voice_uuid_hi if language == "hi" else settings.resemble_voice_uuid_en
    if (
        not settings.resemble_api_key
        or not voice
        or settings.resemble_tts_model != "resemble-ultra"
    ):
        raise ProviderUnavailable("configuration_missing")
    # The configured stock voice/model must be verified at setup; model is not a request field.
    with provider_client(settings) as client:
        raw = bounded_request(
            client,
            "POST",
            str(settings.resemble_tts_base_url).rstrip("/") + "/synthesize",
            headers={"Authorization": "Bearer " + settings.resemble_api_key.get_secret_value()},
            json={"voice_uuid": voice, "data": escape(text, quote=False), "output_format": "mp3"},
        )
    # Omit project_uuid/title: intentionally creating stored clips is never necessary.
    result = ResembleResult.model_validate_json(raw)
    if not result.success or result.output_format != "mp3":
        raise ProviderUnavailable("speech_unavailable")
    return decode_base64(result.audio_content), "audio/mpeg"


PROVIDER_ERRORS = (httpx.HTTPError, ValidationError, ValueError, KeyError, TypeError)
