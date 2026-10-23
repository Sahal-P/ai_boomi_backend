from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

API_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=API_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: SecretStr
    cors_origins: list[AnyHttpUrl] = []
    openai_api_key: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def require_postgres(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except ArgumentError:
            raise ValueError("DATABASE_URL must be a PostgreSQL psycopg URL") from None
        if url.drivername != "postgresql+psycopg" or not url.host or not url.database:
            raise ValueError("DATABASE_URL must be a PostgreSQL psycopg URL")
        return value

    @field_validator("cors_origins")
    @classmethod
    def require_origins(cls, values: list[AnyHttpUrl]) -> list[AnyHttpUrl]:
        for value in values:
            if (
                value.username
                or value.password
                or value.query
                or value.fragment
                or value.path != "/"
            ):
                raise ValueError("CORS_ORIGINS must contain origins without paths or credentials")
        return values

    @property
    def allowed_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.cors_origins]
