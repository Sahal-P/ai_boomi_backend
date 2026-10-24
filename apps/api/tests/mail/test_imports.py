from contextlib import nullcontext
from uuid import uuid4

import httpx
import pytest
from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.mail import AuditEvent, ImportRun, MailConnection
from finboy.services.imports.files import parse_eml
from finboy.services.imports.runner import create_run, run_import
from finboy.services.ingestion.pipeline import IngestionStats
from finboy.services.mail.security import MailError
from sqlalchemy import select


def test_rfc822_allows_optional_subject_but_rejects_invalid_date(eml):
    assert parse_eml(eml.replace(b"Subject: Payment notification\r\n", b"")).raw_rfc822
    with pytest.raises(MailError, match="invalid_eml"):
        parse_eml(eml.replace(b"Wed, 28 Oct 2026 10:00:00 +0530", b"invalid date"))


@pytest.mark.anyio
@pytest.mark.parametrize(
    "count,size,filename,content_type,expected",
    [
        (1, 0, "test.eml", "message/rfc822", 202),
        (50, 0, "test.eml", "message/rfc822", 202),
        (51, 0, "test.eml", "message/rfc822", 413),
        (1, 2 * 1024 * 1024 + 1, "test.eml", "message/rfc822", 413),
        (1, 0, "test.txt", "text/plain", 400),
        (1, 0, "test.eml", "application/pdf", 400),
        (0, 0, "test.eml", "message/rfc822", 400),
    ],
)
async def test_upload_limits_and_types(
    mail_app, monkeypatch, eml, count, size, filename, content_type, expected
):
    scheduled = []
    monkeypatch.setattr("finboy.api.v1.imports.run_import", lambda *args: scheduled.append(args))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/imports/eml",
            files=[
                ("files", (filename, b"x" * size if size else eml, content_type))
                for _ in range(count)
            ]
            or None,
        )
    assert response.status_code == expected
    assert len(scheduled) == (1 if expected == 202 else 0)
    if expected == 202:
        assert scheduled[0][3][0].source == "eml_upload"


@pytest.mark.anyio
async def test_malformed_eml_and_truncated_multipart(mail_app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/imports/eml",
            files={"files": ("test.eml", b"Not an RFC 822 message", "message/rfc822")},
        )
        assert response.status_code == 400
        truncated = await client.post(
            "/api/v1/imports/eml",
            content=b"--test\r\n",
            headers={"Content-Type": "multipart/form-data; boundary=test"},
        )
        assert truncated.status_code == 400


@pytest.mark.anyio
async def test_demo_is_read_only_and_old_import_is_disabled(mail_app, mail_factory):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url="http://test"
    ) as client:
        before = list(mail_factory().scalars(select(ImportRun.id)))
        response = await client.post("/api/v1/imports/demo")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "demo_read_only"
        demo = await client.get("/api/v1/demo")
        assert demo.status_code == 200
        assert demo.json()["read_only"] is True
        assert demo.json()["summary"]["dataset"] == "demo"
        assert demo.json()["summary"]["estimated_unallocated_minor"] == 1478000
        assert list(mail_factory().scalars(select(ImportRun.id))) == before


def test_progress_uses_independent_sessions(mail_factory, mail_settings, monkeypatch, eml):
    monkeypatch.setattr("finboy.services.imports.runner.import_lock", lambda _: nullcontext())
    with mail_factory() as session:
        run = create_run(session, mode="eml_upload")
        run_id = run.id

    def ingest(factory, *, user_id, import_run_id, messages, on_progress, ensure_active):
        assert user_id == LOCAL_USER_ID and import_run_id == run_id
        assert len(list(messages)) == 1
        stats = IngestionStats(
            headers_checked=1,
            candidates_found=1,
            emails_processed=1,
            transactions_created=1,
            duplicates_merged=1,
            needs_review=1,
        )
        on_progress(stats)
        with factory() as observer:
            assert observer.get(ImportRun, run_id).transactions_created == 1
        return stats

    monkeypatch.setattr("finboy.services.imports.runner.ingest_messages", ingest)
    run_import(mail_factory.kw["bind"], mail_settings, run_id, [parse_eml(eml)])
    with mail_factory() as session:
        run = session.get(ImportRun, run_id)
        assert run.status == "completed" and run.finished_at is not None
        assert run.needs_review == run.duplicates_merged == 1
        assert "import.completed" in session.scalars(select(AuditEvent.event_type)).all()


def test_abandoned_import_allows_a_fresh_run(mail_factory, monkeypatch):
    from datetime import timedelta

    from finboy.core.clock import now_ist

    monkeypatch.setattr("finboy.services.imports.runner.import_lock", lambda _: nullcontext())
    with mail_factory() as session:
        first = create_run(session, mode="eml_upload")
        with pytest.raises(MailError, match="import_busy"):
            create_run(session, mode="demo_mailbox")
        first.started_at = now_ist() - timedelta(minutes=1)
        session.commit()
        second = create_run(session, mode="demo_mailbox")
        assert first.status == "failed" and first.error_code == "import_failed"
        assert second.id != first.id and second.status == "queued"


def test_background_failure_recording_is_redacted(mail_settings, monkeypatch, capsys):
    from finboy.core.logging import configure_logging

    configure_logging("INFO")

    class UnavailableFactory:
        def begin(self):
            raise RuntimeError("SENSITIVE_DATABASE_DETAILS")

    monkeypatch.setattr("finboy.services.imports.runner.import_lock", lambda _: nullcontext())
    monkeypatch.setattr(
        "finboy.services.imports.runner.sessionmaker", lambda *args, **kwargs: UnavailableFactory()
    )
    run_import(None, mail_settings, uuid4())
    output = capsys.readouterr().out
    assert "failure_record_unavailable" in output
    assert "SENSITIVE_DATABASE_DETAILS" not in output


@pytest.mark.anyio
async def test_cross_origin_post_has_no_side_effect(mail_app, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "finboy.api.v1.imports.create_run", lambda *args, **kwargs: calls.append(True)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/imports/demo", headers={"Origin": "https://untrusted.example"}
        )
        assert response.status_code == 403
        assert response.headers["cache-control"] == "no-store"
        assert not calls


@pytest.mark.anyio
async def test_upload_error_does_not_expose_content(mail_app, capsys):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/imports/eml",
            files={
                "files": (
                    "private-person@example.test.eml",
                    b"SENSITIVE_EMAIL_BODY",
                    "message/rfc822",
                )
            },
        )
        assert response.status_code == 400
        output = response.text + capsys.readouterr().out
        assert "SENSITIVE_EMAIL_BODY" not in output
        assert "private-person@example.test" not in output


@pytest.mark.parametrize(
    "error,code",
    [
        (RuntimeError("SENSITIVE_TEXT"), "import_failed"),
        (MailError("reconnect_required"), "reconnect_required"),
    ],
)
def test_failures_are_fixed(mail_factory, mail_settings, monkeypatch, error, code):
    from finboy.core.clock import now_ist

    monkeypatch.setattr("finboy.services.imports.runner.import_lock", lambda _: nullcontext())
    with mail_factory() as session:
        connection = MailConnection(
            id=uuid4(),
            user_id=LOCAL_USER_ID,
            provider="gmail",
            account_email_masked="d***@***.test",
            account_email_sha256="a" * 64,
            scopes=[],
            status="active",
            connected_at=now_ist(),
        )
        session.add(connection)
        session.commit()
        run = create_run(session, mode="eml_upload")
        run.mail_connection_id = connection.id
        session.commit()
        run_id, connection_id = run.id, connection.id

    # Raise inside configuration before a network call; this verifies orchestration failures.
    monkeypatch.setattr(
        "finboy.services.imports.runner.OAuthConfig.from_settings",
        lambda _: (_ for _ in ()).throw(error),
    )
    run_import(mail_factory.kw["bind"], mail_settings, run_id)
    with mail_factory() as session:
        run = session.get(ImportRun, run_id)
        assert run.status == "failed"
        assert run.error_code == ("authorization_failed" if code == "reconnect_required" else code)
        assert session.get(MailConnection, connection_id).status == (
            "error" if code == "reconnect_required" else "active"
        )


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["POST", "DELETE"])
async def test_cors_write_methods(mail_app, method):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url="http://test"
    ) as client:
        headers = {
            "Origin": "http://127.0.0.1:3002",
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "Content-Type",
        }
        response = await client.options("/api/v1/privacy/imported-data", headers=headers)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == headers["Origin"]
        headers["Origin"] = "https://untrusted.example"
        assert (
            await client.options("/api/v1/privacy/imported-data", headers=headers)
        ).status_code == 400
