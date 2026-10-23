from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from finboy.core.config import Settings
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppDelivery, WhatsAppReceipt
from finboy.db.session import build_engine
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion, Status
from finboy.services.whatsapp.meta import MetaUnavailable, SendUnknown
from finboy.services.whatsapp.processor import send_reply
from finboy.services.whatsapp.receipts import admit, claim, interrupt_stale
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration


@pytest.fixture
def factory(config: ChannelConfig) -> Iterator[sessionmaker[Session]]:
    settings = Settings()
    url = make_url(settings.database_url.get_secret_value())
    if (
        settings.environment == "production"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database != "finboy_p4"
    ):
        pytest.fail("WhatsApp integration tests require disposable local finboy_p4")
    engine = build_engine(settings)
    factory = sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        with factory() as session:
            # Only this suite's synthetic identities are removed, including their cascade metadata.
            session.execute(
                delete(WhatsAppBinding).where(
                    WhatsAppBinding.sender_hash == config.digest("sender", "919000000001")
                )
            )
            session.commit()
        engine.dispose()


def question(text: str = "synthetic question") -> InboundQuestion:
    return InboundQuestion("wamid." + uuid4().hex, "919000000001", datetime.now(UTC), "text", text)


def test_unknown_sender_and_disabled_binding(
    factory: sessionmaker[Session], config: ChannelConfig
) -> None:
    with factory() as session:
        assert admit(session, config, [replace(question(), sender="919000000099")], []) == []
        assert session.scalar(select(func.count()).select_from(WhatsAppReceipt)) == 0
        stop = question("STOP")
        admit(session, config, [stop], [])
        binding = session.scalar(select(WhatsAppBinding))
        assert binding is not None and not binding.enabled
        ignored = question()
        assert not admit(session, config, [ignored], [])
        assert (
            session.scalar(
                select(WhatsAppReceipt.state).where(
                    WhatsAppReceipt.inbound_message_id == ignored.message_id
                )
            )
            == "ignored"
        )
        admit(session, config, [question("START"), question("hi")], [])
        session.refresh(binding)
        assert binding.enabled and binding.language == "hi"


def test_concurrent_duplicate_admission_and_atomic_claim(
    factory: sessionmaker[Session], config: ChannelConfig
) -> None:
    inbound = question()

    def admission(_: int):
        with factory() as session:
            return admit(session, config, [inbound], [])

    with ThreadPoolExecutor(max_workers=2) as executor:
        admitted = [item for batch in executor.map(admission, [1, 2]) for item in batch]
    assert len(admitted) == 1

    def worker(_: int) -> bool:
        with factory() as session:
            return claim(session, admitted[0].receipt_id) is not None

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sum(executor.map(worker, [1, 2])) == 1
    with factory() as session:
        assert not admit(session, config, [inbound], [])
        assert session.scalar(select(func.count()).select_from(WhatsAppReceipt)) == 1
        original = session.get(WhatsAppReceipt, admitted[0].receipt_id)
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                WhatsAppReceipt(
                    binding_id=original.binding_id,
                    inbound_message_id=inbound.message_id,
                    content_hash="synthetic",
                    kind="text",
                    state="admitted",
                    provider_at=datetime.now(UTC),
                )
            )
            session.flush()


def test_stale_work_is_interrupted_without_replay(
    factory: sessionmaker[Session], config: ChannelConfig
) -> None:
    with factory() as session:
        item = admit(session, config, [question()], [])[0]
        receipt = claim(session, item.receipt_id)
        receipt.received_at = datetime.now(UTC) - timedelta(minutes=20)
        session.add(
            WhatsAppDelivery(
                receipt_id=receipt.id, kind="text", state="sending", created_at=receipt.received_at
            )
        )
        session.commit()
        interrupt_stale(session, before=datetime.now(UTC) - timedelta(minutes=10))
        session.refresh(receipt)
        assert receipt.state == "interrupted"
        assert session.scalar(select(WhatsAppDelivery.state)) == "unknown"
        assert claim(session, receipt.id) is None
        assert not admit(session, config, [item.question], [])


@pytest.mark.parametrize(
    "outcome,expected", [("accepted", "sent"), ("unknown", "unknown"), ("failed", "failed")]
)
def test_send_state_and_no_retry(
    factory: sessionmaker[Session], config: ChannelConfig, outcome: str, expected: str
) -> None:
    class Client:
        calls = 0

        def send(self, *_args, **_kwargs) -> str:
            self.calls += 1
            if outcome == "unknown":
                raise SendUnknown
            if outcome == "failed":
                raise MetaUnavailable
            return "wamid.outbound"

    client = Client()
    with factory() as session:
        item = admit(session, config, [question()], [])[0]
        receipt = claim(session, item.receipt_id)
        send_reply(session, config, client, receipt, item.question, text="synthetic answer")
        assert session.scalar(select(WhatsAppDelivery.state)) == expected
        assert not send_reply(
            session, config, client, receipt, item.question, text="synthetic answer"
        )
        assert client.calls == 1
        if outcome == "accepted":
            status = Status(id="wamid.outbound", status="read", recipient_id="919000000001")
            admit(
                session, config, [], [replace_status(status, "delivered", recipient="919000000099")]
            )
            assert session.scalar(select(WhatsAppDelivery.provider_status)) is None
            admit(session, config, [], [replace_status(status, "sent")])
            admit(session, config, [], [replace_status(status, "failed")])
            assert session.scalar(select(WhatsAppDelivery.provider_status)) == "failed"
            admit(session, config, [], [status])
            admit(session, config, [], [replace_status(status, "sent")])
            assert session.scalar(select(WhatsAppDelivery.provider_status)) == "read"


def replace_status(status: Status, value: str, *, recipient: str = "919000000001") -> Status:
    return status.model_copy(update={"status": value, "recipient_id": recipient})


def test_storage_has_no_content_and_constraints(
    factory: sessionmaker[Session], config: ChannelConfig
) -> None:
    prohibited = {"phone", "sender", "text", "transcript", "audio", "payload", "answer", "body"}
    for model in [WhatsAppBinding, WhatsAppReceipt, WhatsAppDelivery]:
        assert not prohibited.intersection(model.__table__.columns.keys())
    with factory() as session:
        item = admit(session, config, [question()], [])[0]
        receipt = session.get(WhatsAppReceipt, item.receipt_id)
        assert len(receipt.content_hash) == 64
        for invalid in [
            {"state": "raw error"},
            {"error_code": "private provider error"},
            {"language": "unknown"},
        ]:
            with pytest.raises(IntegrityError), session.begin_nested():
                values = {
                    "binding_id": receipt.binding_id,
                    "inbound_message_id": uuid4().hex,
                    "content_hash": "synthetic",
                    "kind": "text",
                    "state": "admitted",
                    "provider_at": datetime.now(UTC),
                    **invalid,
                }
                session.add(WhatsAppReceipt(**values))
                session.flush()


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["text", "audio"])
async def test_concurrent_http_duplicates_run_shared_services_once(
    factory: sessionmaker[Session],
    config: ChannelConfig,
    wa_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    import asyncio
    import hashlib
    import hmac
    import json
    from threading import Lock

    from finboy.main import create_app
    from finboy.services.assistant.models import AssistantAnswer
    from finboy.services.speech.models import SynthesizedAudio, Transcript
    from finboy.services.whatsapp import processor
    from finboy.services.whatsapp.meta import DownloadedAudio
    from httpx import ASGITransport, AsyncClient

    from .conftest import payload

    calls = {"ask": 0, "send": 0, "stt": 0, "tts": 0}
    lock = Lock()

    class Client:
        def __init__(self, _config: ChannelConfig) -> None:
            pass

        def close(self) -> None:
            pass

        def send(self, *_args, **_kwargs) -> str:
            with lock:
                calls["send"] += 1
                return "wamid.outbound." + str(calls["send"])

        def download_audio(self, *_args) -> DownloadedAudio:
            return DownloadedAudio(b"synthetic audio", "audio/ogg")

        def upload_audio(self, _data: bytes) -> str:
            return "12345"

    def answer(*_args, **_kwargs) -> AssistantAnswer:
        with lock:
            calls["ask"] += 1
        return AssistantAnswer(
            intent="synthetic",
            policy="answer",
            display_text="Synthetic answer",
            speech_text="Synthetic answer",
            speech_language="ml",
            facts=[],
            simulation=None,
            evidence_transactions=[],
            warnings=[],
        )

    def stt(**_kwargs) -> Transcript:
        calls["stt"] += 1
        return Transcript(transcript="synthetic question", detected_language="ml")

    def tts(**_kwargs) -> SynthesizedAudio:
        calls["tts"] += 1
        return SynthesizedAudio(b"synthetic mp3")

    monkeypatch.setattr(processor, "MetaClient", Client)
    monkeypatch.setattr(processor.assistant, "answer_question", answer)
    monkeypatch.setattr(processor.speech, "transcribe_audio", stt)
    monkeypatch.setattr(processor.speech, "synthesize_speech", tts)
    settings = wa_settings.model_copy(update={"database_url": Settings().database_url})
    app = create_app(settings)
    raw = json.dumps(payload(kind=kind, message_id="wamid." + uuid4().hex)).encode()
    signature = "sha256=" + hmac.new(config.app_secret.encode(), raw, hashlib.sha256).hexdigest()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            replies = await asyncio.gather(
                *[
                    client.post(
                        "/api/v1/whatsapp/webhook",
                        content=raw,
                        headers={
                            "Content-Type": "application/json",
                            "X-Hub-Signature-256": signature,
                        },
                    )
                    for _ in range(2)
                ]
            )
        assert [reply.status_code for reply in replies] == [200, 200]
        assert calls["ask"] == 1
        assert calls["send"] == (2 if kind == "audio" else 1)
        assert calls["stt"] == calls["tts"] == (1 if kind == "audio" else 0)
        with factory() as session:
            assert session.scalar(select(WhatsAppReceipt.state)) == "completed"
            assert (
                session.scalar(select(func.count()).select_from(WhatsAppDelivery)) == calls["send"]
            )
    finally:
        app.state.engine.dispose()
