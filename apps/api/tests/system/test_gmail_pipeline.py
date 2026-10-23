"""Google HTTP is mocked; Gmail orchestration, extraction, and PostgreSQL are real."""

import base64
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from finboy.db.models.mail import MailConnection
from finboy.services.imports.files import DEMO_DIRECTORY
from finboy.services.mail.google import READ_SCOPE, GoogleClient
from finboy.services.mail.oauth import OAuthConfig
from sqlalchemy import select
from sqlalchemy.orm import Session

# Reuse the disposable-user fixture; do not duplicate its lifecycle.
from .test_import_product import assembled_app

__all__ = ["assembled_app"]

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_mock_google_callback_runs_real_pipeline_then_revokes(assembled_app, monkeypatch):
    app, engine, user = assembled_app
    paths = sorted(DEMO_DIRECTORY.glob("*.eml"))
    requests = []
    invalid_grant = False

    def handler(request):
        requests.append(request)
        if request.url.path == "/token":
            if b"grant_type=refresh_token" in request.content and invalid_grant:
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(
                200,
                json={
                    "access_token": "SYNTHETIC_ACCESS",
                    "refresh_token": "SYNTHETIC_REFRESH",
                    "scope": READ_SCOPE,
                },
            )
        if request.url.path == "/revoke":
            assert request.content == b"token=SYNTHETIC_REFRESH"
            assert "SYNTHETIC_REFRESH" not in str(request.url)
            return httpx.Response(200)
        if request.url.path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": "synthetic@example.test"})
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json={"messages": [{"id": str(i)} for i in range(42)]})
        if request.url.params.get("format") == "metadata":
            return httpx.Response(200, json={"payload": {"headers": []}})
        raw = paths[int(request.url.path.rsplit("/", 1)[-1])].read_bytes()
        return httpx.Response(200, json={"raw": base64.urlsafe_b64encode(raw).decode()})

    monkeypatch.setattr(
        OAuthConfig,
        "google",
        lambda config: GoogleClient(
            config.client_id,
            config.client_secret,
            config.redirect_uri,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8002"
    ) as client:
        auth = await client.get("/api/v1/connections/gmail/authorize")
        state = parse_qs(urlsplit(auth.headers["location"]).query)["state"][0]
        callback = await client.get(
            "/api/v1/connections/gmail/callback", params={"state": state, "code": "SYNTHETIC_CODE"}
        )
        assert callback.status_code == 307
        run_id = callback.headers["location"].rsplit("/", 1)[-1]
        run = (await client.get("/api/v1/imports/" + run_id)).json()
        assert run["mode"] == "gmail" and run["status"] == "completed"
        assert run["transactions_created"] == 26 and run["failed"] == 0
        connection = (await client.get("/api/v1/connections")).json()[0]
        assert connection["status"] == "active" and connection["last_synced_at"]
        invalid_grant = True
        sync = await client.post(f"/api/v1/connections/{connection['id']}/sync")
        failed = (await client.get("/api/v1/imports/" + sync.json()["import_run_id"])).json()
        assert failed["status"] == "failed" and failed["error_code"] == "authorization_failed"
        assert (await client.get("/api/v1/connections")).json()[0]["status"] == "error"
        result = await client.delete(f"/api/v1/connections/{connection['id']}?delete_data=true")
        assert result.status_code == 200
        assert (await client.get("/api/v1/transactions")).json() == []
    with Session(engine) as session:
        row = session.scalar(select(MailConnection).where(MailConnection.user_id == user))
        assert row.status == "revoked" and row.encrypted_refresh_token is None
