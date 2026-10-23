import base64
import json
import subprocess
from unittest.mock import MagicMock

import httpx
import pytest
from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.services.speech import providers, service
from finboy.services.speech.media import InvalidAudio, decode_audio, pcm_to_wav, to_mp3
from finboy.services.speech.models import SynthesizedAudio
from pydantic import SecretStr


@pytest.fixture
def wav() -> bytes:
    return pcm_to_wav(b"\0\0" * 2400)


@pytest.fixture
def configured(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "openai_api_key": SecretStr("synthetic-not-real"),
            "openai_transcribe_model": "gpt-transcribe",
            "gemini_api_key": SecretStr("synthetic-gemini"),
            "gemini_tts_model": "gemini-3.8-flash-tts",
            "gemini_tts_voice": "Kore",
            "resemble_api_key": SecretStr("synthetic-resemble"),
            "resemble_tts_model": "resemble-ultra",
            "resemble_voice_uuid_en": "stock-en",
            "resemble_voice_uuid_hi": "stock-hi",
        }
    )


def mock_http(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    monkeypatch.setattr(
        providers,
        "provider_client",
        lambda settings: httpx.Client(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.parametrize("language", ["en", "hi", "ml"])
def test_stt_detected_languages_and_hint(
    monkeypatch: pytest.MonkeyPatch, configured: Settings, wav: bytes, language: str
) -> None:
    fake = MagicMock()
    result = fake.return_value.__enter__.return_value.audio.transcriptions.create.return_value
    result.model_dump.return_value = {
        "text": "synthetic transcript",
        "languages": [{"code": language}],
    }
    monkeypatch.setattr(service, "OpenAI", fake)
    output = service.transcribe_audio(
        audio=wav, content_type="audio/wav", settings=configured, language_hint=language
    )
    assert output.detected_language == language
    call = fake.return_value.__enter__.return_value.audio.transcriptions.create.call_args.kwargs
    assert call["extra_body"]["languages"] == [language]
    assert call["file"][1].startswith(b"RIFF")


def test_mixed_or_uncertain_language_is_not_fabricated(
    monkeypatch: pytest.MonkeyPatch, configured: Settings, wav: bytes
) -> None:
    fake = MagicMock()
    result = fake.return_value.__enter__.return_value.audio.transcriptions.create.return_value
    result.model_dump.return_value = {
        "text": "hello नमस्ते",
        "languages": [{"code": "en"}, {"code": "hi"}],
    }
    monkeypatch.setattr(service, "OpenAI", fake)
    assert (
        service.transcribe_audio(
            audio=wav, content_type="audio/wav", settings=configured, language_hint="hi"
        ).detected_language
        == "unknown"
    )


def test_media_size_duration_and_real_container(settings: Settings, wav: bytes) -> None:
    assert decode_audio(
        audio=wav, content_type="audio/wav", settings=settings, max_bytes=10000, max_seconds=30
    )
    for audio, mime in [
        (b"not audio", "audio/wav"),
        (wav, "audio/mpeg"),
        (wav, "application/pdf"),
        (pcm_to_wav(b"\0\0" * 24000 * 31), "audio/wav"),
    ]:
        with pytest.raises(InvalidAudio):
            service.transcribe_audio(audio=audio, content_type=mime, settings=settings)
    with pytest.raises(InvalidAudio) as exc:
        service.transcribe_audio(
            audio=b"x" * (3 * 1024 * 1024 + 1), content_type="audio/wav", settings=settings
        )
    assert exc.value.status_code == 413


def test_mp3_is_real_and_pcm_has_wav_header(settings: Settings, wav: bytes) -> None:
    mp3 = to_mp3(wav, "audio/wav", settings)
    probe = subprocess.run(
        [
            settings.ffprobe_binary,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "json",
            "-i",
            "pipe:0",
        ],
        input=mp3,
        capture_output=True,
        check=True,
    )
    assert json.loads(probe.stdout)["streams"][0]["codec_name"] == "mp3"
    assert not mp3.startswith(b"RIFF")
    assert "data=" not in repr(SynthesizedAudio(mp3))


@pytest.mark.parametrize(
    "language,text,expected",
    [("en", "Hello", "resemble"), ("hi", "नमस्ते", "resemble"), ("ml", "നമസ്കാരം", "gemini")],
)
def test_provider_routing(
    monkeypatch: pytest.MonkeyPatch,
    configured: Settings,
    wav: bytes,
    language: str,
    text: str,
    expected: str,
) -> None:
    resemble = MagicMock(return_value=(wav, "audio/wav"))
    gemini = MagicMock(return_value=(wav, "audio/wav"))
    monkeypatch.setattr(providers, "resemble_synthesize", resemble)
    monkeypatch.setattr(providers, "gemini_synthesize", gemini)
    result = service.synthesize_speech(text=text, language=language, settings=configured)
    assert result.media_type == "audio/mpeg" and result.data
    assert resemble.call_count == (expected == "resemble") and gemini.call_count == (
        expected == "gemini"
    )


def test_gemini_current_schema_transient_and_header_key(
    monkeypatch: pytest.MonkeyPatch, configured: Settings, wav: bytes
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1beta/interactions" and not request.url.query
        assert request.headers["x-goog-api-key"] == "synthetic-gemini"
        body = json.loads(request.content)
        assert body["store"] is False
        assert body["model"] == "gemini-3.8-flash-tts"
        return httpx.Response(
            200,
            json={
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {
                                "type": "audio",
                                "mime_type": "audio/wav",
                                "data": base64.b64encode(wav).decode(),
                            }
                        ],
                    }
                ]
            },
        )

    mock_http(monkeypatch, handler)
    assert providers.gemini_synthesize("നമസ്കാരം", configured) == (wav, "audio/wav")


def test_resemble_omits_stored_clip_parameters_and_model(
    monkeypatch: pytest.MonkeyPatch, configured: Settings
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer synthetic-resemble"
        assert json.loads(request.content) == {
            "voice_uuid": "stock-hi",
            "data": "नमस्ते",
            "output_format": "mp3",
        }
        return httpx.Response(
            200,
            json={
                "success": True,
                "output_format": "mp3",
                "audio_content": base64.b64encode(b"synthetic-bytes").decode(),
            },
        )

    mock_http(monkeypatch, handler)
    assert providers.resemble_synthesize("नमस्ते", "hi", configured)[1] == "audio/mpeg"


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_provider_errors_are_fixed_and_redacted(
    monkeypatch: pytest.MonkeyPatch, configured: Settings, status: int, caplog
) -> None:
    mock_http(
        monkeypatch,
        lambda request: httpx.Response(
            status, json={"error": "NEVER-LEAK-body-key-financial-text"}
        ),
    )
    with pytest.raises(ProviderUnavailable) as exc:
        service.synthesize_speech(text="നമസ്കാരം", language="ml", settings=configured)
    assert str(exc.value) == "speech_unavailable"
    assert "NEVER-LEAK" not in caplog.text and "synthetic-gemini" not in caplog.text


def test_timeout_and_missing_credentials(
    monkeypatch: pytest.MonkeyPatch, configured: Settings, settings: Settings
) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("NEVER-LEAK", request=request)

    mock_http(monkeypatch, timeout)
    with pytest.raises(ProviderUnavailable, match="speech_unavailable"):
        service.synthesize_speech(text="നമസ്കാരം", language="ml", settings=configured)
    with pytest.raises(ProviderUnavailable, match="configuration_missing"):
        service.synthesize_speech(text="Hello", language="en", settings=settings)


@pytest.mark.anyio
async def test_multipart_never_spools_and_limits(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, wav: bytes
) -> None:
    import finboy.api.v1.assistant as routes
    from finboy.services.speech.models import Transcript

    fake = MagicMock(
        return_value=Transcript(transcript="editable synthetic", detected_language="unknown")
    )
    monkeypatch.setattr(routes, "transcribe_audio", fake)
    response = await client.post(
        "/api/v1/assistant/transcribe",
        files={"audio": ("question.wav", wav, "audio/wav")},
        data={"language_hint": "ml"},
    )
    assert response.status_code == 200 and response.json()["detected_language"] == "unknown"
    assert fake.call_args.kwargs["audio"] == wav
    assert fake.call_args.kwargs["language_hint"] == "ml"
    bad = await client.post(
        "/api/v1/assistant/transcribe",
        files={"audio": ("question.wav", wav, "audio/wav")},
        data={"language_hint": "xx"},
    )
    assert bad.status_code == 422
    huge = await client.post(
        "/api/v1/assistant/transcribe",
        files={"audio": ("question.wav", b"x" * (3 * 1024 * 1024 + 9000), "audio/wav")},
    )
    assert huge.status_code == 413


@pytest.mark.anyio
async def test_speak_actual_mpeg_contract(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, settings: Settings, wav: bytes
) -> None:
    import finboy.api.v1.assistant as routes

    mp3 = to_mp3(wav, "audio/wav", settings)
    monkeypatch.setattr(routes, "synthesize_speech", lambda **kwargs: SynthesizedAudio(mp3))
    result = await client.post("/api/v1/assistant/speak", json={"text": "Hello", "language": "en"})
    assert result.status_code == 200 and result.headers["content-type"] == "audio/mpeg"
    assert result.content == mp3 and result.headers["cache-control"] == "no-store"
    assert (
        await client.post("/api/v1/assistant/speak", json={"text": "x" * 601, "language": "en"})
    ).status_code == 422


def test_base64_newlines_are_accepted_without_accepting_garbage() -> None:
    assert providers.decode_base64("aGVs\nbG8=\n") == b"hello"
    with pytest.raises(ProviderUnavailable):
        providers.decode_base64("not!base64")


@pytest.mark.anyio
async def test_audio_part_limit_preserves_413(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/assistant/transcribe",
        files={"audio": ("question.wav", b"x" * (3 * 1024 * 1024 + 1), "audio/wav")},
    )
    assert response.status_code == 413
