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


@pytest.fixture
def groq_mode(configured: Settings) -> Settings:
    return configured.model_copy(
        update={
            "speech_transcribe_provider": "groq",
            "groq_api_key": SecretStr("synthetic-groq"),
            "groq_transcribe_model": "whisper-large-v3-turbo",
        }
    )


def fake_openai(monkeypatch: pytest.MonkeyPatch, code: str = "ml") -> MagicMock:
    fake = MagicMock()
    result = fake.return_value.__enter__.return_value.audio.transcriptions.create.return_value
    result.model_dump.return_value = {"text": "openai transcript", "languages": [{"code": code}]}
    monkeypatch.setattr(service, "OpenAI", fake)
    return fake


def whisper(text: str, language: str | None = "english", **extra: object) -> httpx.Response:
    segments = extra.pop("segments", [{"no_speech_prob": 0.01, "avg_logprob": -0.2}])
    return httpx.Response(200, json={"text": text, "language": language, "segments": segments})


@pytest.mark.parametrize("hint", ["en", "hi", None])
def test_groq_request_shape(
    monkeypatch: pytest.MonkeyPatch, groq_mode: Settings, wav: bytes, hint: str | None
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if hint == "hi":
            return whisper("खाने पर कितना खर्च हुआ", "hindi")
        return whisper("How much did I spend on food?", "English")

    mock_http(monkeypatch, handler)
    openai = fake_openai(monkeypatch)
    transcript, provider = service.transcribe_routed(
        audio=wav, content_type="audio/wav", settings=groq_mode, language_hint=hint
    )
    request = seen[0]
    body = request.content
    assert request.method == "POST" and request.url.path == "/openai/v1/audio/transcriptions"
    assert str(request.url).startswith("https://api.groq.com/") and not request.url.query
    assert request.headers["Authorization"] == "Bearer synthetic-groq"
    assert request.headers["content-type"].startswith("multipart/form-data")
    assert b'name="model"\r\n\r\nwhisper-large-v3-turbo\r\n' in body
    assert b'name="response_format"\r\n\r\nverbose_json\r\n' in body
    assert b'name="temperature"\r\n\r\n0\r\n' in body
    assert b"SIP, UPI, EMI" in body and b"RIFF" in body
    assert (b'name="language"\r\n\r\n' + (hint or "").encode() in body) == (hint is not None)
    assert provider == "groq" and transcript.detected_language == (hint or "en")
    assert not openai.called


@pytest.mark.parametrize(
    "hint,reported,text,provider,language",
    [
        ("en", "english", "food spending this month", "groq", "en"),
        ("hi", "hindi", "इस महीने खाने पर कितना खर्च हुआ", "groq", "hi"),
        (None, "English", "food spending this month", "groq", "en"),
        (None, "hi", "SIP पर कितना खर्च हुआ", "groq", "hi"),
        (None, "malayalam", "ഈ മാസം ഭക്ഷണത്തിന് എത്ര ചെലവായി", "openai", "ml"),
        (None, "tamil", "இந்த மாதம் உணவுக்கு", "openai", "ml"),
        (None, None, "food spending this month", "openai", "ml"),
        (None, "hindi", "is mahine khane par kitna kharch hua", "openai", "ml"),
        (None, "hindi", "اس مہینے کھانے پر", "openai", "ml"),
        ("hi", "hindi", "اس مہینے کھانے پر", "openai", "ml"),
        ("en", "english", "खाना", "openai", "ml"),
    ],
)
def test_groq_routing_escalates_uncertain_results_once(
    monkeypatch: pytest.MonkeyPatch,
    groq_mode: Settings,
    wav: bytes,
    hint: str | None,
    reported: str | None,
    text: str,
    provider: str,
    language: str,
) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return whisper(text, reported)

    mock_http(monkeypatch, handler)
    openai = fake_openai(monkeypatch)
    transcript, served = service.transcribe_routed(
        audio=wav, content_type="audio/wav", settings=groq_mode, language_hint=hint
    )
    assert len(calls) == 1 and served == provider
    assert transcript.detected_language == language
    create = openai.return_value.__enter__.return_value.audio.transcriptions.create
    assert create.call_count == (provider == "openai")
    if provider == "openai":
        assert create.call_args.kwargs["file"][1].startswith(b"RIFF")
        assert create.call_args.kwargs["extra_body"]["languages"] == (
            [hint] if hint else ["en", "hi", "ml"]
        )
    else:
        assert transcript.transcript == text


def test_malayalam_hint_and_openai_mode_never_call_groq(
    monkeypatch: pytest.MonkeyPatch, groq_mode: Settings, configured: Settings, wav: bytes
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Groq must not be called")

    mock_http(monkeypatch, handler)
    fake_openai(monkeypatch)
    assert service.transcribe_routed(
        audio=wav, content_type="audio/wav", settings=groq_mode, language_hint="ml"
    ) == (service.Transcript(transcript="openai transcript", detected_language="ml"), "openai")
    for hint in ("en", "hi", None):
        assert (
            service.transcribe_routed(
                audio=wav, content_type="audio/wav", settings=configured, language_hint=hint
            )[1]
            == "openai"
        )


@pytest.mark.parametrize(
    "segments,text,silent",
    [
        ([{"no_speech_prob": 0.92, "avg_logprob": -1.4}], " Thank you.", True),
        ([], "   ", True),
        ([{"no_speech_prob": 0.7, "avg_logprob": -0.5}], "food this month", False),
        (
            [
                {"no_speech_prob": 0.95, "avg_logprob": -1.6},
                {"no_speech_prob": 0.02, "avg_logprob": -0.3},
            ],
            "food this month",
            False,
        ),
    ],
)
def test_silence_guard_drops_hallucinated_filler_without_escalation(
    monkeypatch: pytest.MonkeyPatch,
    groq_mode: Settings,
    wav: bytes,
    segments: list[dict[str, float]],
    text: str,
    silent: bool,
) -> None:
    mock_http(monkeypatch, lambda request: whisper(text, "english", segments=segments))
    openai = fake_openai(monkeypatch)
    transcript, provider = service.transcribe_routed(
        audio=wav, content_type="audio/wav", settings=groq_mode
    )
    assert provider == "groq" and not openai.called
    assert transcript.transcript == ("" if silent else text)
    assert transcript.detected_language == ("unknown" if silent else "en")


def _timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("NEVER-LEAK-timeout", request=request)


def _status(status: int):
    return lambda request: httpx.Response(status, json={"error": "NEVER-LEAK-groq-body"})


@pytest.mark.parametrize(
    "handler",
    [
        *[_status(status) for status in (401, 403, 429, 500, 503)],
        lambda request: httpx.Response(302, headers={"Location": "https://redirect.test/"}),
        lambda request: httpx.Response(200, content=b"NEVER-LEAK not json"),
        lambda request: httpx.Response(200, content=b'{"text":"' + b"x" * 300_000 + b'"}'),
        lambda request: whisper("x" * 2001),
        lambda request: httpx.Response(200, json={"language": "english"}),
        _timeout,
    ],
)
def test_groq_failures_are_fixed_redacted_and_never_retried_on_openai(
    monkeypatch: pytest.MonkeyPatch, groq_mode: Settings, wav: bytes, handler, caplog
) -> None:
    mock_http(monkeypatch, handler)
    openai = fake_openai(monkeypatch)
    with pytest.raises(ProviderUnavailable) as exc:
        service.transcribe_audio(audio=wav, content_type="audio/wav", settings=groq_mode)
    assert str(exc.value) == "speech_unavailable"
    assert not openai.called
    assert "NEVER-LEAK" not in caplog.text and "synthetic-groq" not in caplog.text


@pytest.mark.parametrize(
    "update",
    [
        {"groq_api_key": None},
        {"groq_transcribe_model": None},
        {"groq_transcribe_model": "whisper-large-v3"},
    ],
)
def test_groq_requires_verified_configuration(
    monkeypatch: pytest.MonkeyPatch, groq_mode: Settings, wav: bytes, update: dict
) -> None:
    mock_http(monkeypatch, lambda request: whisper("food"))
    openai = fake_openai(monkeypatch)
    with pytest.raises(ProviderUnavailable, match="configuration_missing"):
        service.transcribe_audio(
            audio=wav, content_type="audio/wav", settings=groq_mode.model_copy(update=update)
        )
    assert not openai.called


@pytest.mark.parametrize(
    "reported,text,expected",
    [
        ("Hindi", "SIP कितना है", "hi"),
        ("hindi", "SIP", "unknown"),
        ("english", "food ₹500", "en"),
        ("english", "₹500", "unknown"),
        ("english", "खाना", "unknown"),
        ("malayalam", "ഭക്ഷണം UPI", "ml"),
        ("ml", "भोजन", "unknown"),
        ("telugu", "food", "unknown"),
        (None, "food", "unknown"),
    ],
)
def test_script_language_requires_matching_script(
    reported: str | None, text: str, expected: str
) -> None:
    assert service.script_language(reported, text) == expected


def test_groq_settings_validation(settings: Settings) -> None:
    from pydantic import ValidationError

    base = {**settings.model_dump(), "_env_file": None}
    for value in (
        "http://api.groq.com/openai/v1",
        "https://user:secret@api.groq.com/openai/v1",
        "https://api.groq.com/openai/v1?key=value",
    ):
        with pytest.raises(ValidationError):
            Settings(**{**base, "groq_base_url": value})
    with pytest.raises(ValidationError):
        Settings(**{**base, "speech_transcribe_provider": "whisper"})
    blank = Settings(
        **{**base, "groq_api_key": "", "groq_transcribe_model": "", "openai_vision_model": ""}
    )
    assert blank.groq_api_key is blank.groq_transcribe_model is blank.openai_vision_model is None
    assert blank.speech_transcribe_provider == "openai"
    assert "synthetic" not in repr(Settings(**{**base, "groq_api_key": "synthetic-groq"}))


def test_benchmark_no_hint_reports_served_provider(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    from finboy.services.speech import benchmark
    from finboy.services.speech.models import Transcript

    hints: list[str | None] = []

    def routed(**kwargs: object) -> tuple[Transcript, str]:
        hints.append(kwargs["language_hint"])  # type: ignore[arg-type]
        return Transcript(transcript="synthetic", detected_language="unknown"), "openai"

    monkeypatch.setattr(benchmark, "transcribe_routed", routed)
    report = benchmark.run(settings=settings, live=True, real=False, hint=False)
    assert report["mode"] == "live_stt_no_hint"
    assert hints and set(hints) == {None}
    assert {row["stt_provider"] for row in report["samples"]} == {"openai"}
