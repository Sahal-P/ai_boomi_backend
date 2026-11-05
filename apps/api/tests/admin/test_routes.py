"""The admin API's access rules, cookies and response boundary, without a database."""

import re
from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, get_args
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.routing import APIRoute
from finboy.api.v1.admin import router as admin_router
from finboy.core.access import password_hash
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.db.models.admin import AdminEvent
from finboy.db.session import get_session
from finboy.main import create_app
from finboy.services.admin import auth, views
from finboy.services.admin.households import allowed, kind_of, sender_digest, status_of
from finboy.services.whatsapp.config import keyed_digest
from pydantic import BaseModel, SecretStr
from sqlalchemy.orm import Session

from .support import LOGIN, ORIGIN, PASSWORD, admin_row, live_session

HOUSEHOLD_PASSWORD = "synthetic-household-password"
NOW = datetime(2026, 11, 5, 9, 30, tzinfo=UTC)


@pytest.fixture
def production_app() -> Iterator[FastAPI]:
    settings = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        cors_origins=[ORIGIN],
        web_app_url=ORIGIN,
        web_session_key=Fernet.generate_key().decode(),
        household_password_hash=password_hash(HOUSEHOLD_PASSWORD),
    )
    app = create_app(settings)
    yield app
    app.state.engine.dispose()


def client_for(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url=ORIGIN)


def code(response: httpx.Response) -> str:
    return response.json()["error"]["code"]


def admin_routes() -> Iterator[APIRoute]:
    """The admin router's own routes (FastAPI keeps included routers nested in `app.routes`)."""
    for route in admin_router.routes:
        assert isinstance(route, APIRoute)
        yield route


@pytest.mark.anyio
async def test_every_admin_route_needs_an_admin_session_even_on_loopback(
    client: httpx.AsyncClient, session: MagicMock
) -> None:
    checked = []
    for route in admin_routes():
        path = "/api/v1" + route.path
        if path == LOGIN:
            continue
        url = re.sub(r"\{[^}]+\}", str(uuid4()), path)
        for method in route.methods:
            response = await client.request(method, url, json={} if method == "POST" else None)
            assert (response.status_code, code(response)) == (401, "admin_required"), path
            checked.append(path)
    assert len(checked) >= 24
    session.execute.assert_not_called()  # refused before any query


@pytest.mark.anyio
async def test_household_and_admin_sessions_never_open_each_other(
    production_app: FastAPI,
) -> None:
    async with client_for(production_app) as client:
        client.headers["origin"] = ORIGIN
        signed_in = await client.post("/api/v1/auth/login", json={"password": HOUSEHOLD_PASSWORD})
        assert signed_in.status_code == 200
        for path in ("/api/v1/admin/session", "/api/v1/admin/overview", "/api/v1/admin/audit"):
            response = await client.get(path)
            assert (response.status_code, code(response)) == (401, "admin_required")
    async with client_for(production_app) as client:
        client.cookies.set(auth.COOKIE, "synthetic-admin-token")
        for path in ("/api/v1/money/summary", "/api/v1/transactions", "/api/v1/account"):
            response = await client.get(path)
            assert (response.status_code, code(response)) == (401, "authentication_required")


@pytest.mark.anyio
async def test_admin_sign_in_sets_a_strict_host_only_cookie_and_needs_the_origin(
    production_app: FastAPI, capsys: pytest.CaptureFixture[str]
) -> None:
    admin = admin_row()
    db = MagicMock(spec=Session)
    db.scalar.return_value = admin
    production_app.dependency_overrides[get_session] = lambda: db
    body = {"email": "Admin@Example.test", "password": PASSWORD}
    async with client_for(production_app) as client:
        assert (await client.post(LOGIN, json=body)).status_code == 403  # no Origin
        client.headers["origin"] = "https://attacker.example.test"
        assert (await client.post(LOGIN, json=body)).status_code == 403
        client.headers["origin"] = ORIGIN
        wrong = await client.post(LOGIN, json={**body, "password": "SENSITIVE-wrong-password"})
        assert (wrong.status_code, code(wrong)) == (401, "admin_login_failed")
        assert "set-cookie" not in wrong.headers
        signed_in = await client.post(LOGIN, json=body)
        assert signed_in.status_code == 200
        assert signed_in.json() == {"email": "admin@example.test", "must_change_password": False}
        cookie = signed_in.headers["set-cookie"]
        assert cookie.startswith(f"{auth.COOKIE}=")
        for part in ("HttpOnly", "Secure", "SameSite=strict", "Path=/", "Max-Age=28800"):
            assert part in cookie
        assert "Domain=" not in cookie
    events = [call.args[0] for call in db.add.call_args_list]
    assert [event.action for event in events if isinstance(event, AdminEvent)] == [
        "login_failed",
        "login",
    ]
    logs = capsys.readouterr().out
    assert "SENSITIVE" not in logs and PASSWORD not in logs and "admin@example.test" not in logs


@pytest.mark.anyio
async def test_admin_writes_are_capped_at_8_kb(production_app: FastAPI) -> None:
    async with client_for(production_app) as client:
        client.headers["origin"] = ORIGIN
        response = await client.post(
            LOGIN, json={"email": "admin@example.test", "password": "x" * 9000}
        )
        assert response.status_code == 413


@pytest.mark.anyio
async def test_sign_in_attempts_are_limited_per_address(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth, "check_password", lambda *_: False)  # keeps the test fast
    body = {"email": "nobody@example.test", "password": "synthetic-wrong-password"}
    statuses = [(await client.post(LOGIN, json=body)).status_code for _ in range(11)]
    assert statuses == [401] * 10 + [429]
    other = await client.post(LOGIN, json={**body, "email": "someone@example.test"})
    assert (other.status_code, code(other)) == (429, "try_later")


@pytest.mark.anyio
async def test_sign_in_errors_never_echo_what_was_typed(client: httpx.AsyncClient) -> None:
    response = await client.post(
        LOGIN, json={"email": "admin@example.test", "password": "SENSITIVE" * 40}
    )
    assert response.status_code == 422 and "SENSITIVE" not in response.text


@pytest.mark.anyio
async def test_a_temporary_password_opens_only_the_password_routes(
    client: httpx.AsyncClient, session: MagicMock
) -> None:
    admin = admin_row(must_change_password=True)
    session.execute.return_value.one_or_none.return_value = (
        admin,
        live_session(admin, "synthetic-token"),
    )
    client.cookies.set(auth.DEV_COOKIE, "synthetic-token")
    for path in ("/api/v1/admin/overview", "/api/v1/admin/households", "/api/v1/admin/audit"):
        blocked = await client.get(path)
        assert (blocked.status_code, code(blocked)) == (403, "admin_password_change_required")
    view = await client.get("/api/v1/admin/session")
    assert view.json() == {"email": "admin@example.test", "must_change_password": True}


def models_in(annotation: Any) -> Iterator[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
        for field in annotation.model_fields.values():
            yield from models_in(field.annotation)
    for argument in get_args(annotation):
        yield from models_in(argument)


# Nothing an admin sees may carry a household's content or contact details (contract).
NEVER = (
    "name",
    "phone",
    "sender",
    "merchant",
    "payee",
    "category",
    "label",
    "note",
    "transcript",
    "message_text",
    "hash",
    "token",
    "secret",
    "key",
    "encrypted",
    "contact",
    "upi",
    "vpa",
    "card",
    "bank",
)
# FinBoy's own ₹299 sales are the only money shown.
OWN_MONEY = {("PaymentRow", "amount_minor"), ("Overview", "received_this_month_minor")}


def test_admin_responses_have_no_field_for_household_content() -> None:
    returned: set[type[BaseModel]] = set()
    for route in admin_routes():
        found = set(models_in(route.response_model))
        assert all(model.__module__ == views.__name__ for model in found), route.path
        returned |= found
    returned |= {views.AdminSession, views.Done}  # sign-in and sign-out build their own reply
    assert len(returned) >= 20
    for model in returned:
        for field in model.model_fields:
            assert not any(word in field for word in NEVER), (model.__name__, field)
            if "amount" in field or field.endswith("_minor"):
                assert (model.__name__, field) in OWN_MONEY


def plan(renewal: str | None = None) -> Any:
    return SimpleNamespace(renewal=renewal)


@pytest.mark.parametrize(
    ("kind", "status", "billing", "renewal", "expected"),
    [
        ("owner", "active", True, None, []),
        ("former_pilot", "active", True, None, []),
        ("self_serve", "deleted", True, None, []),
        ("pending", "active", True, None, ["erase"]),
        ("pilot", "active", True, None, ["suspend", "erase"]),
        ("pilot", "suspended", True, None, ["restore", "erase"]),
        ("self_serve", "suspended", True, "autopay", ["restore", "erase"]),
        ("self_serve", "active", False, None, ["sign_out", "suspend", "erase"]),
        (
            "self_serve",
            "active",
            True,
            "manual",
            ["sign_out", "suspend", "erase", "premium", "pay_link"],
        ),
        (
            "self_serve",
            "active",
            True,
            "autopay",
            ["sign_out", "suspend", "erase", "premium", "pay_link", "autopay_cancel"],
        ),
    ],
)
def test_each_kind_of_household_allows_only_its_own_actions(
    settings: Settings,
    kind: views.Kind,
    status: views.Status,
    billing: bool,
    renewal: str | None,
    expected: list[str],
) -> None:
    configured = settings.model_copy(update={"billing_enabled": billing})
    assert allowed(kind, status, plan(renewal), configured) == expected


def test_household_kinds_and_statuses() -> None:
    other = uuid4()
    assert kind_of(LOCAL_USER_ID, True, None, None) == "owner"
    assert kind_of(other, True, None, None) == "pilot"
    assert kind_of(other, False, "google", NOW) == "self_serve"
    assert kind_of(other, False, "whatsapp", None) == "pending"
    assert kind_of(other, False, None, None) == "former_pilot"
    assert status_of(None, None) == "active"
    assert status_of(None, NOW) == "suspended"
    assert status_of(NOW, NOW) == "deleted"


def test_phone_search_uses_the_stored_sender_hash_and_never_the_number(
    settings: Settings,
) -> None:
    key = Fernet.generate_key().decode()
    keyed = settings.model_copy(update={"token_encryption_key": SecretStr(key)})
    stored = keyed_digest(key.encode(), "sender", "919812345678")
    for typed in ("9812345678", "+91 98123 45678", "91-9812-345678"):
        assert sender_digest(keyed, typed) == stored
    assert sender_digest(keyed, "98123") is None
    assert sender_digest(settings, "9812345678") is None  # no key, no search


def test_every_path_id_is_a_uuid() -> None:
    params = [param for route in admin_routes() for param in route.dependant.path_params]
    assert {param.name for param in params} == {"household_id", "payment_id", "admin_id"}
    assert all(param.field_info.annotation is UUID for param in params)
