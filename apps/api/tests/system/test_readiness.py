from unittest.mock import MagicMock

import pytest
from finboy.core.config import Settings
from finboy.main import create_app


@pytest.mark.anyio
async def test_readiness_separates_configuration_from_live_acceptance(client, session):
    session.scalar.side_effect = ["0005_scan_continuation", 0]
    response = await client.get("/api/v1/readiness")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "ready"
    assert result["gmail_configuration"] == "missing"
    assert result["transcription_configuration"] == "missing"
    assert result["english_hindi_tts_configuration"] == "missing"
    assert result["malayalam_tts_configuration"] == "missing"
    assert result["whatsapp_configuration"] == "disabled"
    assert result["live_provider_acceptance"] == "not_checked_by_readiness"
    assert result["import_worker"] == "in_process_not_durable"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.anyio
async def test_readiness_redacts_database_outage(client, session):
    from sqlalchemy.exc import OperationalError

    session.execute.side_effect = OperationalError("SENSITIVE_SQL", {}, RuntimeError("PRIVATE"))
    response = await client.get("/api/v1/readiness")
    assert response.status_code == 503
    assert response.json()["recorded_active_imports"] is None
    assert "SENSITIVE" not in response.text and "PRIVATE" not in response.text
    assert response.json()["database"] == "unavailable"


@pytest.mark.anyio
async def test_startup_interrupts_stale_tasks_only_when_channel_enabled(
    settings: Settings, monkeypatch
):
    context = MagicMock()
    recover = MagicMock()
    monkeypatch.setattr("finboy.main.Session", context)
    monkeypatch.setattr("finboy.main.interrupt_stale", recover)
    app = create_app(settings.model_copy(update={"whatsapp_enabled": True}))
    async with app.router.lifespan_context(app):
        recover.assert_called_once()
        assert recover.call_args.kwargs["before"].tzinfo is not None
