"""Explicit local-only final demo launcher; never rewrites ignored per-agent env files."""

import argparse
import json
import os
import subprocess
from collections.abc import Mapping

from sqlalchemy.engine import make_url

from finboy.core.config import Settings


def final_environment(settings: Settings, current: Mapping[str, str]) -> dict[str, str]:
    url = make_url(settings.database_url.get_secret_value())
    if (
        settings.environment == "production"
        or url.host != "127.0.0.1"
        or url.port != 5433
        or url.database not in {"finboy_p5", "finboy"}
    ):
        raise ValueError("Final demo requires reviewed local finboy_p5 or finboy settings")
    result = dict(current)
    result.update(
        {
            "DATABASE_URL": url.set(database="finboy").render_as_string(hide_password=False),
            "ENVIRONMENT": "development",
            "DEMO_TODAY": "2026-10-28",
            "WEB_APP_URL": "http://127.0.0.1:3000",
            "CORS_ORIGINS": '["http://127.0.0.1:3000","http://localhost:3000"]',
            "GOOGLE_OAUTH_REDIRECT_URI": "http://127.0.0.1:8000/api/v1/connections/gmail/callback",
            "WHATSAPP_ENABLED": "false",
            "FINBOY_EXTRACTION_MODE": "offline",
        }
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Reviewed local final demo environment")
    parser.add_argument("action", choices=["check", "migrate", "api"])
    args = parser.parse_args()
    try:
        environment = final_environment(Settings(), os.environ)
    except ValueError:
        parser.exit(1, "Final demo environment was not approved by local checks.\n")
    print(
        json.dumps(
            {
                "host": "127.0.0.1",
                "database": "finboy",
                "api_port": 8000,
                "web_port": 3000,
                "gmail_callback_port": 8000,
                "whatsapp": "disabled_here_use_reviewed_restricted_ingress",
            }
        ),
        flush=True,
    )
    if args.action == "migrate":
        raise SystemExit(subprocess.run(["pnpm", "db:migrate"], env=environment).returncode)
    if args.action == "api":
        os.execvpe(
            "uv",
            [
                "uv",
                "run",
                "--package",
                "finboy-api",
                "uvicorn",
                "finboy.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--no-access-log",
                "--log-config",
                "apps/api/logging.json",
            ],
            environment,
        )


if __name__ == "__main__":
    main()
