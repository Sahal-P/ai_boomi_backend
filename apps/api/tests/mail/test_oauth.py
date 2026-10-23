from datetime import timedelta
from time import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from finboy.core.clock import now_ist
from finboy.db.models.mail import AuditEvent, MailConnection, OAuthState
from finboy.services.mail.google import READ_SCOPE, GoogleClient
from finboy.services.mail.oauth import (
    OAuthConfig,
    authorize,
    consume_authorization_handoff,
    consume_state,
    create_authorization_handoff,
    finish_connection,
)
from finboy.services.mail.security import MailError, decrypt, encrypt, pkce_challenge, sha256
from sqlalchemy import select


def test_pkce_encryption_and_one_use(mail_factory, mail_settings):
    # RFC 7636 Appendix B's public vector, independent of the implementation.
    assert pkce_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == (
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )
    config = OAuthConfig.from_settings(mail_settings)
    with mail_factory() as session:
        url, state = authorize(session, config)
        params = parse_qs(urlsplit(url).query)
        row = session.scalar(select(OAuthState))
        assert row.state_sha256 == sha256(state)
        verifier = decrypt(config.encryption_key, row.encrypted_code_verifier)
        assert params["code_challenge"] == [pkce_challenge(verifier)]
        assert params["scope"] == [READ_SCOPE]
        assert params["access_type"] == ["offline"]
        assert params["prompt"] == ["consent"]
        assert params["code_challenge_method"] == ["S256"]
        assert row.encrypted_code_verifier != verifier.encode()
        assert consume_state(session, config, state) == verifier
        with pytest.raises(MailError, match="invalid_state"):
            consume_state(session, config, state)


def test_expired_and_tampered_state(mail_factory, mail_settings):
    config = OAuthConfig.from_settings(mail_settings)
    with mail_factory() as session:
        _, state = authorize(session, config)
        row = session.scalar(select(OAuthState))
        row.expires_at = now_ist() - timedelta(seconds=1)
        session.commit()
        for invalid in (state, state + "tamper", "", "x" * 257):
            with pytest.raises(MailError, match="invalid_state"):
                consume_state(session, config, invalid)
        _, fresh = authorize(session, config)
        with pytest.raises(MailError, match="invalid_state"):
            consume_state(session, config, fresh + "tampered")
        assert consume_state(session, config, fresh)


def test_authorization_handoff_is_expiring_single_use_and_distinct_from_oauth_state(
    mail_factory, mail_settings
):
    from cryptography.fernet import Fernet

    config = OAuthConfig.from_settings(mail_settings)
    cipher = Fernet(config.encryption_key)
    with mail_factory() as session:
        ticket = create_authorization_handoff(session, config)
        payload = cipher.decrypt(ticket.encode())
        expired = cipher.encrypt_at_time(payload, int(time()) - 120).decode()
        for invalid in (
            "",
            "x" * 1025,
            ticket[:-1],
            expired,
            cipher.encrypt(b"wrong-kind").decode(),
        ):
            with pytest.raises(MailError, match="invalid_state"):
                consume_authorization_handoff(session, config, invalid)
        url, state = consume_authorization_handoff(session, config, ticket)
        assert parse_qs(urlsplit(url).query)["state"] == [state]
        assert state.encode() not in payload
        with pytest.raises(MailError, match="invalid_state"):
            consume_authorization_handoff(session, config, ticket)
        assert consume_state(session, config, state)


def test_encryption_roundtrip_and_wrong_key(mail_settings):
    from cryptography.fernet import Fernet

    key = mail_settings.token_encryption_key.get_secret_value()
    encrypted = encrypt(key, "SENSITIVE_REFRESH")
    assert b"SENSITIVE_REFRESH" not in encrypted
    assert decrypt(key, encrypted) == "SENSITIVE_REFRESH"
    with pytest.raises(MailError, match="reconnect_required"):
        decrypt(Fernet.generate_key().decode(), encrypted)


@pytest.mark.parametrize(
    "scope",
    ["", "https://www.googleapis.com/auth/gmail.insert", READ_SCOPE + " https://mail.google.com/"],
)
def test_scope_rejected(mail_factory, mail_settings, scope):
    google = GoogleClient(
        "id",
        "secret",
        "http://localhost",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    json={
                        "scope": scope,
                        "access_token": "SENSITIVE_ACCESS",
                        "refresh_token": "SENSITIVE_REFRESH",
                    },
                )
            )
        ),
    )
    with mail_factory() as session, pytest.raises(MailError, match="scope_missing"):
        finish_connection(
            session,
            OAuthConfig.from_settings(mail_settings),
            google,
            code="SENSITIVE_CODE",
            verifier="SENSITIVE_VERIFIER",
        )
    google.close()


def google_double(monkeypatch, *, token_status=200, scope=READ_SCOPE, refresh=True):
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/token":
            payload = {"scope": scope, "access_token": "SENSITIVE_ACCESS"}
            if refresh:
                payload["refresh_token"] = "SENSITIVE_REFRESH"
            return httpx.Response(token_status, json=payload)
        return httpx.Response(200, json={"emailAddress": "private-person@example.test"})

    def factory(config):
        return GoogleClient(
            config.client_id,
            config.client_secret,
            config.redirect_uri,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

    monkeypatch.setattr(OAuthConfig, "google", factory)
    return requests


@pytest.mark.anyio
async def test_callback_connects_starts_import_and_redacts(
    mail_app, mail_factory, monkeypatch, capsys
):
    calls = google_double(monkeypatch)
    scheduled = []
    monkeypatch.setattr(
        "finboy.api.v1.connections.run_import", lambda *args: scheduled.append(args)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url="http://127.0.0.1:8002"
    ) as client:
        auth = await client.get("/api/v1/connections/gmail/authorize")
        state = parse_qs(urlsplit(auth.headers["location"]).query)["state"][0]
        response = await client.get(
            "/api/v1/connections/gmail/callback", params={"state": state, "code": "SENSITIVE_CODE"}
        )
        assert response.status_code == 307
        assert response.headers["location"].startswith("http://127.0.0.1:3002/import/")
        assert response.headers["referrer-policy"] == "no-referrer"
        connections = await client.get("/api/v1/connections")
        assert connections.json()[0]["account_email_masked"] == "p***@***.test"
        assert "encrypted_refresh_token" not in connections.text
        assert len(scheduled) == 1
        repeated = await client.get(
            "/api/v1/connections/gmail/callback", params={"state": state, "code": "SENSITIVE_CODE"}
        )
        assert repeated.headers["location"].endswith("error=invalid_state")
    with mail_factory() as session:
        saved = session.scalar(select(MailConnection))
        assert b"SENSITIVE_REFRESH" not in saved.encrypted_refresh_token
        assert saved.account_email_sha256 == sha256("private-person@example.test")
        assert set(session.scalars(select(AuditEvent.event_type))) == {
            "gmail.connected",
            "gmail.sync_requested",
            "import.started",
        }
    assert b"code_verifier=" in calls[0].content
    output = capsys.readouterr().out + response.text + connections.text
    for sensitive in (
        "SENSITIVE_CODE",
        "SENSITIVE_REFRESH",
        "SENSITIVE_ACCESS",
        "SENSITIVE_SECRET",
        "private-person@example.test",
    ):
        assert sensitive not in output


@pytest.mark.anyio
async def test_private_cross_host_authorization_sets_cookie_on_callback_host(
    mail_app, mail_settings, monkeypatch
):
    from cryptography.fernet import Fernet
    from finboy.core.access import password_hash
    from finboy.core.config import Settings

    google_double(monkeypatch)
    scheduled = []
    monkeypatch.setattr(
        "finboy.api.v1.connections.run_import", lambda *args: scheduled.append(args)
    )
    frontend = "https://household.example.test"
    backend = "https://api.example.test"
    callback = backend + "/api/v1/connections/gmail/callback"
    mail_app.state.settings = Settings.model_validate(
        mail_settings.model_dump()
        | {
            "environment": "production",
            "web_app_url": frontend,
            "cors_origins": [frontend],
            "google_oauth_redirect_uri": callback,
            "web_session_key": Fernet.generate_key().decode(),
            "household_password_hash": password_hash("synthetic-password"),
        }
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url=frontend
    ) as client:
        authorize_path = "/api/v1/connections/gmail/authorize"
        assert (await client.get(authorize_path)).status_code == 401
        login = await client.post(
            "/api/v1/auth/login",
            json={"password": "synthetic-password"},
            headers={"Origin": frontend},
        )
        assert login.status_code == 200
        auth = await client.get(authorize_path)
        handoff_url = auth.headers["location"]
        assert handoff_url.startswith(backend + "/api/v1/connections/gmail/handoff?ticket=")
        assert "set-cookie" not in auth.headers
        assert auth.headers["cache-control"] == "no-store"
        assert auth.headers["referrer-policy"] == "no-referrer"
        # The household cookie stays on the frontend. The handoff alone can only
        # initiate this one OAuth flow, never read records or start another flow.
        assert (await client.get(backend + authorize_path)).status_code == 401
        assert (await client.get(backend + "/api/v1/connections")).status_code == 401
        handoff = await client.get(handoff_url)
        params = parse_qs(urlsplit(handoff.headers["location"]).query)
        assert params["redirect_uri"] == [callback]
        cookie = handoff.headers["set-cookie"]
        assert "Domain=" not in cookie
        assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
        assert "Path=/api/v1/connections/gmail/callback" in cookie
        cookies = [c for c in client.cookies.jar if c.name == "finboy_oauth_state"]
        assert len(cookies) == 1 and cookies[0].domain == "api.example.test"
        replay = await client.get(handoff_url)
        assert replay.headers["location"] == frontend + "/connect?error=invalid_state"
        response = await client.get(
            callback, params={"state": params["state"][0], "code": "SENSITIVE_CODE"}
        )
        assert response.headers["location"].startswith(frontend + "/import/")
        assert response.headers["cache-control"] == "no-store"
        assert len(scheduled) == 1
        assert not [c for c in client.cookies.jar if c.name == "finboy_oauth_state"]
        missing = await client.get(backend + "/api/v1/connections/gmail/handoff")
        assert missing.headers["location"] == frontend + "/connect?error=invalid_state"
        invalid = await client.get(
            backend + "/api/v1/connections/gmail/handoff", params={"ticket": "SENSITIVE_TICKET"}
        )
        assert invalid.headers["location"] == frontend + "/connect?error=invalid_state"
        assert "SENSITIVE" not in invalid.text + invalid.headers["location"]
        for origin, expected in [(frontend, 200), ("https://attacker.example.test", 400)]:
            preflight = await client.options(
                backend + "/api/v1/connections/gmail/handoff",
                headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
            )
            assert preflight.status_code == expected
            assert preflight.headers.get("access-control-allow-origin") == (
                frontend if expected == 200 else None
            )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("denied", "consent_denied"),
        ("exchange", "oauth_failed"),
        ("scope", "scope_missing"),
        ("refresh", "refresh_token_missing"),
        ("cookie", "invalid_state"),
        ("code", "oauth_failed"),
    ],
)
async def test_callback_errors_are_fixed(mail_app, monkeypatch, scenario, expected):
    google_double(
        monkeypatch,
        token_status=400 if scenario == "exchange" else 200,
        scope="bad" if scenario == "scope" else READ_SCOPE,
        refresh=scenario != "refresh",
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mail_app), base_url="http://127.0.0.1:8002"
    ) as client:
        auth = await client.get("/api/v1/connections/gmail/authorize")
        state = parse_qs(urlsplit(auth.headers["location"]).query)["state"][0]
        if scenario == "cookie":
            client.cookies.clear()
        response = await client.get(
            "/api/v1/connections/gmail/callback",
            params={
                "state": state,
                "code": "" if scenario == "code" else "SENSITIVE_CODE",
                "error": "SENSITIVE_ERROR" if scenario == "denied" else "",
            },
        )
        assert response.status_code == 307
        assert response.headers["location"].endswith("error=" + expected)
        assert "SENSITIVE" not in response.text + response.headers["location"]
