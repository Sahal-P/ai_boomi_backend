"""Uploading a Google Pay statement: checked before anything is saved, failures in fixed words."""

import hashlib
from datetime import date, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.mail import ImportRun
from finboy.db.models.statements import StatementImport
from sqlalchemy import select

from .statement_pdf import Row, statement_pdf

STATEMENT = statement_pdf(
    [
        [
            Row(),
            Row(
                date="02 Apr,",
                details=["Received from Ravi Kumar"],
                upi="200000000002",
                account="Paid to Sample Bank 1234",
                amount=["₹500"],
            ),
        ]
    ],
    sent="₹315",
    received="₹500",
)


@pytest.fixture
def scheduled(mail_app, monkeypatch):
    calls = []
    monkeypatch.setattr(mail_app.state.settings, "statement_import_enabled", True)
    monkeypatch.setattr(
        "finboy.api.v1.imports.run_statement_import",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    return calls


async def upload(app, files=None, **kwargs) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post("/api/v1/imports/gpay", files=files, **kwargs)


@pytest.mark.anyio
async def test_nothing_is_accepted_while_statement_import_is_off(mail_app, mail_factory):
    response = await upload(mail_app, {"file": ("statement.pdf", STATEMENT, "application/pdf")})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "statement_import_off"
    assert list(mail_factory().scalars(select(ImportRun.id))) == []


@pytest.mark.anyio
async def test_a_statement_that_adds_up_starts_an_import(mail_app, mail_factory, scheduled):
    response = await upload(
        mail_app, {"file": ("gpay_statement.pdf", STATEMENT, "application/pdf")}
    )
    assert response.status_code == 202
    run_id = response.json()["import_run_id"]
    with mail_factory() as session:
        run = session.get(ImportRun, UUID(run_id))
        assert (run.mode, run.status, str(run.window_start), str(run.window_end)) == (
            "gpay_statement",
            "queued",
            "2026-04-01",
            "2026-04-30",
        )
    ((args, kwargs),) = scheduled
    assert str(args[1]) == run_id and len(args[2].rows) == 2
    assert (
        kwargs["file_sha256"] == hashlib.sha256(STATEMENT).hexdigest() and kwargs["holder"] is None
    )


@pytest.mark.anyio
async def test_a_statement_that_does_not_add_up_fails_at_once_and_shows_what_was_found(
    mail_app, scheduled
):
    data = statement_pdf([[Row()]], sent="₹300", received="₹0")
    response = await upload(mail_app, {"file": ("gpay_statement.pdf", data, "application/pdf")})
    assert response.status_code == 202 and scheduled == []
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url="http://test"
    ) as client:
        view = (await client.get(f"/api/v1/imports/{response.json()['import_run_id']}")).json()
    assert (view["status"], view["outcome"], view["error_code"]) == (
        "failed",
        "failed",
        "extraction_failed",
    )
    statement = view["statement"]
    assert (statement["reconciled"], statement["sent_minor"], statement["paid_minor"]) == (
        False,
        30000,
        31500,
    )
    assert statement["accounts"] == ["Sample Bank ••1234"] and statement["new"] == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "files,status,code",
    [
        ({"file": ("statement.txt", STATEMENT, "text/plain")}, 400, "invalid_statement"),
        ({"files": ("statement.pdf", STATEMENT, "application/pdf")}, 400, "invalid_statement"),
        (
            [
                ("file", ("a.pdf", STATEMENT, "application/pdf")),
                ("file", ("b.pdf", STATEMENT, "application/pdf")),
            ],
            413,
            "upload_limit",
        ),
        (
            {"file": ("statement.pdf", b"%PDF-" + b"0" * (10 * 1024 * 1024), "application/pdf")},
            413,
            "upload_limit",
        ),
        (
            {"file": ("letter.pdf", b"%PDF-1.4 a private letter", "application/pdf")},
            422,
            "not_gpay_statement",
        ),
    ],
)
async def test_other_uploads_get_fixed_words_and_start_nothing(
    mail_app, mail_factory, scheduled, files, status, code
):
    response = await upload(mail_app, files)
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code and set(error) == {"code", "message", "request_id"}
    assert "private letter" not in response.text and "Asha" not in response.text
    assert scheduled == [] and list(mail_factory().scalars(select(ImportRun.id))) == []


@pytest.mark.anyio
async def test_the_same_statement_twice_is_refused_until_it_is_removed(
    mail_app, mail_factory, scheduled
):
    digest = hashlib.sha256(STATEMENT).hexdigest()
    run_id = uuid4()
    with mail_factory.begin() as session:
        session.add(
            ImportRun(id=run_id, user_id=LOCAL_USER_ID, mode="gpay_statement", status="completed")
        )
        session.flush()
        session.add(
            StatementImport(
                import_run_id=run_id,
                user_id=LOCAL_USER_ID,
                provider="gpay",
                period_start=date(2026, 4, 1),
                period_end=date(2026, 4, 30),
                pages=1,
                rows_total=2,
                sent_minor=31500,
                received_minor=50000,
                paid_minor=31500,
                got_minor=50000,
                reconciled=True,
                accounts=["Sample Bank ••1234"],
                file_sha256=digest,
            )
        )
    response = await upload(mail_app, {"file": ("statement.pdf", STATEMENT, "application/pdf")})
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "statement_already_imported"
    )
    with mail_factory.begin() as session:
        session.get(StatementImport, run_id).removed_at = datetime.now()
    again = await upload(mail_app, {"file": ("statement.pdf", STATEMENT, "application/pdf")})
    assert again.status_code == 202 and len(scheduled) == 1


@pytest.mark.anyio
async def test_uploads_from_other_sites_are_refused(mail_app, scheduled):
    response = await upload(
        mail_app,
        {"file": ("statement.pdf", STATEMENT, "application/pdf")},
        headers={"Origin": "https://elsewhere.example"},
    )
    assert response.status_code == 403 and scheduled == []


@pytest.mark.anyio
async def test_the_session_says_whether_statements_can_be_imported(mail_app, monkeypatch):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url="http://test"
    ) as client:
        assert (await client.get("/api/v1/auth/session")).json()["statement_import"] is False
        monkeypatch.setattr(mail_app.state.settings, "statement_import_enabled", True)
        assert (await client.get("/api/v1/auth/session")).json()["statement_import"] is True
