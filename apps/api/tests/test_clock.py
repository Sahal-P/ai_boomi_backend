from datetime import UTC, date, datetime, timedelta

import pytest
from finboy.core import clock
from finboy.core.config import Settings


@pytest.mark.parametrize("environment", ["development", "test", "production"])
def test_demo_today_applies_only_outside_production(
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
) -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@localhost/finboy_test",
        environment=environment,
        demo_today="2026-10-28",
    )
    monkeypatch.setattr(clock, "Settings", lambda: settings)
    real_now = datetime(2026, 11, 1, 0, 15, tzinfo=clock.IST)
    monkeypatch.setattr(clock, "now_ist", lambda: real_now)
    expected = real_now.date() if environment == "production" else date(2026, 10, 28)
    assert clock.today_ist() == expected


def test_today_uses_ist_calendar_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@localhost/finboy_test",
    )
    monkeypatch.setattr(clock, "Settings", lambda: settings)
    utc_time = datetime(2026, 10, 31, 19, 0, tzinfo=UTC)
    monkeypatch.setattr(clock, "now_ist", lambda: utc_time.astimezone(clock.IST))
    assert clock.today_ist() == date(2026, 11, 1)


def test_now_is_real_timezone_aware_ist() -> None:
    before = datetime.now(UTC)
    result = clock.now_ist()
    after = datetime.now(UTC)
    assert result.utcoffset() == timedelta(hours=5, minutes=30)
    assert before <= result <= after
