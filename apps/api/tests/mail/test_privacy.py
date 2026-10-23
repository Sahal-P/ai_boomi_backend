from datetime import date
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from finboy.core.clock import now_ist
from finboy.core.config import LOCAL_USER_ID
from finboy.db.models import (
    AuditEvent,
    Commitment,
    EmailSource,
    ExtractionCache,
    ImportRun,
    MailConnection,
    SourceEvent,
    Transaction,
    TransactionRevision,
)
from finboy.services.mail.google import GoogleClient
from finboy.services.mail.oauth import OAuthConfig
from finboy.services.mail.security import encrypt
from finboy.services.privacy.audit import audit
from finboy.services.privacy.delete import delete_imported_data
from sqlalchemy import func, select


def new_connection(session, settings, suffix="a"):
    connection = MailConnection(
        id=uuid4(),
        user_id=LOCAL_USER_ID,
        provider="gmail",
        account_email_masked="d***@***.test",
        account_email_sha256=suffix * 64,
        encrypted_refresh_token=encrypt(
            settings.token_encryption_key.get_secret_value(), "SENSITIVE_REFRESH"
        ),
        scopes=[],
        status="active",
        connected_at=now_ist(),
    )
    session.add(connection)
    session.flush()
    return connection


@pytest.mark.anyio
@pytest.mark.parametrize("google_status,expected,revoked", [(200, 200, True), (503, 503, False)])
async def test_disconnect_revokes_then_wipes(
    mail_app, mail_factory, mail_settings, monkeypatch, google_status, expected, revoked, capsys
):
    with mail_factory.begin() as session:
        connection_id = new_connection(session, mail_settings).id
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(google_status, json={"error": "SENSITIVE_DETAILS"})

    monkeypatch.setattr(
        OAuthConfig,
        "google",
        lambda config: GoogleClient(
            config.client_id,
            config.client_secret,
            config.redirect_uri,
            sleep=lambda _: None,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url="http://test"
    ) as client:
        response = await client.delete(f"/api/v1/connections/{connection_id}")
        assert response.status_code == expected
        events = await client.get("/api/v1/privacy/audit-events")
    with mail_factory() as session:
        connection = session.get(MailConnection, connection_id)
        assert (connection.status == "revoked") is revoked
        assert (connection.encrypted_refresh_token is None) is revoked
        assert session.scalar(select(AuditEvent.event_type)) == (
            "gmail.revoked" if revoked else "gmail.revoke_failed"
        )
    assert calls[0].content == b"token=SENSITIVE_REFRESH"
    output = response.text + events.text + capsys.readouterr().out
    assert "SENSITIVE" not in output


@pytest.mark.anyio
async def test_pause_resume_sync_and_user_scoping(
    mail_app, mail_factory, mail_settings, monkeypatch
):
    with mail_factory.begin() as session:
        connection_id = new_connection(session, mail_settings).id
    scheduled = []
    monkeypatch.setattr(
        "finboy.api.v1.connections.run_import", lambda *args: scheduled.append(args)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url="http://test"
    ) as client:
        prefix = f"/api/v1/connections/{connection_id}"
        assert (await client.post(prefix + "/pause")).status_code == 200
        assert (await client.post(prefix + "/sync")).status_code == 409
        assert (await client.post(prefix + "/resume")).status_code == 200
        sync = await client.post(prefix + "/sync")
        assert sync.status_code == 202
        assert len(scheduled) == 1
        assert (await client.post(f"/api/v1/connections/{uuid4()}/sync")).status_code == 404
        assert (await client.post(prefix + "/sync")).status_code == 409


def make_transaction(session):
    transaction = Transaction(
        id=uuid4(),
        user_id=LOCAL_USER_ID,
        direction="out",
        kind="purchase",
        amount_minor=100,
        currency="INR",
        merchant="Synthetic",
        category="other",
        occurred_at=now_ist(),
        confidence=Decimal("0.900"),
        confidence_factors={},
        status="confirmed",
        fingerprint=uuid4().hex,
        user_locked_fields=[],
    )
    session.add(transaction)
    session.flush()
    return transaction


def make_source(session, connection, transaction):
    run = ImportRun(
        id=uuid4(),
        user_id=LOCAL_USER_ID,
        mode="gmail",
        status="completed",
        mail_connection_id=connection.id,
    )
    session.add(run)
    session.flush()
    source = EmailSource(
        id=uuid4(),
        user_id=LOCAL_USER_ID,
        import_run_id=run.id,
        mail_connection_id=connection.id,
        source="gmail",
        provider_message_id=uuid4().hex,
        content_sha256="a" * 64,
        sender_domain="example.test",
        subject_sha256="b" * 64,
        received_at=now_ist(),
        classification="bank_alert",
        processing_status="extracted",
    )
    session.add(source)
    session.flush()
    source_event = SourceEvent(
        id=uuid4(),
        user_id=LOCAL_USER_ID,
        email_source_id=source.id,
        transaction_id=transaction.id,
        event_type="debit",
        amount_minor=100,
        currency="INR",
        extraction_method="rule",
        extractor_id="test",
        evidence={},
        field_confidence={},
    )
    session.add(source_event)
    session.flush()
    return source_event


def exercise_deletion(session, settings):
    audit_count = session.scalar(select(func.count()).select_from(AuditEvent))
    first, second = new_connection(session, settings), new_connection(session, settings, "b")
    shared, sole, manual, linked = [make_transaction(session) for _ in range(4)]
    transaction_ids = [shared.id, sole.id, manual.id, linked.id]
    linked.linked_transaction_id = sole.id
    make_source(session, first, shared)
    remaining_event = make_source(session, second, shared)
    deleted_event = make_source(session, first, sole)
    make_source(session, second, linked)
    for source_event in (deleted_event, remaining_event):
        session.add(
            Commitment(
                id=uuid4(),
                user_id=LOCAL_USER_ID,
                kind="bill",
                label="Synthetic",
                amount_minor=100,
                currency="INR",
                due_date=date(2026, 10, 30),
                status="upcoming",
                source_event_id=source_event.id,
                paid_transaction_id=sole.id,
                confidence=Decimal("0.9"),
            )
        )
    session.add(
        TransactionRevision(
            id=uuid4(),
            transaction_id=sole.id,
            field="category",
            old_value="other",
            new_value="food_dining",
            changed_by="user",
            reason="test",
        )
    )
    session.add(ExtractionCache(id=uuid4(), cache_key="test", result={"private": "synthetic"}))
    audit(session, "gmail.connected", "connection", first.id)
    session.flush()
    delete_imported_data(session, connection_id=first.id)
    session.flush()
    session.expire_all()
    assert set(
        session.scalars(select(Transaction.id).where(Transaction.id.in_(transaction_ids)))
    ) == {shared.id, manual.id, linked.id}
    assert (
        session.scalar(
            select(func.count())
            .select_from(EmailSource)
            .where(EmailSource.mail_connection_id.in_([first.id, second.id]))
        )
        == 2
    )
    assert (
        session.scalar(
            select(func.count())
            .select_from(Commitment)
            .where(Commitment.source_event_id.in_([deleted_event.id, remaining_event.id]))
        )
        == 1
    )
    assert (
        session.scalar(
            select(Commitment.paid_transaction_id).where(
                Commitment.source_event_id == remaining_event.id
            )
        )
        is None
    )
    assert session.get(Transaction, linked.id).linked_transaction_id is None
    assert (
        session.scalar(
            select(func.count())
            .select_from(TransactionRevision)
            .where(TransactionRevision.transaction_id == sole.id)
        )
        == 0
    )
    assert session.scalar(select(func.count()).select_from(ExtractionCache)) == 0
    assert session.scalar(select(func.count()).select_from(AuditEvent)) == audit_count + 2
    delete_imported_data(session)
    session.flush()
    assert list(
        session.scalars(select(Transaction.id).where(Transaction.id.in_(transaction_ids)))
    ) == [manual.id]
    assert session.scalar(select(func.count()).select_from(EmailSource)) == 0
    assert (
        session.scalar(
            select(func.count())
            .select_from(Commitment)
            .where(Commitment.source_event_id.in_([deleted_event.id, remaining_event.id]))
        )
        == 0
    )
    assert session.scalar(select(func.count()).select_from(AuditEvent)) == audit_count + 3


def test_delete_preserves_shared_sources_manual_records_and_audit(mail_factory, mail_settings):
    with mail_factory.begin() as session:
        exercise_deletion(session, mail_settings)


@pytest.mark.anyio
async def test_disconnect_option_deletes_only_its_sources(
    mail_app,
    mail_factory,
    mail_settings,
    monkeypatch,
):
    with mail_factory.begin() as session:
        first, second = (
            new_connection(session, mail_settings),
            new_connection(session, mail_settings, "b"),
        )
        shared, sole = make_transaction(session), make_transaction(session)
        make_source(session, first, shared)
        make_source(session, second, shared)
        make_source(session, first, sole)
        connection_id, shared_id, sole_id = first.id, shared.id, sole.id
    monkeypatch.setattr(
        OAuthConfig,
        "google",
        lambda config: GoogleClient(
            config.client_id,
            config.client_secret,
            config.redirect_uri,
            client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200))),
        ),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url="http://test"
    ) as client:
        response = await client.delete(f"/api/v1/connections/{connection_id}?delete_data=true")
        assert response.status_code == 200
    with mail_factory() as session:
        assert session.get(Transaction, shared_id) is not None
        assert session.get(Transaction, sole_id) is None
        assert session.get(MailConnection, connection_id).encrypted_refresh_token is None
        assert set(session.scalars(select(AuditEvent.event_type))) == {
            "gmail.revoked",
            "data.deleted",
        }


@pytest.mark.integration
def test_postgres_privacy_foreign_keys_and_import_lock(mail_settings):
    from finboy.core.config import Settings
    from finboy.db.session import build_engine
    from finboy.services.imports.locking import import_lock
    from finboy.services.mail.security import MailError
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session

    settings = Settings()
    url = make_url(settings.database_url.get_secret_value())
    if settings.environment == "production" or url.host not in {"127.0.0.1", "localhost"}:
        pytest.fail("Mail integration tests require a local disposable database")
    engine = build_engine(settings)
    try:
        with (
            import_lock(engine),
            pytest.raises(MailError, match="import_busy"),
            import_lock(engine),
        ):
            pass
        with engine.connect() as connection, connection.begin() as transaction:
            with Session(bind=connection) as session:
                exercise_deletion(session, mail_settings)
            transaction.rollback()
    finally:
        engine.dispose()


def test_audit_rejects_unknown_events_and_drops_sensitive_fields(mail_factory):
    with mail_factory() as session:
        audit(
            session,
            "import.started",
            "import",
            uuid4(),
            mode="demo_mailbox",
            token="SENSITIVE_TOKEN",
            email="private@example.test",
            result="invalid",
        )
        session.flush()
        assert session.scalar(select(AuditEvent)).event_metadata == {"mode": "demo_mailbox"}
        with pytest.raises(ValueError):
            audit(session, "SENSITIVE_TOKEN", "user", LOCAL_USER_ID)


@pytest.mark.anyio
async def test_privacy_delete_endpoint_keeps_audit(mail_app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url="http://test"
    ) as client:
        assert (await client.delete("/api/v1/privacy/imported-data")).status_code == 200
        events = (await client.get("/api/v1/privacy/audit-events")).json()
        assert events[0]["event_type"] == "data.deleted"
        assert "event_metadata" not in events[0]


def test_scoped_delete_preserves_obligation_with_another_source(mail_factory, mail_settings):
    with mail_factory.begin() as session:
        first = new_connection(session, mail_settings)
        second = new_connection(session, mail_settings, "b")
        transaction = make_transaction(session)
        original = make_source(session, first, transaction)
        replacement = make_source(session, second, transaction)
        for event in (original, replacement):
            event.transaction_id = None
            event.event_type = "bill_due"
            event.due_date = date(2026, 10, 30)
            event.merchant_normalized = "Synthetic bill"
        commitment = Commitment(
            id=uuid4(),
            user_id=LOCAL_USER_ID,
            kind="bill",
            label="Synthetic bill",
            amount_minor=100,
            currency="INR",
            due_date=date(2026, 10, 30),
            status="upcoming",
            source_event_id=original.id,
            confidence=Decimal("0.9"),
        )
        session.add(commitment)
        session.flush()
        delete_imported_data(session, connection_id=first.id)
        session.flush()
        assert commitment.source_event_id == replacement.id
        assert session.get(Commitment, commitment.id) is not None
        assert session.get(SourceEvent, original.id) is None
        delete_imported_data(session, connection_id=second.id)
        session.flush()
        assert session.get(Commitment, commitment.id) is None
