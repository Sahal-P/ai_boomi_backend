import json
import logging
import logging.config
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Only serialize known operational fields; never format raw exception text."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.msg if record.name.startswith("finboy") else "server.event",
        }
        for field in ("request_id", "method", "route", "status_code", "duration_ms", "error_type"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload)


def configure_logging(level: str) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"handlers": ["console"], "level": level},
            "loggers": {
                "uvicorn": {"handlers": ["console"], "level": level, "propagate": False},
                "uvicorn.error": {"handlers": ["console"], "level": level, "propagate": False},
                "uvicorn.access": {"handlers": [], "propagate": False},
                "sqlalchemy.engine": {"level": "WARNING"},
                "httpx": {"level": "WARNING"},
            },
        }
    )
