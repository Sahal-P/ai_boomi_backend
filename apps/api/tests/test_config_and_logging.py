import json
import logging

import pytest
from finboy.core.config import Settings
from finboy.core.logging import JsonFormatter
from httpx import AsyncClient
from pydantic import ValidationError

pytestmark = pytest.mark.anyio


def test_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:secret@localhost/finboy_test")
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000"]')
    settings = Settings(_env_file=None)
    assert settings.allowed_origins == ["http://localhost:3000"]
    assert "secret" not in repr(settings)


@pytest.mark.parametrize(
    "url", ["sqlite:///db", "invalid-secret", "postgresql://user:secret@host/db"]
)
def test_settings_requires_psycopg_postgres_url(url: str) -> None:
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url=url)
    assert "secret" not in str(error.value)


def test_settings_rejects_cors_paths() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test:test@localhost/finboy_test",
            cors_origins=["http://localhost:3000/path"],
        )


def test_formatter_omits_exception_and_unapproved_fields() -> None:
    record = logging.LogRecord(
        "uvicorn.error", logging.ERROR, "", 0, "secret-token=%s", ("bank",), None
    )
    record.request_id = "safe-request-id"
    record.authorization = "Bearer secret"
    record.exc_info = (RuntimeError, RuntimeError("private-password"), None)

    result = JsonFormatter().format(record)
    payload = json.loads(result)
    assert payload["request_id"] == "safe-request-id"
    assert payload["event"] == "server.event"
    assert "secret" not in result
    assert "private-password" not in result


async def test_request_logs_do_not_include_url_input(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    await client.get(
        "/bank-account-sensitive?token=secret-query", headers={"Authorization": "Bearer private"}
    )
    output = "\n".join(JsonFormatter().format(record) for record in caplog.records)
    assert "bank-account-sensitive" not in output
    assert "secret-query" not in output
    assert "Bearer private" not in output
    assert '"route": "unmatched"' in output
