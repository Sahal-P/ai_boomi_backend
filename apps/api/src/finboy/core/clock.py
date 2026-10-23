"""Business dates use IST; the demo override never changes real audit timestamps."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from finboy.core.config import Settings

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def today_ist() -> date:
    settings = Settings()
    if settings.environment != "production" and settings.demo_today is not None:
        return settings.demo_today
    return now_ist().date()
