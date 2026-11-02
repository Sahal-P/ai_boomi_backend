import logging
from collections.abc import AsyncIterator
from unittest.mock import MagicMock
from urllib.parse import urlencode

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from finboy.api import deps
from finboy.core.access import password_hash
from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.db.session import get_session
from finboy.main import create_app
from finboy.services.billing.payu import response_hash
from sqlalchemy.orm import Session

from .support import KEY, SALT, billing_settings

FORM = {"content-type": "application/x-www-form-urlencoded"}
TXN = "fb0123456789abcdef0123456"


def signed(**overrides: str) -> dict[str, str]:
    fields = {
        "key": KEY,
        "txnid": TXN,
        "amount": "299.00",
        "productinfo": "FinBoy Premium monthly",
        "firstname": "FinBoy",
        "email": "someone@example.in",
        "status": "success",
        "mihpayid": "403993715531234567",
        "mode": "UPI",
    }
    fields.update(overrides)
    fields.setdefault("hash", response_hash(fields, SALT))
    return fields


def app_for(settings: Settings) -> tuple[FastAPI, MagicMock]:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: session
    return app, session


@pytest.fixture
async def billing_client() -> AsyncIterator[tuple[httpx.AsyncClient, MagicMock]]:
    app, session = app_for(billing_settings())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://127.0.0.1:8071"
    ) as client:
        yield client, session
    app.state.engine.dispose()


@pytest.mark.anyio
async def test_return_goes_back_to_the_web_app_without_payu_data(billing_client, caplog) -> None:
    client, session = billing_client
    caplog.set_level(logging.INFO)
    tampered = signed()
    tampered["amount"] = "1.00"
    response = await client.post("/api/v1/payu/return", content=urlencode(tampered), headers=FORM)
    assert response.status_code == 303
    assert response.headers["location"] == "http://127.0.0.1:3071/plan?payment=unknown"
    session.scalar.assert_not_called()  # refused before any database work
    for secret in (SALT, tampered["hash"], "someone@example.in", "403993715531234567"):
        assert secret not in caplog.text
    wrong_key = signed(key="0therK")
    response = await client.post("/api/v1/payu/return", content=urlencode(wrong_key), headers=FORM)
    assert response.headers["location"].endswith("/plan?payment=unknown")


@pytest.mark.anyio
async def test_unknown_payments_are_refused(billing_client) -> None:
    client, _session = billing_client  # session.scalar() finds no payment
    response = await client.post("/api/v1/payu/return", content=urlencode(signed()), headers=FORM)
    assert response.headers["location"].endswith("/plan?payment=unknown")


@pytest.mark.anyio
async def test_webhooks_answer_fast_and_refuse_only_forgeries(billing_client) -> None:
    client, _session = billing_client
    forged = signed()
    forged["status"] = "failure"
    response = await client.post("/api/v1/payu/webhook", content=urlencode(forged), headers=FORM)
    assert response.status_code == 400 and response.json()["error"]["code"] == "invalid_request"
    other_app = signed(key="0therK")
    response = await client.post("/api/v1/payu/webhook", content=urlencode(other_app), headers=FORM)
    assert response.status_code == 200
    refund = await client.post("/api/v1/payu/webhook", json={"mihpayid": "1", "status": "success"})
    assert refund.status_code == 200 and refund.json() == {"received": True}
    notice = await client.post("/api/v1/payu/mandate", json={"authPayuId": "not a number"})
    assert notice.status_code == 200


@pytest.mark.anyio
async def test_payu_posts_are_size_limited(billing_client) -> None:
    client, _session = billing_client
    response = await client.post("/api/v1/payu/return", content="a=" + "x" * 20000, headers=FORM)
    assert response.status_code == 413


@pytest.mark.anyio
async def test_billing_off_changes_nothing() -> None:
    app, session = app_for(billing_settings(billing_enabled=False))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://127.0.0.1:8071"
    ) as client:
        response = await client.post(
            "/api/v1/payu/return", content=urlencode(signed()), headers=FORM
        )
        assert response.headers["location"] == "http://127.0.0.1:3071/plan"
        refused = await client.post("/api/v1/billing/checkout", json={})
        assert refused.status_code == 503
        assert refused.json()["error"]["code"] == "billing_unavailable"
    session.scalar.assert_not_called()
    app.state.engine.dispose()


@pytest.mark.anyio
async def test_premium_features_answer_premium_required(billing_client, monkeypatch) -> None:
    client, _session = billing_client

    def refuse(*_args: object) -> None:
        raise AccessError("premium_required")

    monkeypatch.setattr(deps, "require_premium", refuse)
    for path, kwargs in [
        ("/api/v1/assistant/ask", {"json": {"text": "How much did I spend?"}}),
        ("/api/v1/assistant/speak", {"json": {"text": "Hello", "language": "en"}}),
        ("/api/v1/assistant/transcribe", {"files": {"audio": ("a.ogg", b"x", "audio/ogg")}}),
        ("/api/v1/imports/gpay", {"files": {"file": ("s.pdf", b"%PDF", "application/pdf")}}),
    ]:
        response = await client.post(path, **kwargs)
        assert response.status_code == 402, path
        assert response.json()["error"] == {
            "code": "premium_required",
            "message": "This is part of FinBoy Premium.",
            "request_id": response.headers["x-request-id"],
        }


@pytest.fixture
async def production() -> AsyncIterator[httpx.AsyncClient]:
    settings = billing_settings(
        environment="production",
        cors_origins=["https://finboy.io"],
        web_app_url="https://finboy.io",
        api_public_url="https://finboy.io",
        payu_environment="production",
        billing_launch_date="2026-11-10",
        web_session_key=Fernet.generate_key().decode(),
        household_password_hash=password_hash("synthetic-household-password"),
    )
    app, _session = app_for(settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="https://finboy.io"
    ) as client:
        yield client
    app.state.engine.dispose()


@pytest.mark.anyio
async def test_only_payus_paths_skip_sign_in_and_the_origin_rule(production) -> None:
    # PayU posts without the web app's Origin or cookie: the hash decides, not the 401/403 rules.
    response = await production.post(
        "/api/v1/payu/webhook", content=urlencode(signed(key="0therK")), headers=FORM
    )
    assert response.status_code == 200
    response = await production.post("/api/v1/payu/return", content="", headers=FORM)
    assert response.status_code == 303
    assert (await production.post("/api/v1/payu/mandate", json={})).status_code == 200
    # Household billing routes still need a session, and public ones still need the Origin.
    assert (await production.post("/api/v1/billing/checkout", json={})).status_code == 401
    assert (await production.get("/api/v1/billing/payments")).status_code == 401
    receipt = await production.post(
        "/api/v1/billing/receipt", json={"payment_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert receipt.status_code == 403 and receipt.json()["error"]["code"] == "origin_not_allowed"
    link = await production.post(
        "/api/v1/billing/link", json={"token": "x" * 40}, headers={"origin": "https://evil.example"}
    )
    assert link.status_code == 403
