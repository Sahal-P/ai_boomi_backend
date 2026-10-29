"""Screenshot capture through real admission, import, ledger and privacy tables.

Meta and the vision model are fakes; the import pipeline runs in rules mode.
"""

import asyncio
import hashlib
import hmac
import importlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime
from threading import Lock
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from finboy.core.config import Settings
from finboy.db.models import AuditEvent, EmailSource, ImportRun, SourceEvent, Transaction, User
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppDelivery, WhatsAppReceipt
from finboy.db.session import build_engine
from finboy.services.imports.locking import IMPORT_LOCK
from finboy.services.imports.runner import create_run, run_import
from finboy.services.ingestion.pipeline import InboundMessage
from finboy.services.ingestion.screenshot import ImageReading
from finboy.services.privacy.delete import delete_imported_data
from finboy.services.whatsapp import capture
from finboy.services.whatsapp.capture import Capture, capture_screenshot
from finboy.services.whatsapp.config import channel_config
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.meta import DownloadedMedia
from pydantic import SecretStr
from sqlalchemy import Engine, Text, cast, delete, func, select, text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

SENT_AT = datetime(2026, 10, 24, 5, 12, tzinfo=UTC)
LINE = "Rs. 500.00 paid to Ravi Kumar via UPI on 24-10-26 10:42, UPI Ref: 612345678901"
USER_MODULES = (
    "finboy.services.imports.runner",
    "finboy.services.privacy.audit",
    "finboy.services.privacy.delete",
    "finboy.services.whatsapp.capture",
    "finboy.services.whatsapp.config",
    "finboy.services.whatsapp.receipts",
)


@pytest.fixture
def household(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Engine, UUID]]:
    settings = Settings()
    engine = build_engine(settings)
    assert settings.environment != "production"
    assert engine.url.host in {"127.0.0.1", "localhost"}
    assert engine.url.database in {
        "finboy_capture",
        "finboy_p5",
        "finboy_ux_api",
        "finboy_test",
        "finboy_pilot",
        "finboy_signup",
    }
    user = uuid4()
    for name in USER_MODULES:
        monkeypatch.setattr(importlib.import_module(name), "LOCAL_USER_ID", user)
    monkeypatch.setenv("FINBOY_EXTRACTION_MODE", "rules")
    with Session(engine) as session, session.begin():
        session.add(User(id=user, display_name="Synthetic screenshot capture test"))
    try:
        yield engine, user
    finally:
        with Session(engine) as session, session.begin():
            delete_imported_data(session)
            session.execute(delete(WhatsAppBinding).where(WhatsAppBinding.user_id == user))
            session.execute(delete(AuditEvent).where(AuditEvent.user_id == user))
            session.execute(delete(ImportRun).where(ImportRun.user_id == user))
            session.execute(delete(User).where(User.id == user))
        engine.dispose()


@pytest.fixture
def meta(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    client = MagicMock()
    client.download_image.return_value = DownloadedMedia(b"synthetic image", "image/png")
    monkeypatch.setattr(capture.screenshot, "read_image", lambda *_args: ImageReading(LINE))
    return client


def screenshot(message_id: str | None = None) -> InboundQuestion:
    return InboundQuestion(
        message_id or "wamid." + uuid4().hex,
        "919000000001",
        SENT_AT,
        "image",
        media_id="5678",
        mime_type="image/png",
    )


def bank_alert(engine: Engine) -> None:
    message = EmailMessage()
    message["From"] = "HDFC Bank <alerts@alerts.hdfcbank.test>"
    message["Subject"] = "UPI transaction alert"
    message["Date"] = format_datetime(SENT_AT)
    # Same shape as the synthetic demo-mailbox UPI alert.
    message.set_content(
        "Dear Arun,\nDebited ₹500.00 to Ravi Kumar on 24-10-26 10:42 IST;\n"
        "A/c XX1234 via UPI; UTR: 612345678901.\n"
    )
    with Session(engine) as session:
        run_id = create_run(session, mode="eml_upload").id
    inbound = InboundMessage("eml_upload", "synthetic-alert-" + uuid4().hex, message.as_bytes())
    run_import(engine, Settings(), run_id, [inbound])


def active_transactions(session: Session, user: UUID) -> list[Transaction]:
    return list(
        session.scalars(
            select(Transaction).where(Transaction.user_id == user, Transaction.status != "merged")
        )
    )


def test_screenshot_becomes_one_household_review_record(household, meta) -> None:
    engine, user = household
    question = screenshot()
    result = capture_screenshot(engine, Settings(), meta, question)
    assert (result.outcome, result.amount_minor, result.merchant) == ("saved", 50000, "Ravi Kumar")
    with Session(engine) as session:
        (source,) = session.scalars(select(EmailSource).where(EmailSource.user_id == user))
        assert (source.source, source.provider_message_id) == (
            "whatsapp_image",
            question.message_id,
        )
        assert source.sender_domain == "whatsapp.invalid"
        assert source.processing_status == "extracted"
        (transaction,) = active_transactions(session, user)
        assert (transaction.status, transaction.dataset) == ("needs_review", "household")
        assert (transaction.amount_minor, transaction.merchant) == (50000, "Ravi Kumar")
        assert result.transaction_id == transaction.id, "the reply's card points at this record"
        assert transaction.occurred_at == datetime.fromisoformat("2026-10-24T10:42:00+05:30")
        assert transaction.reference_id and transaction.reference_id.startswith("H-")
        (run,) = session.scalars(select(ImportRun).where(ImportRun.user_id == user))
        assert (run.mode, run.status, run.transactions_created) == (
            "whatsapp_image",
            "completed",
            1,
        )
        events = session.scalars(
            select(AuditEvent.event_metadata).where(AuditEvent.user_id == user)
        ).all()
        assert events and all(item == {"mode": "whatsapp_image"} for item in events)
        # The raw UPI reference and any image bytes never reach PostgreSQL.
        leaked = session.scalar(
            select(func.count())
            .select_from(SourceEvent)
            .where(
                SourceEvent.user_id == user,
                cast(SourceEvent.evidence, Text).contains("612345678901"),
            )
        )
        assert leaked == 0
    # Retrying the same WhatsApp message adds nothing.
    assert capture_screenshot(engine, Settings(), meta, question).outcome == "already_recorded"
    with Session(engine) as session:
        assert len(active_transactions(session, user)) == 1


@pytest.mark.parametrize("order", ["email_first", "screenshot_first"])
def test_bank_email_and_screenshot_reconcile(household, meta, order: str) -> None:
    engine, user = household
    if order == "email_first":
        bank_alert(engine)
    result = capture_screenshot(engine, Settings(), meta, screenshot())
    if order == "screenshot_first":
        bank_alert(engine)
    assert result.outcome == ("already_recorded" if order == "email_first" else "saved")
    with Session(engine) as session:
        (transaction,) = active_transactions(session, user)
        sources = session.scalars(
            select(EmailSource.source)
            .join(SourceEvent, SourceEvent.email_source_id == EmailSource.id)
            .where(SourceEvent.transaction_id == transaction.id)
        ).all()
        assert sorted(sources) == ["eml_upload", "whatsapp_image"]


def test_privacy_deletion_removes_screenshot_records(household, meta) -> None:
    engine, user = household
    capture_screenshot(engine, Settings(), meta, screenshot())
    with Session(engine) as session, session.begin():
        delete_imported_data(session)
    with Session(engine) as session:
        assert not session.scalars(select(EmailSource).where(EmailSource.user_id == user)).all()
        assert not active_transactions(session, user)


def test_busy_import_is_never_queued(household, meta) -> None:
    engine, user = household
    with Session(engine) as session, session.begin():
        session.add(ImportRun(id=uuid4(), user_id=user, mode="gmail", status="running"))
    with engine.connect() as worker:
        assert worker.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": IMPORT_LOCK})
        try:
            assert capture_screenshot(engine, Settings(), meta, screenshot()) == Capture("busy")
        finally:
            worker.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": IMPORT_LOCK})
    with Session(engine) as session:
        assert not session.scalars(select(EmailSource).where(EmailSource.user_id == user)).all()


@pytest.mark.anyio
async def test_signed_image_webhook_captures_once(
    household, monkeypatch: pytest.MonkeyPatch, wa_settings: Settings
) -> None:
    from finboy.main import create_app
    from finboy.services.whatsapp import processor
    from httpx import ASGITransport, AsyncClient

    from .conftest import payload

    engine, user = household
    calls = {"read": 0, "send": 0}
    lock = Lock()

    class Client:
        def __init__(self, _config) -> None:
            pass

        def close(self) -> None:
            pass

        def download_image(self, *_args) -> DownloadedMedia:
            return DownloadedMedia(b"synthetic image", "image/png")

        def send(self, *_args, **kwargs) -> str:
            assert kwargs["text"].startswith("Saved for review: ₹500 · Ravi Kumar.")
            with lock:
                calls["send"] += 1
                return "wamid.outbound." + str(calls["send"])

    def read(*_args) -> ImageReading:
        with lock:
            calls["read"] += 1
        return ImageReading(LINE)

    monkeypatch.setattr(processor, "MetaClient", Client)
    monkeypatch.setattr(capture.screenshot, "read_image", read)
    settings = wa_settings.model_copy(
        update={
            "database_url": Settings().database_url,
            "whatsapp_sender_allowlist_json": SecretStr(json.dumps({"919000000001": str(user)})),
        }
    )
    config = channel_config(settings)
    app = create_app(settings)
    raw = json.dumps(payload(kind="image", message_id="wamid." + uuid4().hex)).encode()
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
        assert calls == {"read": 1, "send": 1}
        with Session(engine) as session:
            receipt = session.scalars(
                select(WhatsAppReceipt)
                .join(WhatsAppBinding, WhatsAppBinding.id == WhatsAppReceipt.binding_id)
                .where(WhatsAppBinding.user_id == user)
            ).one()
            assert (receipt.kind, receipt.state, receipt.error_code) == ("image", "completed", None)
            delivery = session.scalars(
                select(WhatsAppDelivery).where(WhatsAppDelivery.receipt_id == receipt.id)
            ).one()
            assert (delivery.kind, delivery.state) == ("text", "sent")
            (transaction,) = active_transactions(session, user)
            assert transaction.status == "needs_review"
    finally:
        app.state.engine.dispose()
