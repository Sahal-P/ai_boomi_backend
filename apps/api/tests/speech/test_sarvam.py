"""Sarvam speech (docs/malayalam-round/contract.md): request shapes, routing and redaction."""

import base64
import json
import subprocess
from unittest.mock import MagicMock

import httpx
import pytest
from finboy.api.v1.readiness import _malayalam_tts, _transcription
from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.services.speech import providers, service
from finboy.services.speech.media import pcm_to_wav
from finboy.services.speech.models import Transcript
from pydantic import SecretStr, ValidationError


@pytest.fixture
def wav() -> bytes:
    return pcm_to_wav(b"\0\0" * 2400)


@pytest.fixture
def sarvam(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "speech_transcribe_provider": "sarvam",
            "malayalam_tts_provider": "sarvam",
            "sarvam_api_key": SecretStr("synthetic-sarvam"),
            "sarvam_stt_model": "saaras:v3",
            "sarvam_tts_model": "bulbul:v3",
            "sarvam_tts_speaker_ml": "kavitha",
            "openai_api_key": SecretStr("synthetic-openai"),
            "openai_transcribe_model": "gpt-transcribe",
        }
    )


def mock_http(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    monkeypatch.setattr(
        providers,
        "provider_client",
        lambda settings: httpx.Client(transport=httpx.MockTransport(handler)),
    )


def heard(transcript: str, code: str | None) -> httpx.Response:
    return httpx.Response(
        200, json={"request_id": "synthetic", "transcript": transcript, "language_code": code}
    )


@pytest.fixture
def openai(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    fake = MagicMock()
    monkeypatch.setattr(service, "OpenAI", fake)
    return fake


@pytest.mark.parametrize(
    "hint,code", [("en", "en-IN"), ("hi", "hi-IN"), ("ml", "ml-IN"), (None, "unknown")]
)
def test_request_shape(
    monkeypatch: pytest.MonkeyPatch,
    sarvam: Settings,
    wav: bytes,
    openai: MagicMock,
    hint: str | None,
    code: str,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return heard("Paid the milkman ₹500 yesterday.", "en-IN")

    mock_http(monkeypatch, handler)
    transcript, provider = service.transcribe_routed(
        audio=wav, content_type="audio/wav", settings=sarvam, language_hint=hint
    )
    request, body = seen[0], seen[0].content
    assert request.method == "POST" and str(request.url) == "https://api.sarvam.ai/speech-to-text"
    assert request.headers["api-subscription-key"] == "synthetic-sarvam"
    assert "authorization" not in request.headers
    assert request.headers["content-type"].startswith("multipart/form-data")
    assert b'name="model"\r\n\r\nsaaras:v3\r\n' in body
    assert b'name="mode"\r\n\r\ncodemix\r\n' in body
    assert b'name="language_code"\r\n\r\n' + code.encode() + b"\r\n" in body
    assert b"RIFF" in body and b"keyterms" not in body
    assert provider == "sarvam" and len(seen) == 1 and not openai.called
    assert transcript == Transcript(
        transcript="Paid the milkman ₹500 yesterday.", detected_language="en"
    )


@pytest.mark.parametrize(
    "code,text,expected",
    [
        ("hi-IN", "मैंने कल Swiggy पे ₹500 दिए।", "hi"),
        ("ml-IN", "പാൽക്കാരന് ₹500 കൊടുത്തു.", "ml"),
        ("ml-IN", "Swiggy-ൽ ₹500 കൊടുത്തു", "ml"),
        ("en-IN", "Got salary ₹25000", "en"),
        ("ta-IN", "பால்காரருக்கு ₹500", "unknown"),
        ("ur-IN", "اس مہینے کھانے پر", "unknown"),
        ("hi-IN", "اس مہینے کھانے پر", "unknown"),
        ("ml-IN", "दूधवाले को ₹500 दिए", "unknown"),
    ],
)
def test_language_needs_the_matching_script(
    monkeypatch: pytest.MonkeyPatch, sarvam: Settings, wav: bytes, code: str, text: str, expected
) -> None:
    mock_http(monkeypatch, lambda request: heard(f" {text} ", code))
    transcript, provider = service.transcribe_routed(
        audio=wav, content_type="audio/wav", settings=sarvam
    )
    assert provider == "sarvam"
    assert transcript == Transcript(transcript=text, detected_language=expected)


@pytest.mark.parametrize(
    "transcript,code", [("", None), ("   ", "hi-IN"), ("", "ml-IN"), ("Thank you.", None)]
)
def test_nothing_heard_is_empty_and_never_guessed(
    monkeypatch: pytest.MonkeyPatch,
    sarvam: Settings,
    wav: bytes,
    openai: MagicMock,
    transcript: str,
    code: str | None,
) -> None:
    mock_http(monkeypatch, lambda request: heard(transcript, code))
    assert service.transcribe_routed(audio=wav, content_type="audio/wav", settings=sarvam) == (
        Transcript(transcript="", detected_language="unknown"),
        "sarvam",
    )
    assert not openai.called


def _timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("NEVER-LEAK-timeout", request=request)


def _error(status: int):
    body = {"error": {"request_id": "x", "message": "NEVER-LEAK-body", "code": "rate_limit"}}
    return lambda request: httpx.Response(status, json=body)


@pytest.mark.parametrize(
    "handler",
    [
        *[_error(status) for status in (400, 401, 403, 422, 429, 500, 503)],
        lambda request: httpx.Response(302, headers={"Location": "https://redirect.test/"}),
        lambda request: httpx.Response(200, content=b"NEVER-LEAK not json"),
        lambda request: httpx.Response(200, content=b'{"transcript":"' + b"x" * 300_000 + b'"}'),
        lambda request: heard("x" * 2001, "en-IN"),
        lambda request: httpx.Response(200, json={"language_code": "hi-IN"}),
        _timeout,
    ],
)
def test_failures_are_fixed_redacted_and_never_retried_elsewhere(
    monkeypatch: pytest.MonkeyPatch,
    sarvam: Settings,
    wav: bytes,
    openai: MagicMock,
    handler,
    caplog,
) -> None:
    mock_http(monkeypatch, handler)
    with pytest.raises(ProviderUnavailable) as exc:
        service.transcribe_audio(audio=wav, content_type="audio/wav", settings=sarvam)
    assert str(exc.value) == "speech_unavailable"
    assert not openai.called
    assert "NEVER-LEAK" not in caplog.text and "synthetic-sarvam" not in caplog.text


@pytest.mark.parametrize(
    "update",
    [{"sarvam_api_key": None}, {"sarvam_stt_model": None}, {"sarvam_stt_model": "saaras:v4"}],
)
def test_transcription_requires_the_verified_model(
    monkeypatch: pytest.MonkeyPatch, sarvam: Settings, wav: bytes, openai: MagicMock, update
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Sarvam must not be called")

    mock_http(monkeypatch, handler)
    with pytest.raises(ProviderUnavailable, match="configuration_missing"):
        service.transcribe_audio(
            audio=wav, content_type="audio/wav", settings=sarvam.model_copy(update=update)
        )
    assert not openai.called


def spoken(wav: bytes, count: int = 1) -> httpx.Response:
    return httpx.Response(
        200,
        json={"request_id": "synthetic", "audios": [base64.b64encode(wav).decode()] * count},
    )


def test_malayalam_speech_request_shape_and_real_mp3(
    monkeypatch: pytest.MonkeyPatch, sarvam: Settings, wav: bytes
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return spoken(wav)

    mock_http(monkeypatch, handler)
    monkeypatch.setattr(providers, "gemini_synthesize", MagicMock(side_effect=AssertionError))
    audio = service.synthesize_speech(text="നമസ്കാരം", language="ml", settings=sarvam)
    request = seen[0]
    assert str(request.url) == "https://api.sarvam.ai/text-to-speech"
    assert request.headers["api-subscription-key"] == "synthetic-sarvam"
    assert json.loads(request.content) == {
        "text": "നമസ്കാരം",
        "language_code": "ml-IN",
        "model": "bulbul:v3",
        "speaker": "kavitha",
        "speech_sample_rate": 24000,
        "output_audio_codec": "wav",
    }
    probe = subprocess.run(
        [sarvam.ffprobe_binary, "-v", "error", "-show_entries", "stream=codec_name"]
        + ["-of", "json", "-i", "pipe:0"],
        input=audio.data,
        capture_output=True,
        check=True,
    )
    assert json.loads(probe.stdout)["streams"][0]["codec_name"] == "mp3"
    assert audio.media_type == "audio/mpeg" and not audio.data.startswith(b"RIFF")


@pytest.mark.parametrize(
    "provider,language,expected",
    [
        ("gemini", "ml", "gemini"),
        ("sarvam", "ml", "sarvam"),
        ("sarvam", "hi", "resemble"),
        ("sarvam", "en", "resemble"),
    ],
)
def test_only_malayalam_speech_follows_the_setting(
    monkeypatch: pytest.MonkeyPatch, sarvam: Settings, wav: bytes, provider, language, expected
) -> None:
    calls = {
        name: MagicMock(return_value=(wav, "audio/wav"))
        for name in ("gemini_synthesize", "sarvam_synthesize", "resemble_synthesize")
    }
    for name, fake in calls.items():
        monkeypatch.setattr(providers, name, fake)
    text = {"ml": "നമസ്കാരം", "hi": "नमस्ते", "en": "Hello"}[language]
    service.synthesize_speech(
        text=text,
        language=language,
        settings=sarvam.model_copy(update={"malayalam_tts_provider": provider}),
    )
    assert [name for name, fake in calls.items() if fake.called] == [f"{expected}_synthesize"]


@pytest.mark.parametrize(
    "handler",
    [
        *[_error(status) for status in (400, 403, 429, 500)],
        lambda request: httpx.Response(200, json={"audios": []}),
        lambda request: httpx.Response(200, json={"audios": ["bm90IGF1ZGlv", "bm90IGF1ZGlv"]}),
        lambda request: httpx.Response(200, json={"audios": ["NEVER-LEAK!not-base64"]}),
        lambda request: httpx.Response(200, json={"audios": [base64.b64encode(b"x").decode()]}),
        _timeout,
    ],
)
def test_speech_failures_are_fixed_and_redacted(
    monkeypatch: pytest.MonkeyPatch, sarvam: Settings, handler, caplog
) -> None:
    mock_http(monkeypatch, handler)
    with pytest.raises(ProviderUnavailable) as exc:
        service.synthesize_speech(text="നമസ്കാരം", language="ml", settings=sarvam)
    assert str(exc.value) == "speech_unavailable"
    assert "NEVER-LEAK" not in caplog.text and "synthetic-sarvam" not in caplog.text


@pytest.mark.parametrize(
    "update",
    [
        {"sarvam_api_key": None},
        {"sarvam_tts_model": None},
        {"sarvam_tts_model": "bulbul:v4-flash"},
        {"sarvam_tts_speaker_ml": None},
    ],
)
def test_speech_requires_a_verified_model_and_a_chosen_voice(
    monkeypatch: pytest.MonkeyPatch, sarvam: Settings, update
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Sarvam must not be called")

    mock_http(monkeypatch, handler)
    with pytest.raises(ProviderUnavailable, match="configuration_missing"):
        service.synthesize_speech(
            text="നമസ്കാരം", language="ml", settings=sarvam.model_copy(update=update)
        )


def test_settings_validation(settings: Settings) -> None:
    base = {**settings.model_dump(), "_env_file": None}
    for update in (
        {"sarvam_base_url": "http://api.sarvam.ai"},
        {"sarvam_base_url": "https://user:secret@api.sarvam.ai"},
        {"sarvam_base_url": "https://api.sarvam.ai?key=value"},
        {"sarvam_tts_speaker_ml": "Kavitha"},
        {"sarvam_tts_speaker_ml": "kavitha; rm"},
        {"malayalam_tts_provider": "resemble"},
        {"speech_transcribe_provider": "saaras"},
    ):
        with pytest.raises(ValidationError):
            Settings(**{**base, **update})
    blank = Settings(
        **{
            **base,
            "sarvam_api_key": "",
            "sarvam_stt_model": "",
            "sarvam_tts_model": "",
            "sarvam_tts_speaker_ml": "",
        }
    )
    assert blank.sarvam_api_key is blank.sarvam_stt_model is None
    assert blank.sarvam_tts_model is blank.sarvam_tts_speaker_ml is None
    assert (blank.speech_transcribe_provider, blank.malayalam_tts_provider) == ("openai", "gemini")
    assert "synthetic" not in repr(Settings(**{**base, "sarvam_api_key": "synthetic-sarvam"}))


def test_readiness_follows_the_chosen_providers(settings: Settings, sarvam: Settings) -> None:
    assert _transcription(sarvam) and _malayalam_tts(sarvam)
    assert not _transcription(sarvam.model_copy(update={"sarvam_stt_model": None}))
    assert not _malayalam_tts(sarvam.model_copy(update={"sarvam_tts_speaker_ml": None}))
    # The defaults keep reporting OpenAI transcription and Gemini Malayalam speech.
    assert not _transcription(settings) and not _malayalam_tts(settings)
    openai_only = sarvam.model_copy(update={"speech_transcribe_provider": "openai"})
    assert _transcription(openai_only)
    groq = openai_only.model_copy(update={"speech_transcribe_provider": "groq"})
    assert not _transcription(groq)
    assert _transcription(
        groq.model_copy(
            update={
                "groq_api_key": SecretStr("synthetic-groq"),
                "groq_transcribe_model": "whisper-large-v3-turbo",
            }
        )
    )
