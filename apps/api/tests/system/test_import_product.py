"""Real HTTP imports, PostgreSQL persistence, finance writes, and shared assistant.

No seeded final totals, mocked ingestion, live provider calls, or other-agent DBs.
"""

import importlib
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from finboy.core.config import Settings
from finboy.db.models import (
    AuditEvent,
    EmailSource,
    ImportRun,
    MailConnection,
    OAuthState,
    Transaction,
    User,
)
from finboy.db.session import build_engine
from finboy.main import create_app
from finboy.services.imports.files import DEMO_DIRECTORY
from finboy.services.privacy.delete import delete_imported_data
from pydantic import SecretStr
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.fixture
def assembled_app(monkeypatch):
    settings = Settings()
    engine = build_engine(settings)
    assert settings.environment != "production"
    assert engine.url.host in {"127.0.0.1", "localhost"}
    assert engine.url.database in {"finboy_p5", "finboy_ux_api", "finboy_ux_ui", "finboy_test"}, (
        "Use integration disposable DB"
    )
    user = uuid4()
    for name in (
        "finboy.api.v1.imports",
        "finboy.api.v1.privacy",
        "finboy.api.v1.connections",
        "finboy.api.v1.money",
        "finboy.api.v1.transactions",
        "finboy.api.v1.assistant",
        "finboy.services.imports.runner",
        "finboy.services.mail.oauth",
        "finboy.services.privacy.audit",
        "finboy.services.privacy.delete",
    ):
        module = importlib.import_module(name)
        if hasattr(module, "LOCAL_USER_ID"):
            monkeypatch.setattr(module, "LOCAL_USER_ID", user)
    monkeypatch.setenv("FINBOY_EXTRACTION_MODE", "offline")
    monkeypatch.setenv("OPENAI_EXTRACTION_MODEL", "gpt-6-luna")
    monkeypatch.setenv("DEMO_TODAY", "2026-10-28")
    with Session(engine) as session, session.begin():
        session.add(User(id=user, display_name="Synthetic complete-system test"))
    # Text intent tests use deterministic paths, without making provider calls.
    app = create_app(
        settings.model_copy(
            update={
                "openai_api_key": None,
                "whatsapp_enabled": False,
                "google_oauth_client_id": "synthetic-client",
                "google_oauth_client_secret": SecretStr("synthetic-secret"),
                "google_oauth_redirect_uri": "http://127.0.0.1:8002/api/v1/connections/gmail/callback",
                "token_encryption_key": SecretStr(Fernet.generate_key().decode()),
                "web_app_url": "http://127.0.0.1:3015",
            }
        )
    )
    app.state.engine.dispose()
    app.state.engine = engine
    try:
        yield app, engine, user
    finally:
        with Session(engine) as session, session.begin():
            delete_imported_data(session)
            session.execute(delete(AuditEvent).where(AuditEvent.user_id == user))
            session.execute(delete(ImportRun).where(ImportRun.user_id == user))
            session.execute(delete(OAuthState).where(OAuthState.user_id == user))
            session.execute(delete(MailConnection).where(MailConnection.user_id == user))
            session.execute(delete(User).where(User.id == user))
        engine.dispose()


async def test_actual_mailbox_to_money_review_assistant_and_privacy(assembled_app):
    app, engine, user = assembled_app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        paths = sorted(DEMO_DIRECTORY.glob("*.eml"))
        start = await client.post(
            "/api/v1/imports/eml",
            files=[("files", (path.name, path.read_bytes(), "message/rfc822")) for path in paths],
        )
        assert start.status_code == 202
        run = (await client.get("/api/v1/imports/" + start.json()["import_run_id"])).json()
        assert run["status"] == "completed", run["error_code"]
        assert {
            key: run[key]
            for key in (
                "headers_checked",
                "candidates_found",
                "emails_processed",
                "events_extracted",
                "transactions_created",
                "duplicates_merged",
                "needs_review",
                "non_financial_skipped",
                "failed",
            )
        } == {
            "headers_checked": 42,
            "candidates_found": 36,
            "emails_processed": 42,
            "events_extracted": 36,
            "transactions_created": 26,
            "duplicates_merged": 6,
            "needs_review": 2,
            "non_financial_skipped": 6,
            "failed": 0,
        }
        summary = (await client.get("/api/v1/money/summary")).json()
        assert [
            summary[name]
            for name in (
                "tracked_income_minor",
                "confirmed_outflows_minor",
                "upcoming_commitments_minor",
                "estimated_unallocated_minor",
            )
        ] == [6200000, 3742000, 980000, 1478000]
        assert summary["pending_review_count"] == 2
        rows = (await client.get("/api/v1/transactions")).json()
        assert isinstance(rows, list) and len(rows) == 26
        amazon = next(row for row in rows if row["amount_minor"] == 79900)
        detail = (await client.get("/api/v1/transactions/" + amazon["id"])).json()
        assert len(detail["sources"]) == 3
        arya = next(row for row in rows if row["merchant"] == "HOTEL ARYA")
        assert arya["category"] == "travel"
        before_food = next(row for row in summary["categories"] if row["category"] == "food_dining")
        assert before_food["amount_minor"] == 661000
        corrected = await client.patch(
            "/api/v1/transactions/" + arya["id"], json={"category": "food_dining"}
        )
        assert corrected.status_code == 200
        assert corrected.json()["transaction"]["category"] == "food_dining"
        assert corrected.json()["revisions"]
        after = (await client.get("/api/v1/money/summary")).json()
        assert after["confirmed_outflows_minor"] == 3742000
        assert (
            next(row for row in after["categories"] if row["category"] == "food_dining")[
                "amount_minor"
            ]
            == 786000
        )
        simulation = (
            await client.post(
                "/api/v1/money/simulations",
                json={"monthly_amount_minor": 500000, "label": "Synthetic proposal"},
            )
        ).json()
        assert simulation["remaining_after_proposal_minor"] == 978000
        for text, style in [
            ("How much did I spend on food this month?", "en"),
            ("इस महीने खाने पर कितना खर्च हुआ?", "hi"),
            ("ഈ മാസം ഭക്ഷണത്തിന് എത്ര ചെലവായി?", "ml"),
            ("Ee masam foodinu ethra poyi?", "manglish"),
            ("Is mahine food par kitna kharch hua?", "hinglish"),
        ]:
            answer = await client.post(
                "/api/v1/assistant/ask", json={"text": text, "display_style": style}
            )
            assert answer.status_code == 200
            payload = answer.json()
            assert payload["policy"] == "answer", (style, payload["intent"])
            assert any(fact["amount_minor"] == 786000 for fact in payload["facts"]), style
        again = await client.post(
            "/api/v1/imports/eml",
            files=[("files", (path.name, path.read_bytes(), "message/rfc822")) for path in paths],
        )
        assert again.status_code == 202
        second = (await client.get("/api/v1/imports/" + again.json()["import_run_id"])).json()
        assert second["status"] == "completed" and second["transactions_created"] == 0
        assert second["events_extracted"] == 0
        paths = sorted(DEMO_DIRECTORY.glob("*.eml"))
        upload = await client.post(
            "/api/v1/imports/eml",
            files=[("files", (path.name, path.read_bytes(), "message/rfc822")) for path in paths],
        )
        assert upload.status_code == 202
        uploaded = (await client.get("/api/v1/imports/" + upload.json()["import_run_id"])).json()
        assert uploaded["status"] == "completed" and uploaded["failed"] == 0
        assert uploaded["transactions_created"] == 0
        preserved = (await client.get("/api/v1/transactions/" + arya["id"])).json()
        assert preserved["transaction"]["category"] == "food_dining"
        with Session(engine) as session:
            assert (
                session.scalar(
                    select(func.count()).select_from(Transaction).where(Transaction.user_id == user)
                )
                == 26
            )
            assert (
                session.scalar(
                    select(func.count()).select_from(EmailSource).where(EmailSource.user_id == user)
                )
                == 42
            )
        review = (await client.get("/api/v1/transactions?status=needs_review")).json()
        assert len(review) == 2
        chosen = next(row for row in review if row["amount_minor"] == 50000)
        assert (
            await client.post(f"/api/v1/transactions/{chosen['id']}/confirm")
        ).status_code == 200
        other = next(row for row in review if row["id"] != chosen["id"])
        assert (await client.post(f"/api/v1/transactions/{other['id']}/reject")).status_code == 200
        assert (await client.get("/api/v1/money/summary")).json()["pending_review_count"] == 0
        audit_before = (await client.get("/api/v1/privacy/audit-events?limit=200")).json()
        assert (await client.delete("/api/v1/privacy/imported-data")).status_code == 200
        assert (await client.get("/api/v1/transactions")).json() == []
        events = (await client.get("/api/v1/privacy/audit-events?limit=200")).json()
        assert len(events) > len(audit_before)
        assert any(event["event_type"] == "data.deleted" for event in events)
