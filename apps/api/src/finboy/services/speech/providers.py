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
from finboy.services.speech.media import MAX_PROVIDER_AUDIO_BYTES, SAMPLE_RATE, pcm_to_wav

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


class GroqSegment(BaseModel):
    no_speech_prob: float
    avg_logprob: float


class GroqTranscription(BaseModel):
    text: str = Field(max_length=2000, repr=False)
    # Undocumented format (a name or ISO code); the service maps it and checks the script.
    language: str | None = Field(default=None, max_length=32)
    segments: list[GroqSegment] = Field(default_factory=list, max_length=200)


# Language-neutral terms: an English sentence here biases Whisper's language detection.
GROQ_VOCABULARY = "SIP, UPI, EMI, Swiggy, Zomato, Amazon"
MAX_GROQ_JSON_BYTES = 256 * 1024


def groq_transcribe(wav: bytes, language: Language | None, settings: Settings) -> GroqTranscription:
    """Groq Whisper for English/Hindi; callers keep Malayalam on OpenAI."""
    if not settings.groq_api_key or settings.groq_transcribe_model != "whisper-large-v3-turbo":
        raise ProviderUnavailable("configuration_missing")
    fields = {
        "model": settings.groq_transcribe_model,
        "response_format": "verbose_json",
        "temperature": "0",
        "prompt": GROQ_VOCABULARY,
    }
    if language in {"en", "hi"}:
        fields["language"] = language
    with provider_client(settings) as client:
        raw = bounded_request(
            client,
            "POST",
            str(settings.groq_base_url).rstrip("/") + "/audio/transcriptions",
            limit=MAX_GROQ_JSON_BYTES,
            headers={"Authorization": "Bearer " + settings.groq_api_key.get_secret_value()},
            data=fields,
            files={"file": ("question.wav", wav, "audio/wav")},
        )
    return GroqTranscription.model_validate_json(raw)


class SarvamTranscription(BaseModel):
    transcript: str = Field(max_length=2000, repr=False)
    # BCP-47 such as "ml-IN"; null when no speech was detected.
    language_code: str | None = Field(default=None, max_length=16)


class SarvamSpeech(BaseModel):
    audios: list[str] = Field(min_length=1, max_length=1, repr=False)


# Live check on 28 October 2026: saaras:v3 in codemix mode wrote spoken amounts as digits in all
# three languages ("₹500") and kept brand names in Latin ("Swiggy पे ₹500"); saaras:v4 left
# Malayalam amounts as words, which the amount parser does not read.
SARVAM_STT_MODELS = {"saaras:v3"}
SARVAM_TTS_MODELS = {"bulbul:v3"}  # Bulbul v4 Flash has no Malayalam voice
SARVAM_LANGUAGES: dict[Language, str] = {"en": "en-IN", "hi": "hi-IN", "ml": "ml-IN"}
MAX_SARVAM_JSON_BYTES = 256 * 1024


def sarvam_transcribe(
    wav: bytes, language: Language | None, settings: Settings
) -> SarvamTranscription:
    """Saaras speech-to-text for English, Hindi and Malayalam; no hint means auto-detect."""
    if not settings.sarvam_api_key or settings.sarvam_stt_model not in SARVAM_STT_MODELS:
        raise ProviderUnavailable("configuration_missing")
    with provider_client(settings) as client:
        raw = bounded_request(
            client,
            "POST",
            str(settings.sarvam_base_url).rstrip("/") + "/speech-to-text",
            limit=MAX_SARVAM_JSON_BYTES,
            headers={"api-subscription-key": settings.sarvam_api_key.get_secret_value()},
            data={
                "model": settings.sarvam_stt_model,
                "mode": "codemix",
                "language_code": SARVAM_LANGUAGES[language] if language else "unknown",
            },
            files={"file": ("question.wav", wav, "audio/wav")},
        )
    return SarvamTranscription.model_validate_json(raw)


def sarvam_synthesize(text: str, settings: Settings) -> tuple[bytes, str]:
    """Bulbul Malayalam speech; the speaker was chosen by listening, never defaulted."""
    if (
        not settings.sarvam_api_key
        or settings.sarvam_tts_model not in SARVAM_TTS_MODELS
        or not settings.sarvam_tts_speaker_ml
    ):
        raise ProviderUnavailable("configuration_missing")
    with provider_client(settings) as client:
        raw = bounded_request(
            client,
            "POST",
            str(settings.sarvam_base_url).rstrip("/") + "/text-to-speech",
            headers={"api-subscription-key": settings.sarvam_api_key.get_secret_value()},
            json={
                "text": text,
                "language_code": SARVAM_LANGUAGES["ml"],
                "model": settings.sarvam_tts_model,
                "speaker": settings.sarvam_tts_speaker_ml,
                "speech_sample_rate": SAMPLE_RATE,
                "output_audio_codec": "wav",
            },
        )
    return decode_base64(SarvamSpeech.model_validate_json(raw).audios[0]), "audio/wav"


PROVIDER_ERRORS = (httpx.HTTPError, ValidationError, ValueError, KeyError, TypeError)
