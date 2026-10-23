import json
import logging

import pytest
from finboy.core.config import Settings
from finboy.core.logging import JsonFormatter
from httpx import AsyncClient
from pydantic import ValidationError

pytestmark = pytest.mark.anyio


def test_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://test:private-db-password@localhost/finboy_test"
    )
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000"]')
    settings = Settings(_env_file=None)
    assert settings.allowed_origins == ["http://localhost:3000"]
    assert "private-db-password" not in repr(settings)


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


def test_optional_integrations_accept_blank_placeholders() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@localhost/finboy_test",
        openai_api_key="",
        openai_extraction_model="",
        openai_assistant_model="",
        openai_transcribe_model="",
        google_oauth_client_id="",
        google_oauth_client_secret="",
        google_oauth_redirect_uri="",
        google_cloud_project="",
        token_encryption_key="",
        web_app_url="",
        demo_today="",
    )
    assert settings.token_encryption_key is None
    assert settings.google_oauth_redirect_uri is None
    assert settings.web_app_url is None
    assert settings.demo_today is None
    assert settings.openai_extraction_model is None


@pytest.mark.parametrize("key", ["not-a-fernet-key", "é" * 44, "a" * 44])
def test_invalid_token_key_is_redacted(key: str) -> None:
    with pytest.raises(ValidationError) as error:
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test:test@localhost/finboy_test",
            token_encryption_key=key,
        )
    assert key not in str(error.value)


def test_valid_integration_secrets_are_hidden() -> None:
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@localhost/finboy_test",
        token_encryption_key=key,
        google_oauth_client_secret="private-oauth-secret",
    )
    assert settings.token_encryption_key.get_secret_value() == key
    assert key not in repr(settings)
    assert "private-oauth-secret" not in repr(settings)


@pytest.mark.parametrize("url", ["https://untrusted.example", "http://localhost:3000/path"])
def test_web_app_url_must_be_configured_cors_origin(url: str) -> None:
    with pytest.raises(ValidationError, match="WEB_APP_URL"):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test:test@localhost/finboy_test",
            cors_origins=["http://localhost:3000"],
            web_app_url=url,
        )


def test_web_app_url_accepts_matching_origin() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@localhost/finboy_test",
        cors_origins=["http://localhost:3000"],
        web_app_url="http://localhost:3000",
        demo_today="2026-10-28",
    )
    assert str(settings.web_app_url) == "http://localhost:3000/"
    assert settings.demo_today.isoformat() == "2026-10-28"


def test_import_logging_fields_are_allowlisted() -> None:
    fields = {
        "import_run_id": "synthetic-run",
        "stage": "filter",
        "count": 4,
        "provider": "gmail",
        "outcome": "completed",
        "model": "configured-model",
        "latency_ms": 25,
    }
    record = logging.LogRecord("finboy.services", logging.INFO, "", 0, "import.progress", (), None)
    for key, value in fields.items():
        setattr(record, key, value)
    record.email_body = "private-email"
    record.access_token = "private-token"
    result = JsonFormatter().format(record)
    payload = json.loads(result)
    for key, value in fields.items():
        assert payload[key] == value
    assert "private" not in result
