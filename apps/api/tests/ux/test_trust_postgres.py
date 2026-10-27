"""Synthetic high-risk journeys against only the assigned disposable PostgreSQL."""

import importlib
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from finboy.api.deps import current_user_id
from finboy.core.clock import IST
from finboy.core.config import Settings
from finboy.db.models import (
    AuditEvent,
    Commitment,
    EmailSource,
    ImportRun,
    MailConnection,
    OAuthState,
    SourceEvent,
    Transaction,
    TransactionRevision,
    User,
)
from finboy.db.models.ledger import ReviewDecision
from finboy.db.session import build_engine, get_session
from finboy.main import create_app
from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration


@pytest.fixture
def ux(monkeypatch):
    settings = Settings()
    engine = build_engine(settings)
    assert settings.environment != "production"
    assert engine.url.host in {"127.0.0.1", "localhost"}
    assert engine.url.database in {
        "finboy_ux_api",
        "finboy_ux_ui",
        "finboy_capture",
        "finboy_pilot",
        "finboy_signup",
    }
    factory = sessionmaker(engine, expire_on_commit=False)
    uid = uuid4()
    for name in (
        "finboy.api.v1.imports",
        "finboy.api.v1.money",
        "finboy.api.v1.transactions",
        "finboy.api.v1.privacy",
        "finboy.api.v1.connections",
        "finboy.api.v1.assistant",
        "finboy.services.imports.runner",
        "finboy.services.privacy.delete",
        "finboy.services.privacy.audit",
    ):
        module = importlib.import_module(name)
        if hasattr(module, "LOCAL_USER_ID"):
            monkeypatch.setattr(module, "LOCAL_USER_ID", uid)
    monkeypatch.setenv("FINBOY_EXTRACTION_MODE", "rules")
    monkeypatch.setenv("DEMO_TODAY", "2026-10-24")
    with factory.begin() as session:
        session.add(User(id=uid, display_name="Synthetic UX acceptance"))
    app = create_app(settings)

    def dependency():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = dependency
    app.dependency_overrides[current_user_id] = lambda: uid
    with TestClient(app) as client:
        yield client, factory, uid
    with factory.begin() as session:
        for model in (
            ReviewDecision,
            Commitment,
            TransactionRevision,
            SourceEvent,
            Transaction,
            EmailSource,
            AuditEvent,
            ImportRun,
            OAuthState,
            MailConnection,
            User,
        ):
            condition = (
                model.transaction_id.in_(select(Transaction.id).where(Transaction.user_id == uid))
                if model is TransactionRevision
                else (model.id if model is User else model.user_id) == uid
            )
            session.execute(delete(model).where(condition))
    engine.dispose()


def tx(session, uid, **values):
    row = Transaction(
        user_id=uid,
        dataset="household",
        direction="out",
        kind="purchase",
        amount_minor=10000,
        currency="INR",
        merchant="Sample Bookshop",
        category="shopping",
        occurred_at=datetime(2026, 10, 24, 10, tzinfo=IST),
        confidence=Decimal("0.800"),
        confidence_factors={},
        status="needs_review",
        review_reason="low_confidence",
        fingerprint=uuid4().hex,
        user_locked_fields=[],
    )
    for key, value in values.items():
        setattr(row, key, value)
    session.add(row)
    session.flush()
    return row


def source(session, uid, transaction, *, mode="eml_upload", proof=True):
    run = ImportRun(
        user_id=uid,
        mode=mode,
        status="completed",
        started_at=datetime(2026, 10, 24, tzinfo=IST),
        finished_at=datetime(2026, 10, 24, 1, tzinfo=IST),
    )
    session.add(run)
    session.flush()
    email = EmailSource(
        user_id=uid,
        import_run_id=run.id,
        source=mode,
        provider_message_id=uuid4().hex,
        content_sha256="a" * 64,
        sender_domain="example.test",
        subject_sha256="b" * 64,
        received_at=datetime(2026, 10, 24, tzinfo=IST),
        classification="bank_alert",
        processing_status="extracted",
    )
    session.add(email)
    session.flush()
    event = SourceEvent(
        user_id=uid,
        email_source_id=email.id,
        transaction_id=transaction.id,
        origin_transaction_id=transaction.id,
        event_type="debit",
        amount_minor=transaction.amount_minor,
        currency="INR",
        merchant_raw="Sample Bookshop",
        merchant_normalized=transaction.merchant,
        occurred_at=transaction.occurred_at,
        extraction_method="rule",
        extractor_id="synthetic",
        evidence={"payment_proof": "debited"} if proof else {},
        field_confidence={"amount_minor": 1, "merchant": 1, "occurred_at": 1},
    )
    session.add(event)
    session.flush()
    return email, event


def version(client):
    return client.get("/api/v1/money/summary").json()["data_version"]


def test_demo_and_mixed_scope_never_change_household_facts(ux):
    client, factory, uid = ux
    with factory.begin() as session:
        tx(session, uid, status="confirmed", review_reason=None, amount_minor=50000)
        demo = tx(session, uid, dataset="demo", status="confirmed", amount_minor=999999)
        mixed = tx(session, uid, dataset="quarantined", status="confirmed", amount_minor=888888)
        session.add(
            Commitment(
                user_id=uid,
                dataset="demo",
                kind="bill",
                label="Sample only",
                amount_minor=777777,
                currency="INR",
                due_date=date(2026, 10, 23),
                status="upcoming",
                confidence=Decimal(".9"),
            )
        )
        demo_id, mixed_id = demo.id, mixed.id
    before = client.get("/api/v1/money/summary").json()
    assert before["confirmed_outflows_minor"] == 50000
    assert before["coverage"]["quarantined_count"] == 1
    for _ in range(2):
        sample = client.get("/api/v1/demo")
        assert sample.status_code == 200 and sample.json()["read_only"]
    assert client.post("/api/v1/imports/demo").status_code == 409
    assert client.get("/api/v1/money/summary").json() == before
    assert client.get(f"/api/v1/transactions/{demo_id}").status_code == 404
    assert (
        client.post(
            f"/api/v1/transactions/{mixed_id}/decisions",
            json={"expected_version": before["data_version"], "action": "confirm"},
        ).json()["error"]["code"]
        == "quarantined_record"
    )
    page = client.get("/api/v1/transactions/page?scope=all").json()
    assert page["total"] == 1
    answer = client.post(
        "/api/v1/assistant/ask", json={"text": "How much did I spend this month?"}
    ).json()
    assert answer["facts"][0]["amount_minor"] == 50000


def test_unpaid_overdue_uncertain_obligation_is_inspectable_and_repairable(ux):
    client, factory, uid = ux
    with factory.begin() as session:
        tx(
            session,
            uid,
            status="confirmed",
            direction="in",
            kind="salary",
            category="salary",
            amount_minor=1000000,
            review_reason=None,
        )
        bill = Commitment(
            user_id=uid,
            kind="bill",
            label="Synthetic bill",
            amount_minor=100000,
            currency="INR",
            due_date=date(2026, 9, 30),
            status="upcoming",
            confidence=Decimal(".4"),
        )
        session.add(bill)
        session.flush()
        bid = bill.id
    result = client.get("/api/v1/money/summary").json()
    assert result["estimated_unallocated_minor"] == 900000
    assert result["overdue_commitments_minor"] == result["uncertain_commitments_minor"] == 100000
    detail = client.get(f"/api/v1/money/obligations/{bid}").json()
    assert detail["commitment"]["liability_state"] == "overdue"
    resolved = client.patch(
        f"/api/v1/money/obligations/{bid}",
        json={"expected_version": detail["version"], "status": "paid"},
    )
    assert resolved.status_code == 200
    assert client.get("/api/v1/money/summary").json()["estimated_unallocated_minor"] == 1000000
    stale = client.patch(
        f"/api/v1/money/obligations/{bid}",
        json={"expected_version": detail["version"], "status": "dismissed"},
    )
    assert stale.status_code == 409


def test_merge_preview_confirmed_target_undo_and_stale_rejection(ux):
    client, factory, uid = ux
    with factory.begin() as session:
        keep = tx(session, uid, status="confirmed", review_reason=None)
        pending = tx(session, uid)
        source(session, uid, keep)
        source(session, uid, pending)
        kid, pid = keep.id, pending.id
    candidates = client.get(f"/api/v1/transactions/{pid}/merge-candidates").json()
    assert str(kid) in [row["id"] for row in candidates["items"]]
    original = version(client)
    body = {"expected_version": original, "action": "merge", "keep_id": str(kid)}
    preview = client.post(f"/api/v1/transactions/{pid}/decision-preview", json=body)
    assert preview.status_code == 200
    assert preview.json()["source_count"] == 1
    assert version(client) == original
    merged = client.post(f"/api/v1/transactions/{pid}/decisions", json=body)
    assert merged.status_code == 200
    result = merged.json()
    assert client.get(f"/api/v1/transactions/{kid}").json()["transaction"]["source_count"] == 2
    assert client.post(f"/api/v1/transactions/{pid}/decisions", json=body).status_code == 409
    undone = client.post(
        f"/api/v1/transactions/{pid}/decisions/{result['decision_id']}/undo",
        json={"expected_version": result["data_version"]},
    )
    assert undone.status_code == 200
    assert undone.json()["detail"]["transaction"]["status"] == "needs_review"
    assert client.get(f"/api/v1/transactions/{kid}").json()["transaction"]["source_count"] == 1
    rejected = client.post(
        f"/api/v1/transactions/{pid}/decisions",
        json={"expected_version": version(client), "action": "reject"},
    ).json()
    reopened = client.post(
        f"/api/v1/transactions/{pid}/decisions",
        json={"expected_version": rejected["data_version"], "action": "reopen"},
    )
    assert reopened.status_code == 200
    conflict = client.post(
        f"/api/v1/transactions/{pid}/decisions/{rejected['decision_id']}/undo",
        json={"expected_version": reopened.json()["data_version"]},
    )
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "decision_conflict"


def test_correction_and_confirmation_are_atomic_and_undo_retains_history(ux):
    client, factory, uid = ux
    with factory.begin() as session:
        row = tx(session, uid)
        source(session, uid, row, proof=False)
        rid = row.id
    body = {
        "expected_version": version(client),
        "action": "confirm",
        "correction": {
            "occurred_at": "2026-09-30T23:00:00+05:30",
            "direction": "in",
            "kind": "refund",
            "amount_minor": 5000,
        },
    }
    result = client.post(f"/api/v1/transactions/{rid}/decisions", json=body)
    assert result.status_code == 200
    value = result.json()
    assert value["detail"]["transaction"]["kind"] == "refund"
    assert value["detail"]["transaction"]["status"] == "confirmed"
    assert client.get("/api/v1/transactions/page?scope=unresolved").json()["total"] == 0
    undone = client.post(
        f"/api/v1/transactions/{rid}/decisions/{value['decision_id']}/undo",
        json={"expected_version": value["data_version"]},
    )
    assert undone.status_code == 200
    assert len(undone.json()["detail"]["revisions"]) > len(value["detail"]["revisions"])


def test_history_201_and_prior_month_reviews_and_filtered_empty(ux):
    client, factory, uid = ux
    with factory.begin() as session:
        for i in range(201):
            tx(session, uid, occurred_at=datetime(2026, 9, 1, tzinfo=IST) + timedelta(minutes=i))
    first = client.get("/api/v1/transactions/page?scope=unresolved&limit=200").json()
    assert len(first["items"]) == 200 and first["total"] == first["unresolved_total"] == 201
    second = client.get(
        f"/api/v1/transactions/page?scope=unresolved&limit=200&offset=200&data_version={first['data_version']}"
    ).json()
    assert len(second["items"]) == 1 and second["next_offset"] is None
    assert second["items"][0]["id"] not in {row["id"] for row in first["items"]}
    empty = client.get("/api/v1/transactions/page?scope=unresolved&q=does-not-match").json()
    assert empty["total"] == 0 and empty["unresolved_total"] == 201


def test_merchant_totals_and_income_evidence_use_all_contributors(ux):
    client, factory, uid = ux
    with factory.begin() as session:
        salary = tx(
            session,
            uid,
            status="confirmed",
            review_reason=None,
            direction="in",
            kind="salary",
            category="salary",
            amount_minor=1000000,
            occurred_at=datetime(2026, 10, 1, tzinfo=IST),
        )
        salary_id = salary.id
        for _ in range(15):
            tx(
                session,
                uid,
                status="confirmed",
                review_reason=None,
                merchant="Amazon",
                amount_minor=10000,
            )
        tx(
            session,
            uid,
            status="confirmed",
            review_reason=None,
            direction="in",
            kind="refund",
            merchant="Amazon",
            amount_minor=25000,
        )
        tx(
            session,
            uid,
            status="confirmed",
            review_reason=None,
            kind="transfer",
            merchant="Amazon",
            amount_minor=999999,
        )
    result = client.post(
        "/api/v1/assistant/ask",
        json={"text": "How much did I spend on Amazon this month?", "display_style": "hi"},
    ).json()
    facts = {f["key"]: f["amount_minor"] for f in result["facts"]}
    assert (
        facts["gross_spending"] == 150000
        and facts["refunds"] == 25000
        and facts["net_spending"] == 125000
    )
    assert result["evidence_total"] == 16 and result["evidence_sampled"] is True
    assert len(result["evidence_transactions"]) == 10
    assert (
        result["facts"][0]["label"] != "Gross Spending"
        and result["warning_labels"]["incomplete_coverage"]
    )
    income = client.post(
        "/api/v1/assistant/ask", json={"text": "What was my income this month?"}
    ).json()
    assert [row["id"] for row in income["evidence_transactions"]] == [str(salary_id)]
    today = client.post(
        "/api/v1/assistant/ask", json={"text": "How much did I spend today?"}
    ).json()
    assert today["resolved_period"]["start"] == today["resolved_period"]["end"] == "2026-10-24"
    unsupported = client.post(
        "/api/v1/assistant/ask", json={"text": "How much did I spend last week?"}
    ).json()
    assert (
        unsupported["policy"] == "clarify"
        and "period" in unsupported["display_text"]
        and "rupee amount" not in unsupported["display_text"]
    )


def test_deletion_preview_and_explicit_export_preserve_shared_records(ux):
    client, factory, uid = ux
    with factory.begin() as session:
        row = tx(
            session,
            uid,
            status="confirmed",
            review_reason=None,
            reference_id="PRIVATE_REFERENCE",
            account_last4="1234",
            payment_instrument="PRIVATE_INSTRUMENT",
        )
        source(session, uid, row)
    current = version(client)
    preview = client.post("/api/v1/privacy/deletion-preview", json={}).json()
    assert preview["removed_transaction_count"] == 1 and preview["backup_retention_days"] == 7
    exported = client.post("/api/v1/privacy/export", json={"expected_version": current})
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    assert "PRIVATE_REFERENCE" not in exported.text and "PRIVATE_INSTRUMENT" not in exported.text
    assert "evidence" not in exported.json()["transactions"][0]
    assert "account_last4" not in exported.json()["transactions"][0]
    with factory.begin() as session:
        tx(session, uid)
    conflict = client.post("/api/v1/privacy/delete", json={"expected_version": preview["version"]})
    assert conflict.status_code == 409


def test_failed_upload_recovery_keeps_source_identity_and_successful_dedupe(ux, monkeypatch):
    from finboy.services.imports.files import DEMO_DIRECTORY
    from finboy.services.ingestion import pipeline

    client, factory, uid = ux
    first = (DEMO_DIRECTORY / "12-amazon799.eml").read_bytes()
    second = (DEMO_DIRECTORY / "13-bookshop.eml").read_bytes()
    original = pipeline._prepare
    fail = [True]

    def prepare(factory, inbound, settings):
        if inbound.raw_rfc822 == first and fail[0]:
            fail[0] = False
            return None
        return original(factory, inbound, settings)

    monkeypatch.setattr(pipeline, "_prepare", prepare)
    files = [
        ("files", ("one.eml", first, "message/rfc822")),
        ("files", ("two.eml", second, "message/rfc822")),
    ]
    started = client.post("/api/v1/imports/eml", files=files)
    assert started.status_code == 202
    rid = started.json()["import_run_id"]
    run = client.get(f"/api/v1/imports/{rid}").json()
    assert run["outcome"] == "partial" and run["failed"] == 1 and run["transactions_created"] == 1
    issue = client.get(f"/api/v1/imports/{rid}/issues").json()["items"][0]
    assert (
        issue["reason"] == "extraction_failed"
        and issue["retry_strategy"] == "select_original_files"
    )
    assert (
        client.post(
            f"/api/v1/imports/{rid}/retry", json={"expected_version": version(client)}
        ).json()["error"]["code"]
        == "original_files_required"
    )
    again = client.post("/api/v1/imports/eml", files=files)
    newrun = client.get("/api/v1/imports/" + again.json()["import_run_id"]).json()
    assert newrun["outcome"] == "complete" and newrun["transactions_created"] == 1
    assert newrun["events_extracted"] == 1
    assert client.get(f"/api/v1/imports/{rid}/issues").json()["total"] == 0
    with factory() as session:
        assert session.get(EmailSource, UUID(issue["source_id"])).attempts == 2
        assert (
            session.scalar(
                select(func.count()).select_from(EmailSource).where(EmailSource.user_id == uid)
            )
            == 2
        )
        assert (
            session.scalar(
                select(func.count()).select_from(Transaction).where(Transaction.user_id == uid)
            )
            == 2
        )


def test_gmail_retry_refetches_only_failed_sources_and_cap_continuation_is_encrypted(
    ux, monkeypatch
):
    import base64

    import httpx
    from cryptography.fernet import Fernet
    from finboy.services.imports.files import DEMO_DIRECTORY
    from finboy.services.ingestion import pipeline
    from finboy.services.mail import fetch
    from finboy.services.mail.google import READ_SCOPE, GoogleClient
    from finboy.services.mail.oauth import OAuthConfig
    from finboy.services.mail.security import encrypt
    from pydantic import SecretStr

    client, factory, uid = ux
    settings = client.app.state.settings.model_copy(
        update={
            "web_app_url": "http://127.0.0.1:3031",
            "google_oauth_client_id": "synthetic-client",
            "google_oauth_client_secret": SecretStr("synthetic-secret"),
            "google_oauth_redirect_uri": "http://127.0.0.1:8000/api/v1/connections/gmail/callback",
            "token_encryption_key": SecretStr(Fernet.generate_key().decode()),
        }
    )
    client.app.state.settings = settings
    with factory.begin() as session:
        connection = MailConnection(
            user_id=uid,
            provider="gmail",
            account_email_masked="s***@***.test",
            account_email_sha256="c" * 64,
            encrypted_refresh_token=encrypt(
                settings.token_encryption_key.get_secret_value(), "synthetic-refresh"
            ),
            scopes=[READ_SCOPE],
            status="active",
        )
        session.add(connection)
        session.flush()
        cid = connection.id
    raws = {
        "a": (DEMO_DIRECTORY / "12-amazon799.eml").read_bytes(),
        "b": (DEMO_DIRECTORY / "13-bookshop.eml").read_bytes(),
        "c": (DEMO_DIRECTORY / "20-music.eml").read_bytes(),
    }
    calls = []

    def handle(request):
        calls.append((request.url.path, dict(request.url.params)))
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "synthetic-access"})
        if request.url.path.endswith("/messages"):
            return httpx.Response(
                200,
                json={"messages": [{"id": "c"}]}
                if request.url.params.get("pageToken")
                else {
                    "messages": [{"id": "a"}, {"id": "b"}],
                    "nextPageToken": "private-continuation",
                },
            )
        if request.url.params.get("format") == "metadata":
            return httpx.Response(200, json={"payload": {}})
        return httpx.Response(
            200,
            json={
                "raw": base64.urlsafe_b64encode(raws[request.url.path.rsplit("/", 1)[-1]]).decode()
            },
        )

    monkeypatch.setattr(
        OAuthConfig,
        "google",
        lambda conf: GoogleClient(
            conf.client_id,
            conf.client_secret,
            conf.redirect_uri,
            client=httpx.Client(transport=httpx.MockTransport(handle)),
        ),
    )
    monkeypatch.setattr(fetch, "MAX_CANDIDATES", 2)
    original = pipeline._prepare
    fail = [True]

    def prepare(factory, inbound, settings):
        if inbound.provider_message_id == "a" and fail[0]:
            fail[0] = False
            return None
        return original(factory, inbound, settings)

    monkeypatch.setattr(pipeline, "_prepare", prepare)
    started = client.post(f"/api/v1/connections/{cid}/sync")
    assert started.status_code == 202
    rid = started.json()["import_run_id"]
    run = client.get(f"/api/v1/imports/{rid}").json()
    assert run["outcome"] == "partial" and run["can_continue"] and run["truncated"]
    assert "private-continuation" not in str(run)
    issue = client.get(f"/api/v1/imports/{rid}/issues").json()["items"][0]
    calls.clear()
    retry = client.post(
        f"/api/v1/imports/{rid}/retry",
        json={"expected_version": version(client), "source_ids": [issue["source_id"]]},
    )
    assert retry.status_code == 202
    retried = client.get("/api/v1/imports/" + retry.json()["import_run_id"]).json()
    assert retried["transactions_created"] == 1 and retried["failed"] == 0
    assert not any(path.endswith("/messages") or path.endswith("/b") for path, _ in calls)
    calls.clear()
    continued = client.post(
        f"/api/v1/imports/{rid}/continue", json={"expected_version": version(client)}
    )
    assert continued.status_code == 202
    final = client.get("/api/v1/imports/" + continued.json()["import_run_id"]).json()
    assert (
        final["outcome"] == "complete"
        and final["transactions_created"] == 1
        and not final["truncated"]
    )
    assert any(params.get("pageToken") == "private-continuation" for _, params in calls)
    assert final["window_start"] == run["window_start"] and final["window_end"] == run["window_end"]


def test_interruption_cancel_and_pause_do_not_promise_resume(ux, monkeypatch):
    from finboy.core.clock import now_ist
    from finboy.services.imports.files import DEMO_DIRECTORY, parse_eml
    from finboy.services.imports.runner import create_run, run_import
    from finboy.services.ingestion import pipeline

    client, factory, uid = ux
    with factory.begin() as session:
        abandoned = ImportRun(
            user_id=uid,
            mode="eml_upload",
            status="running",
            started_at=now_ist() - timedelta(minutes=2),
        )
        session.add(abandoned)
        session.flush()
        aid = abandoned.id
    interrupted = client.get(f"/api/v1/imports/{aid}").json()
    assert (
        interrupted["outcome"] == "interrupted"
        and interrupted["retry_strategy"] == "select_original_files"
    )
    with factory() as session:
        run = create_run(session, mode="eml_upload")
        rid = run.id
    queued = client.post(
        f"/api/v1/imports/{rid}/cancel", json={"expected_version": version(client)}
    )
    assert queued.status_code == 200 and queued.json()["outcome"] == "cancelled"
    messages = [
        parse_eml((DEMO_DIRECTORY / name).read_bytes())
        for name in ["12-amazon799.eml", "13-bookshop.eml"]
    ]
    with factory() as session:
        running = create_run(session, mode="eml_upload")
        running_id = running.id
    real = pipeline._persist_message
    count = [0]

    def persist(session, **kwargs):
        result = real(session, **kwargs)
        count[0] += 1
        if count[0] == 1:
            row = session.get(ImportRun, running_id)
            row.cancel_requested = True
        return result

    monkeypatch.setattr(pipeline, "_persist_message", persist)
    run_import(factory.kw["bind"], client.app.state.settings, running_id, messages)
    cancelled = client.get(f"/api/v1/imports/{running_id}").json()
    assert cancelled["outcome"] == "cancelled"
    assert cancelled["emails_processed"] == cancelled["transactions_created"] == 1
    assert count[0] == 1


def test_shared_source_preview_delete_and_task_outcomes(ux):
    client, factory, uid = ux
    with factory.begin() as session:
        connection = MailConnection(
            user_id=uid,
            provider="gmail",
            account_email_masked="s***@***.test",
            account_email_sha256="e" * 64,
            scopes=[],
            status="active",
        )
        session.add(connection)
        session.flush()
        cid = connection.id
        row = tx(session, uid, status="confirmed", review_reason=None)
        first, _ = source(session, uid, row, mode="gmail")
        first.mail_connection_id = cid
        second, _ = source(session, uid, row, mode="eml_upload")
        for email in [first, second]:
            event = SourceEvent(
                user_id=uid,
                email_source_id=email.id,
                event_type="bill_due",
                amount_minor=5000,
                currency="INR",
                merchant_normalized="Sample bill",
                due_date=date(2026, 10, 23),
                extraction_method="rule",
                extractor_id="synthetic",
                evidence={},
                field_confidence={},
            )
            session.add(event)
            session.flush()
            if email == first:
                bill = Commitment(
                    user_id=uid,
                    kind="bill",
                    label="Sample bill",
                    amount_minor=5000,
                    currency="INR",
                    due_date=date(2026, 10, 23),
                    status="upcoming",
                    source_event_id=event.id,
                    confidence=Decimal(".8"),
                )
                session.add(bill)
                session.flush()
                bid = bill.id
        rid = row.id
    preview = client.post(
        "/api/v1/privacy/deletion-preview", json={"connection_id": str(cid)}
    ).json()
    assert preview["source_count"] == 1 and preview["event_count"] == 2
    assert preview["removed_transaction_count"] == preview["removed_obligation_count"] == 0
    assert (
        preview["retained_shared_transaction_count"]
        == preview["retained_shared_obligation_count"]
        == 1
    )
    result = client.post(
        "/api/v1/privacy/delete",
        json={"expected_version": preview["version"], "connection_id": str(cid)},
    )
    assert result.status_code == 200
    assert client.get(f"/api/v1/transactions/{rid}").status_code == 200
    assert client.get(f"/api/v1/money/obligations/{bid}").status_code == 200
    outcome = client.post(
        "/api/v1/privacy/task-outcomes", json={"task": "evidence_opened", "subject_id": str(rid)}
    )
    assert outcome.status_code == 200
    assert (
        client.post(
            "/api/v1/privacy/task-outcomes",
            json={"task": "evidence_opened", "subject_id": str(uuid4())},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/privacy/task-outcomes",
            json={"task": "evidence_opened", "question": "PRIVATE_QUESTION"},
        ).status_code
        == 422
    )
    with factory() as session:
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.user_id == uid, AuditEvent.event_type == "task.evidence_opened"
            )
        )
        assert event.event_metadata == {} and event.subject_id == rid


def test_delete_after_merge_removes_origin_stub_and_private_decision_snapshots(ux):
    client, factory, uid = ux
    with factory.begin() as session:
        keep = tx(session, uid, status="confirmed", review_reason=None)
        pending = tx(session, uid)
        source(session, uid, keep)
        source(session, uid, pending)
        kid, pid = keep.id, pending.id
    merged = client.post(
        f"/api/v1/transactions/{pid}/decisions",
        json={"expected_version": version(client), "action": "merge", "keep_id": str(kid)},
    )
    assert merged.status_code == 200
    preview = client.post("/api/v1/privacy/deletion-preview", json={}).json()
    assert preview["removed_transaction_count"] == 2
    assert (
        client.post(
            "/api/v1/privacy/delete", json={"expected_version": preview["version"]}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/transactions/page?scope=all").json()["total"] == 0
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ReviewDecision)
                .where(ReviewDecision.user_id == uid)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(TransactionRevision)
                .join(Transaction, Transaction.id == TransactionRevision.transaction_id)
                .where(Transaction.user_id == uid)
            )
            == 0
        )


def test_scoped_delete_after_merge_keeps_surviving_evidence(ux):
    client, factory, uid = ux
    with factory.begin() as session:
        connection = MailConnection(
            user_id=uid,
            provider="gmail",
            account_email_masked="s***@***.test",
            account_email_sha256="f" * 64,
            scopes=[],
            status="active",
        )
        session.add(connection)
        session.flush()
        cid = connection.id
        keep = tx(session, uid, status="confirmed", review_reason=None)
        pending = tx(session, uid)
        source(session, uid, keep)
        imported, _ = source(session, uid, pending, mode="gmail")
        imported.mail_connection_id = cid
        kid, pid = keep.id, pending.id
    assert (
        client.post(
            f"/api/v1/transactions/{pid}/decisions",
            json={"expected_version": version(client), "action": "merge", "keep_id": str(kid)},
        ).status_code
        == 200
    )
    preview = client.post(
        "/api/v1/privacy/deletion-preview", json={"connection_id": str(cid)}
    ).json()
    assert preview["removed_transaction_count"] == preview["retained_shared_transaction_count"] == 1
    assert (
        client.post(
            "/api/v1/privacy/delete",
            json={"expected_version": preview["version"], "connection_id": str(cid)},
        ).status_code
        == 200
    )
    assert client.get(f"/api/v1/transactions/{pid}").status_code == 404
    assert client.get(f"/api/v1/transactions/{kid}").json()["transaction"]["source_count"] == 1


def test_legacy_merge_with_missing_origin_fails_closed_before_privacy_mutation(ux):
    from finboy.services.ledger.reconcile import merge_transactions

    client, factory, uid = ux
    with factory.begin() as session:
        keep = tx(session, uid, status="confirmed", review_reason=None)
        pending = tx(session, uid)
        _, first = source(session, uid, keep)
        _, second = source(session, uid, pending)
        first.origin_transaction_id = second.origin_transaction_id = None
        merge_transactions(session, user_id=uid, keep_id=keep.id, merge_id=pending.id)
    result = client.post("/api/v1/privacy/deletion-preview", json={})
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "source_lineage_unavailable"
    with factory() as session:
        assert (
            session.scalar(
                select(func.count()).select_from(EmailSource).where(EmailSource.user_id == uid)
            )
            == 2
        )


def test_source_free_manual_record_survives_deleting_its_imported_merge_target(ux):
    client, factory, uid = ux
    with factory.begin() as session:
        manual = tx(session, uid, merchant="Sample manual entry")
        imported = tx(session, uid, status="confirmed", review_reason=None)
        source(session, uid, imported)
        mid, iid = manual.id, imported.id
    assert (
        client.post(
            f"/api/v1/transactions/{mid}/decisions",
            json={"expected_version": version(client), "action": "merge", "keep_id": str(iid)},
        ).status_code
        == 200
    )
    preview = client.post("/api/v1/privacy/deletion-preview", json={}).json()
    assert preview["removed_transaction_count"] == 1
    assert (
        client.post(
            "/api/v1/privacy/delete", json={"expected_version": preview["version"]}
        ).status_code
        == 200
    )
    manual = client.get(f"/api/v1/transactions/{mid}").json()["transaction"]
    assert manual["status"] == "needs_review" and manual["merged_into_id"] is None
    assert manual["merchant"] == "Sample manual entry"


def test_bill_only_deletion_also_removes_derived_review_snapshot(ux):
    client, factory, uid = ux
    with factory.begin() as session:
        connection = MailConnection(
            user_id=uid,
            provider="gmail",
            account_email_masked="s***@***.test",
            account_email_sha256="1" * 64,
            scopes=[],
            status="active",
        )
        session.add(connection)
        session.flush()
        cid = connection.id
        row = tx(session, uid, status="confirmed", review_reason=None)
        email, _ = source(session, uid, row)
        bill_email = EmailSource(
            user_id=uid,
            import_run_id=email.import_run_id,
            mail_connection_id=cid,
            source="gmail",
            provider_message_id=uuid4().hex,
            content_sha256="2" * 64,
            sender_domain="example.test",
            subject_sha256="3" * 64,
            received_at=datetime(2026, 10, 24, tzinfo=IST),
            classification="bill_notice",
            processing_status="extracted",
        )
        session.add(bill_email)
        session.flush()
        claim = SourceEvent(
            user_id=uid,
            email_source_id=bill_email.id,
            event_type="bill_due",
            amount_minor=row.amount_minor,
            currency="INR",
            merchant_normalized=row.merchant,
            due_date=date(2026, 10, 24),
            extraction_method="rule",
            extractor_id="synthetic",
            evidence={},
            field_confidence={},
        )
        session.add(claim)
        session.flush()
        session.add(
            Commitment(
                user_id=uid,
                kind="bill",
                label=row.merchant,
                amount_minor=row.amount_minor,
                currency="INR",
                due_date=date(2026, 10, 24),
                status="paid",
                source_event_id=claim.id,
                paid_transaction_id=row.id,
                confidence=Decimal(".8"),
            )
        )
        rid = row.id
    assert (
        client.post(
            f"/api/v1/transactions/{rid}/decisions",
            json={"expected_version": version(client), "action": "reject"},
        ).status_code
        == 200
    )
    with factory() as session:
        assert session.scalar(
            select(ReviewDecision).where(ReviewDecision.user_id == uid)
        ).before_state["commitments"]
    preview = client.post(
        "/api/v1/privacy/deletion-preview", json={"connection_id": str(cid)}
    ).json()
    assert preview["removed_transaction_count"] == 0 and preview["removed_obligation_count"] == 1
    assert (
        client.post(
            "/api/v1/privacy/delete",
            json={"expected_version": preview["version"], "connection_id": str(cid)},
        ).status_code
        == 200
    )
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ReviewDecision)
                .where(ReviewDecision.user_id == uid)
            )
            == 0
        )
        assert session.get(Transaction, rid) is not None


def test_deleting_last_payment_proof_reopens_shared_record_without_changing_values(ux):
    client, factory, uid = ux
    with factory.begin() as session:
        connection = MailConnection(
            user_id=uid,
            provider="gmail",
            account_email_masked="s***@***.test",
            account_email_sha256="4" * 64,
            scopes=[],
            status="active",
        )
        session.add(connection)
        session.flush()
        cid = connection.id
        keep = tx(session, uid, status="confirmed", review_reason=None)
        pending = tx(session, uid)
        proof, _ = source(session, uid, keep, mode="gmail")
        proof.mail_connection_id = cid
        source(session, uid, pending, proof=False)
        kid, pid = keep.id, pending.id
    assert (
        client.post(
            f"/api/v1/transactions/{pid}/decisions",
            json={"expected_version": version(client), "action": "merge", "keep_id": str(kid)},
        ).status_code
        == 200
    )
    preview = client.post(
        "/api/v1/privacy/deletion-preview", json={"connection_id": str(cid)}
    ).json()
    assert (
        client.post(
            "/api/v1/privacy/delete",
            json={"expected_version": preview["version"], "connection_id": str(cid)},
        ).status_code
        == 200
    )
    record = client.get(f"/api/v1/transactions/{kid}").json()["transaction"]
    assert record["status"] == "needs_review" and record["payment_verification"] == "unverified"
    assert record["amount_minor"] == 10000 and record["merchant"] == "Sample Bookshop"


def test_import_review_next_action_tracks_current_decisions_and_recovery(ux):
    from finboy.services.imports.files import DEMO_DIRECTORY

    client, factory, uid = ux
    raw = (DEMO_DIRECTORY / "25-revieworder.eml").read_bytes()
    created = client.post(
        "/api/v1/imports/eml", files=[("files", ("synthetic-order.eml", raw, "message/rfc822"))]
    )
    assert created.status_code == 202
    run_id = created.json()["import_run_id"]
    assert client.get(f"/api/v1/imports/{run_id}").json()["needs_review"] == 1
    item = client.get("/api/v1/transactions/page?scope=unresolved").json()["items"][0]
    confirmed = client.post(
        f"/api/v1/transactions/{item['id']}/decisions",
        json={"expected_version": version(client), "action": "confirm"},
    )
    assert confirmed.status_code == 200
    assert client.get(f"/api/v1/imports/{run_id}").json()["needs_review"] == 0
    with factory() as session:
        assert session.get(ImportRun, UUID(run_id)).needs_review == 1
    reopened = client.post(
        f"/api/v1/transactions/{item['id']}/decisions",
        json={"expected_version": version(client), "action": "reopen"},
    )
    assert reopened.status_code == 200
    assert client.get(f"/api/v1/imports/{run_id}").json()["needs_review"] == 1


def test_category_correction_keeps_refund_drilldown_and_user_override_consistent(ux):
    client, factory, uid = ux
    with factory.begin() as session:
        purchase = tx(
            session, uid, status="confirmed", review_reason=None, reference_id="SYN-CATEGORY-PAIR"
        )
        refund = tx(
            session,
            uid,
            status="confirmed",
            review_reason=None,
            direction="in",
            kind="refund",
            reference_id="SYN-CATEGORY-PAIR",
        )
        source(session, uid, purchase)
        _, claim = source(session, uid, refund)
        claim.event_type = "refund"
        pid, rid = purchase.id, refund.id
    corrected = client.post(
        f"/api/v1/transactions/{pid}/decisions",
        json={
            "expected_version": version(client),
            "action": "correct",
            "correction": {"category": "food_dining"},
        },
    )
    assert corrected.status_code == 200
    items = client.get(
        "/api/v1/transactions/page?scope=all&category=food_dining&status=confirmed"
    ).json()["items"]
    assert {row["id"] for row in items} == {str(pid), str(rid)}
    assert (
        next(
            row
            for row in client.get("/api/v1/money/summary").json()["categories"]
            if row["category"] == "food_dining"
        )["amount_minor"]
        == 0
    )
    override = client.post(
        f"/api/v1/transactions/{rid}/decisions",
        json={
            "expected_version": version(client),
            "action": "correct",
            "correction": {"category": "education"},
        },
    )
    assert override.status_code == 200
    categories = {
        row["category"]: row["amount_minor"]
        for row in client.get("/api/v1/money/summary").json()["categories"]
    }
    assert categories == {"food_dining": 10000, "education": -10000}
    answer = client.post(
        "/api/v1/assistant/ask", json={"text": "How much did I spend on education this month?"}
    ).json()
    assert answer["facts"][0]["amount_minor"] == -10000


def test_real_ingestion_never_matches_sample_events_or_bills_into_household(ux):
    from finboy.services.imports.files import DEMO_DIRECTORY
    from finboy.services.ingestion.pipeline import InboundMessage, ingest_messages

    client, factory, uid = ux
    with factory.begin() as session:
        demo_run = ImportRun(user_id=uid, mode="demo_mailbox", status="running")
        real_run = ImportRun(user_id=uid, mode="eml_upload", status="running")
        session.add_all([demo_run, real_run])
        session.flush()
        did, rid = demo_run.id, real_run.id
    paths = [DEMO_DIRECTORY / "01-salary.eml", DEMO_DIRECTORY / "27-emi.eml"]
    demo = [
        InboundMessage(
            source="demo_mailbox", provider_message_id=str(i), raw_rfc822=path.read_bytes()
        )
        for i, path in enumerate(paths)
    ]
    household = [
        InboundMessage(
            source="eml_upload", provider_message_id=str(i), raw_rfc822=path.read_bytes()
        )
        for i, path in enumerate(paths)
    ]
    first = ingest_messages(factory, user_id=uid, import_run_id=did, messages=demo)
    second = ingest_messages(factory, user_id=uid, import_run_id=rid, messages=household)
    assert first.transactions_created == second.transactions_created == 1
    assert second.duplicates_merged == 0
    with factory() as session:
        assert set(
            session.scalars(select(Transaction.dataset).where(Transaction.user_id == uid))
        ) == {"demo", "household"}
        assert set(
            session.scalars(select(Commitment.dataset).where(Commitment.user_id == uid))
        ) == {"demo", "household"}
    summary = client.get("/api/v1/money/summary").json()
    assert summary["tracked_income_minor"] == 6200000
    assert summary["upcoming_commitments_minor"] == 650000
    page = client.get("/api/v1/transactions/page?scope=all").json()
    assert page["total"] == 1 and page["items"][0]["source_count"] == 1
