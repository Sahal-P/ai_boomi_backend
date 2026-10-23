import time

import httpx
import pytest
from cryptography.fernet import Fernet
from finboy.core.access import COOKIE, SESSION_SECONDS, password_hash
from finboy.core.config import Settings
from finboy.main import create_app
from pydantic import ValidationError


@pytest.fixture
def private_app():
    key = Fernet.generate_key().decode()
    settings = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        cors_origins=["https://household.example.test"],
        web_app_url="https://household.example.test",
        web_session_key=key,
        household_password_hash=password_hash("synthetic-household-password"),
    )
    app = create_app(settings)
    yield app, key
    app.state.engine.dispose()


@pytest.mark.anyio
async def test_public_requests_cannot_reach_any_product_or_privacy_route(private_app):
    app, _ = private_app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="https://household.example.test"
    ) as client:
        for method, path in [
            ("GET", "/api/v1/money/summary"),
            ("GET", "/api/v1/transactions"),
            ("GET", "/api/v1/privacy/audit-events"),
            ("DELETE", "/api/v1/privacy/imported-data"),
            ("POST", "/api/v1/imports/demo"),
            ("POST", "/api/v1/assistant/ask"),
            ("GET", "/api/v1/connections/gmail/authorize"),
            ("GET", "/api/v1/readiness"),
            ("GET", "/docs"),
            ("GET", "/openapi.json"),
        ]:
            assert (await client.request(method, path)).status_code == 401
        assert (await client.get("/api/v1/auth/session")).json() == {
            "required": True,
            "authenticated": False,
        }


@pytest.mark.anyio
async def test_login_cookie_csrf_logout_and_redaction(private_app, capsys):
    app, _ = private_app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="https://household.example.test"
    ) as client:
        body = {"password": "synthetic-household-password"}
        assert (await client.post("/api/v1/auth/login", json=body)).status_code == 403
        client.headers["origin"] = "https://household.example.test"
        wrong = await client.post("/api/v1/auth/login", json={"password": "SENSITIVE_BAD_PASSWORD"})
        assert wrong.status_code == 401 and "SENSITIVE" not in wrong.text
        response = await client.post("/api/v1/auth/login", json=body)
        assert response.status_code == 200
        cookie = response.headers["set-cookie"]
        assert all(part in cookie for part in ["HttpOnly", "Secure", "SameSite=lax", "Path=/"])
        assert "Domain=" not in cookie
        assert (await client.get("/api/v1/auth/session")).json()["authenticated"]
        client.headers["origin"] = "https://attacker.example.test"
        assert (await client.delete("/api/v1/privacy/imported-data")).status_code == 403
        client.headers["origin"] = "https://household.example.test"
        assert (await client.post("/api/v1/auth/logout")).status_code == 200
        assert not (await client.get("/api/v1/auth/session")).json()["authenticated"]
        assert "synthetic-household-password" not in capsys.readouterr().out


@pytest.mark.anyio
async def test_expired_tampered_tokens_and_login_limits(private_app):
    app, key = private_app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="https://household.example.test"
    ) as client:
        for token in [
            "tampered",
            Fernet(key)
            .encrypt_at_time(b"finboy:household:v1", int(time.time()) - SESSION_SECONDS - 1)
            .decode(),
        ]:
            client.cookies.set(COOKIE, token)
            assert not (await client.get("/api/v1/auth/session")).json()["authenticated"]
        client.headers["origin"] = "https://household.example.test"
        for _ in range(10):
            assert (
                await client.post("/api/v1/auth/login", json={"password": "wrong"})
            ).status_code == 401
        assert (
            await client.post("/api/v1/auth/login", json={"password": "wrong"})
        ).status_code == 429
        assert (await client.post("/api/v1/auth/login", content=b"x" * 4097)).status_code == 413


def test_production_refuses_to_start_without_private_access():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        )
