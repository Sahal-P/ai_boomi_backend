from datetime import date
from pathlib import Path
from typing import Literal
from uuid import UUID

from cryptography.fernet import Fernet
from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
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
    resend_api_key: SecretStr | None = None

    openai_extraction_model: str | None = None
    openai_assistant_model: str | None = None
    openai_transcribe_model: str | None = None
    openai_vision_model: str | None = None
    # "groq" sends English/Hindi to Groq Whisper (Malayalam stays on OpenAI); "sarvam" sends all
    # three languages to Sarvam Saaras (docs/malayalam-round/contract.md).
    speech_transcribe_provider: Literal["openai", "groq", "sarvam"] = "openai"
    groq_api_key: SecretStr | None = None
    groq_transcribe_model: str | None = None
    groq_base_url: AnyHttpUrl = "https://api.groq.com/openai/v1"
    sarvam_api_key: SecretStr | None = None
    sarvam_stt_model: str | None = None
    sarvam_tts_model: str | None = None
    # A Bulbul speaker name, chosen by listening; Malayalam replies only.
    sarvam_tts_speaker_ml: str | None = Field(default=None, pattern=r"^[a-z]{2,24}$")
    sarvam_base_url: AnyHttpUrl = "https://api.sarvam.ai"
    # Malayalam spoken replies; English and Hindi stay on Resemble.
    malayalam_tts_provider: Literal["gemini", "sarvam"] = "gemini"
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: SecretStr | None = None
    google_oauth_redirect_uri: AnyHttpUrl | None = None
    google_cloud_project: str | None = None
    token_encryption_key: SecretStr | None = None
    web_app_url: AnyHttpUrl | None = None
    demo_today: date | None = None
    household_password_hash: SecretStr | None = None
    web_session_key: SecretStr | None = None

    # Provider model/voice IDs are configured only after a synthetic live capability check.
    resemble_tts_base_url: AnyHttpUrl = "https://f.cluster.resemble.ai"
    gemini_tts_base_url: AnyHttpUrl = "https://generativelanguage.googleapis.com/v1beta"
    ffprobe_binary: str = "ffprobe"
    resemble_api_key: SecretStr | None = None
    resemble_project_uuid: str | None = None
    resemble_voice_uuid_en: str | None = None
    resemble_voice_uuid_hi: str | None = None
    resemble_tts_model: str | None = None
    gemini_api_key: SecretStr | None = None
    gemini_tts_model: str | None = None
    gemini_tts_voice: str | None = None
    assistant_timeout_seconds: float = Field(default=30, ge=1, le=60)
    speech_timeout_seconds: float = Field(default=30, ge=1, le=60)
    provider_max_retries: int = Field(default=1, ge=0, le=3)
    speech_max_audio_bytes: int = Field(default=3 * 1024 * 1024, ge=1, le=3 * 1024 * 1024)
    speech_max_duration_seconds: int = Field(default=30, ge=1, le=30)
    speech_max_text_characters: int = Field(default=600, ge=1, le=600)
    ffmpeg_binary: str = "ffmpeg"

    whatsapp_enabled: bool = False
    whatsapp_app_id: str | None = None
    whatsapp_app_secret: SecretStr | None = None
    whatsapp_verify_token: SecretStr | None = None
    whatsapp_access_token: SecretStr | None = None
    whatsapp_phone_number_id: SecretStr | None = None
    whatsapp_business_account_id: SecretStr | None = None
    whatsapp_graph_api_version: str | None = None
    # JSON object: approved provider sender identifier -> local user UUID. Never log or return it.
    whatsapp_sender_allowlist_json: SecretStr | None = None
    whatsapp_timeout_seconds: float = Field(default=15, ge=1, le=60)
    whatsapp_max_webhook_bytes: int = Field(default=256 * 1024, ge=1, le=1024 * 1024)
    whatsapp_ingress_port: int = Field(default=8095, ge=1024, le=65535)
    # Village pilot: an approved Hindi utility template for due reminders (name only). Unset
    # means reminders are added to replies inside the 24-hour window instead.
    whatsapp_reminder_template: str | None = Field(default=None, pattern=r"^[a-z0-9_]{1,64}$")

    # Sign-up round (docs/signup-round/contract.md). Off until the human enables it; none of
    # these values is a secret, and the web app reads them from GET /api/v1/auth/session.
    signup_enabled: bool = False
    signup_limit: int = Field(default=100, ge=0, le=100_000)
    session_days: int = Field(default=30, ge=1, le=90)
    daily_ai_limit: int = Field(default=100, ge=1, le=10_000)
    daily_voice_limit: int = Field(default=60, ge=1, le=10_000)
    google_signin_client_id: str | None = Field(
        default=None, pattern=r"^[0-9]{6,32}-[a-z0-9]{8,64}\.apps\.googleusercontent\.com$"
    )
    # The business number people message, digits only. It is printed on posters, not secret.
    whatsapp_public_number: str | None = Field(default=None, pattern=r"^[0-9]{7,20}$")
    gmail_for_new_accounts: bool = False

    @field_validator(
        "resemble_api_key",
        "resemble_project_uuid",
        "resemble_voice_uuid_en",
        "resemble_voice_uuid_hi",
        "resemble_tts_model",
        "gemini_api_key",
        "gemini_tts_model",
        "gemini_tts_voice",
        "whatsapp_app_id",
        "whatsapp_app_secret",
        "whatsapp_verify_token",
        "whatsapp_access_token",
        "whatsapp_phone_number_id",
        "whatsapp_business_account_id",
        "whatsapp_graph_api_version",
        "whatsapp_sender_allowlist_json",
        "whatsapp_reminder_template",
        "openai_api_key",
        "resend_api_key",
        "openai_extraction_model",
        "openai_assistant_model",
        "openai_transcribe_model",
        "openai_vision_model",
        "groq_api_key",
        "groq_transcribe_model",
        "sarvam_api_key",
        "sarvam_stt_model",
        "sarvam_tts_model",
        "sarvam_tts_speaker_ml",
        "google_oauth_client_id",
        "google_oauth_client_secret",
        "google_oauth_redirect_uri",
        "google_cloud_project",
        "token_encryption_key",
        "web_app_url",
        "demo_today",
        "household_password_hash",
        "web_session_key",
        "google_signin_client_id",
        "whatsapp_public_number",
        mode="before",
    )
    @classmethod
    def empty_optional_value(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator(
        "resemble_tts_base_url", "gemini_tts_base_url", "groq_base_url", "sarvam_base_url"
    )
    @classmethod
    def require_provider_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if (
            value.scheme != "https"
            or value.username
            or value.password
            or value.query
            or value.fragment
        ):
            raise ValueError("Provider base URLs must use HTTPS without credentials or queries")
        return value

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

    @model_validator(mode="after")
    def require_production_access(self) -> Settings:
        if self.environment == "production":
            if not self.household_password_hash or not self.web_session_key or not self.web_app_url:
                raise ValueError("Production requires household access settings")
            if self.web_app_url.scheme != "https":
                raise ValueError("Production requires an HTTPS web origin")
            try:
                Fernet(self.web_session_key.get_secret_value().encode("ascii"))
                from finboy.core.access import valid_password_hash

                if not valid_password_hash(self.household_password_hash.get_secret_value()):
                    raise ValueError
            except ValueError, UnicodeError:
                raise ValueError("Production requires valid household access settings") from None
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
