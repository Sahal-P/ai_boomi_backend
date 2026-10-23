from datetime import date
from pathlib import Path
from typing import Literal
from uuid import UUID

from cryptography.fernet import Fernet
from pydantic import AnyHttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

LOCAL_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

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

    openai_extraction_model: str | None = None
    openai_assistant_model: str | None = None
    openai_transcribe_model: str | None = None
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: SecretStr | None = None
    google_oauth_redirect_uri: AnyHttpUrl | None = None
    google_cloud_project: str | None = None
    token_encryption_key: SecretStr | None = None
    web_app_url: AnyHttpUrl | None = None
    demo_today: date | None = None

    @field_validator(
        "openai_api_key",
        "openai_extraction_model",
        "openai_assistant_model",
        "openai_transcribe_model",
        "google_oauth_client_id",
        "google_oauth_client_secret",
        "google_oauth_redirect_uri",
        "google_cloud_project",
        "token_encryption_key",
        "web_app_url",
        "demo_today",
        mode="before",
    )
    @classmethod
    def empty_optional_value(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("token_encryption_key")
    @classmethod
    def require_fernet_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            try:
                Fernet(value.get_secret_value().encode("ascii"))
            except ValueError, UnicodeError:
                raise ValueError("TOKEN_ENCRYPTION_KEY must be a Fernet key") from None
        return value

    @model_validator(mode="after")
    def require_web_origin(self) -> Settings:
        if (
            self.web_app_url is not None
            and str(self.web_app_url).rstrip("/") not in self.allowed_origins
        ):
            raise ValueError("WEB_APP_URL must be one of CORS_ORIGINS")
        return self

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
