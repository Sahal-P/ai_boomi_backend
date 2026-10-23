from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.core.errors import ProviderUnavailable
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppReceipt
from finboy.services.assistant.models import AssistantAnswer
from finboy.services.speech.media import InvalidAudio
from finboy.services.speech.models import SynthesizedAudio, Transcript
from finboy.services.whatsapp import processor
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.meta import DownloadedAudio, InvalidMedia
from sqlalchemy.orm import Session


def harness(monkeypatch: pytest.MonkeyPatch, *, preferred: str | None = None):
    receipt = WhatsAppReceipt(id=uuid4(), binding_id=uuid4(), state="processing")
    binding = WhatsAppBinding(
        id=receipt.binding_id, user_id=LOCAL_USER_ID, enabled=True, language=preferred
    )
    session = MagicMock(spec=Session)
    session.get.return_value = binding
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session
    monkeypatch.setattr(processor.receipts, "claim", lambda *_: receipt)
    finish = MagicMock()
    monkeypatch.setattr(processor.receipts, "finish", finish)
    meta = MagicMock()
    monkeypatch.setattr(processor, "MetaClient", lambda _: meta)
    meta.download_audio.return_value = DownloadedAudio(b"synthetic", "audio/ogg")
    meta.upload_audio.return_value = "12345"
    send = MagicMock(return_value=True)
    monkeypatch.setattr(processor, "send_reply", send)
    ask = MagicMock(
        return_value=AssistantAnswer(
            intent="spend",
            policy="answer",
            display_text="synthetic text reply",
            speech_text="synthetic speech",
            speech_language=preferred or "en",
            facts=[],
            simulation=None,
            evidence_transactions=[],
            warnings=[],
        )
    )
    monkeypatch.setattr(processor.assistant, "answer_question", ask)
    transcribe = MagicMock(
        return_value=Transcript(
            transcript="synthetic question", detected_language=preferred or "en"
        )
    )
    monkeypatch.setattr(processor.speech, "transcribe_audio", transcribe)
    speak = MagicMock(return_value=SynthesizedAudio(b"synthetic mp3"))
    monkeypatch.setattr(processor.speech, "synthesize_speech", speak)
    return factory, receipt, binding, meta, send, ask, transcribe, speak, finish


@pytest.mark.parametrize("preferred", [None, "en", "hi", "ml"])
@pytest.mark.parametrize("kind", ["text", "audio"])
def test_shared_assistant_and_speech_routing(
    monkeypatch: pytest.MonkeyPatch,
    config: ChannelConfig,
    wa_settings: Settings,
    preferred: str | None,
    kind: str,
) -> None:
    factory, receipt, _, meta, send, ask, transcribe, speak, finish = harness(
        monkeypatch, preferred=preferred
    )
    question = InboundQuestion(
        "wamid.synthetic",
        "919000000001",
        datetime.now(UTC),
        kind,
        text="synthetic question",
        media_id="1234",
        mime_type="audio/ogg",
    )
    processor.process_question(factory, wa_settings, config, receipt.id, question)
    assert ask.call_count == 1
    assert ask.call_args.kwargs["display_style"] == (preferred or "auto")
    assert ask.call_args.kwargs["user_id"] == LOCAL_USER_ID
    assert send.call_args_list[0].kwargs["text"] == "synthetic text reply"
    assert transcribe.call_count == speak.call_count == (1 if kind == "audio" else 0)
    assert send.call_count == (2 if kind == "audio" else 1)
    if kind == "audio":
        assert send.call_args_list[1].kwargs["media_id"] == "12345"
        assert transcribe.call_args.kwargs["language_hint"] == preferred
    assert finish.call_args.kwargs["error"] is None
    meta.close.assert_called_once()


@pytest.mark.parametrize("fault", ["stt", "tts", "media", "assistant", "invalid_audio"])
def test_provider_failure_keeps_correct_text_when_available(
    monkeypatch: pytest.MonkeyPatch, config: ChannelConfig, wa_settings: Settings, fault: str
) -> None:
    factory, receipt, _, meta, send, ask, transcribe, speak, finish = harness(monkeypatch)
    if fault == "invalid_audio":
        transcribe.side_effect = InvalidAudio()
    if fault == "stt":
        transcribe.side_effect = ProviderUnavailable("speech_unavailable")
    if fault == "tts":
        speak.side_effect = ProviderUnavailable("speech_unavailable")
    if fault == "media":
        meta.download_audio.side_effect = InvalidMedia
    if fault == "assistant":
        ask.side_effect = ProviderUnavailable("assistant_unavailable")
    question = InboundQuestion(
        "wamid.synthetic",
        "919000000001",
        datetime.now(UTC),
        "audio",
        media_id="1234",
        mime_type="audio/ogg",
    )
    processor.process_question(factory, wa_settings, config, receipt.id, question)
    assert send.call_count == 1
    response = send.call_args.kwargs["text"]
    assert "synthetic text reply" in response if fault == "tts" else "could not process" in response
    if fault != "tts":
        assert finish.call_args.kwargs["error"] is not None


@pytest.mark.parametrize("command", ["stop", "start", "en", "hi", "ml"])
def test_commands_never_call_assistant(
    monkeypatch: pytest.MonkeyPatch, config: ChannelConfig, wa_settings: Settings, command: str
) -> None:
    factory, receipt, binding, _, send, ask, transcribe, speak, _ = harness(monkeypatch)
    binding.enabled = command != "stop"
    processor.process_question(
        factory,
        wa_settings,
        config,
        receipt.id,
        InboundQuestion("wamid.command", "919000000001", datetime.now(UTC), "text", text=command),
    )
    assert send.call_count == 1
    assert not ask.called and not transcribe.called and not speak.called


def test_unexpected_failure_log_redaction(
    monkeypatch: pytest.MonkeyPatch,
    config: ChannelConfig,
    wa_settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    factory, receipt, _, _, send, ask, _, _, _ = harness(monkeypatch)
    ask.side_effect = RuntimeError("sensitive financial answer private-token")
    processor.process_question(
        factory,
        wa_settings,
        config,
        receipt.id,
        InboundQuestion(
            "wamid.synthetic", "919000000001", datetime.now(UTC), "text", text="private question"
        ),
    )
    assert "whatsapp.processing_failed" in caplog.text
    assert "sensitive" not in caplog.text and "private" not in caplog.text
    assert not send.called


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:3014/review", "http://localhost:3000/review", "http://[::1]:3000/review"],
)
def test_phone_answers_direct_review_to_demo_computer(url: str) -> None:
    response = processor.phone_text("Please review at " + url + ".")
    assert "http" not in response and "demo computer" in response
