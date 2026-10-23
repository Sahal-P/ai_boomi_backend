import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

pytestmark = pytest.mark.anyio


async def test_not_found_uses_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/does-not-exist?token=private")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": "Not Found",
            "request_id": response.headers["x-request-id"],
        }
    }
    assert "private" not in response.text


async def test_method_not_allowed_preserves_allow_header(client: AsyncClient) -> None:
    response = await client.post("/api/v1/health")
    assert response.status_code == 405
    assert "GET" in response.headers["allow"]
    assert response.json()["error"]["message"] == "Method Not Allowed"


async def test_unexpected_error_is_redacted(app: FastAPI) -> None:
    @app.get("/test-error")
    def fail() -> None:
        raise RuntimeError("postgresql://user:private-password@host/db")

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/test-error", headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert "private-password" not in response.text
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_http_exception_detail_is_redacted(app: FastAPI) -> None:
    @app.get("/test-http-error")
    def fail() -> None:
        raise HTTPException(status_code=400, detail="bank-account-number")

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/test-http-error")
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Bad Request"
    assert "bank-account-number" not in response.text


class ValidationInput(BaseModel):
    amount: int


async def test_validation_does_not_echo_input(app: FastAPI) -> None:
    @app.post("/test-validation")
    def validate(body: ValidationInput) -> ValidationInput:
        return body

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.post(
            "/test-validation", json={"amount": "sensitive-financial-data"}
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "sensitive-financial-data" not in response.text


async def test_cors_allows_only_configured_origin(client: AsyncClient) -> None:
    allowed = await client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    blocked = await client.options(
        "/api/v1/health",
        headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert blocked.status_code == 400
    assert "access-control-allow-origin" not in blocked.headers
