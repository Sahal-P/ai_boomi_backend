from unittest.mock import MagicMock
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError

pytestmark = pytest.mark.anyio


async def test_health_checks_database(client: AsyncClient, session: MagicMock) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "finboy-api",
        "version": "0.1.0",
        "database": "connected",
    }
    assert response.headers["cache-control"] == "no-store"
    assert UUID(response.headers["x-request-id"]).version == 4
    session.execute.assert_called_once()
    assert str(session.execute.call_args.args[0]) == "SELECT 1"


async def test_health_reports_database_outage(client: AsyncClient, session: MagicMock) -> None:
    session.execute.side_effect = OperationalError("SELECT secret", {}, Exception("bank-secret"))
    response = await client.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "unavailable"
    assert "secret" not in response.text
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_health_generates_request_ids(client: AsyncClient) -> None:
    first = await client.get("/api/v1/health", headers={"X-Request-ID": "untrusted-user-input"})
    second = await client.get("/api/v1/health")
    assert first.headers["x-request-id"] != "untrusted-user-input"
    assert first.headers["x-request-id"] != second.headers["x-request-id"]


async def test_health_openapi_documents_degraded_response(client: AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()
    responses = schema["paths"]["/api/v1/health"]["get"]["responses"]
    assert "200" in responses
    assert "503" in responses
