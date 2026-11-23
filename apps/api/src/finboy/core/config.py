import re
from datetime import date
from pathlib import Path
from typing import Literal
from uuid import UUID

from cryptography.fernet import Fernet
from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from finboy.core.languages import Language

LOCAL_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
ModelProvider = Literal["openai", "deepseek"]
DEEPSEEK_MODEL = "deepseek-flash"

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
    # Where a new household feedback report is announced (docs/feedback-round/contract.md).
    feedback_email: str | None = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    openai_extraction_model: str | None = None
    openai_assistant_model: str | None = None
    openai_transcribe_model: str | None = None
    openai_vision_model: str | None = None
    entry_parser_provider: ModelProvider = "openai"
    assistant_provider: ModelProvider = "openai"
    advisor_answer_provider: ModelProvider = "openai"
    email_extraction_provider: ModelProvider = "openai"
    screenshot_provider: ModelProvider = "openai"
    deepseek_api_key: SecretStr | None = None
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
    # Malayalam spoken replies (English and Hindi stay on Resemble): Sarvam Bulbul, or off so
    # Malayalam replies are written only. Gemini was removed on 20 Nov 2026.
    malayalam_tts_provider: Literal["off", "sarvam"] = "off"
    # Liquid AI d1-ultra sorts messages, questions and photos so a sure answer need not wait for
    # the slower model call (docs/triage-round/contract.md). Off until the human releases it.
    liquid_api_key: SecretStr | None = None
    liquid_decision_model: str | None = None
    liquid_base_url: AnyHttpUrl = "https://api.liquid.ai"
    triage_enabled: bool = False
    triage_timeout_seconds: float = Field(default=2, ge=0.5, le=10)
    # Only languages that passed the offline gate (`pnpm eval:triage`) are sorted.
    triage_languages: list[Language] = ["en", "hi", "ml"]
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
    ffprobe_binary: str = "ffprobe"
    resemble_api_key: SecretStr | None = None
    resemble_project_uuid: str | None = None
    resemble_voice_uuid_en: str | None = None
    resemble_voice_uuid_hi: str | None = None
    resemble_tts_model: str | None = None
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
    # Money manager: an approved utility template (English, Hindi and Malayalam) for the opt-in
    # monthly check-in (name only). Unset means it is neither offered nor sent.
    whatsapp_checkin_template: str | None = Field(default=None, pattern=r"^[a-z0-9_]{1,64}$")

    # Advisor round (docs/advisor-round/contract.md): one money coach on the web and WhatsApp that
    # reads the household's records through read-only tools, keeps its chats and remembers what
    # matters. Off until the human releases it; Ask then answers as before.
    advisor_enabled: bool = False
    # Defaults to OPENAI_ASSISTANT_MODEL; set only after a live capability check.
    openai_advisor_model: str | None = None
    advisor_reasoning_effort: Literal["none", "minimal", "low", "medium", "high"] = "low"
    advisor_timeout_seconds: float = Field(default=20, ge=1, le=60)
    advisor_max_tool_rounds: int = Field(default=4, ge=1, le=8)
    advisor_history_turns: int = Field(default=8, ge=0, le=30)
    # Kept per household; the most relevant `advisor_memory_prompt` of them reach each answer.
    advisor_memory_limit: int = Field(default=300, ge=1, le=1000)
    advisor_memory_prompt: int = Field(default=40, ge=5, le=200)
    # Phase 2: the reviewed money-knowledge library (off until the human reviews and releases it)
    # and embeddings for semantic search; unset embeddings mean keyword search only.
    knowledge_enabled: bool = False
    openai_embedding_model: str | None = None  # set only after a live capability check
    advisor_embedding_dimensions: int = Field(default=256, ge=64, le=3072)
    # Names and search round (docs/names-search-round/contract.md): public prices and loan rates
    # from OpenAI's web search, whichever model answers. Off until the human releases it.
    advisor_web_search_enabled: bool = False
    # Advisor edits round (docs/advisor-edits-round/contract.md): Ask proposes category,
    # own-transfer, payee-name, budget and goal changes, applied only on the household's tap and
    # undone in one step. Off until the human releases it; Ask then only reads.
    advisor_edits_enabled: bool = False
    # Phase 3: the proactive coach. Opted-in WhatsApp households hear at most one nudge a day and
    # Home shows "For you". Off until the human releases it; it also needs ADVISOR_ENABLED.
    coach_enabled: bool = False
    # An approved utility template for nudges outside WhatsApp's 24-hour window (name only).
    # Unset means nudges reach only households that wrote to FinBoy in the last day.
    whatsapp_coach_template: str | None = Field(default=None, pattern=r"^[a-z0-9_]{1,64}$")

    # Statement round (docs/statement-round/contract.md): Google Pay statement imports on the web
    # and by WhatsApp document. Off until the human enables it; the web reads it from the session.
    statement_import_enabled: bool = False

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

    # Subscription round (docs/subscription-round/contract.md). Off until the human releases it;
    # while off every household has every feature. The PayU salt never leaves the backend.
    billing_enabled: bool = False
    # Households that signed up before this IST date get their 30-day trial from it instead.
    billing_launch_date: date | None = None
    # False only to test billing locally as the owner (loopback development acts as the owner).
    billing_owner_included: bool = True
    payu_environment: Literal["test", "production"] = "test"
    payu_merchant_key: str | None = Field(default=None, pattern=r"^[A-Za-z0-9]{4,32}$")
    payu_merchant_salt: SecretStr | None = None
    # UPI AutoPay and card auto-renew ("Pay and Subscribe"), once PayU enables Subscriptions.
    payu_autopay_enabled: bool = False
    # The API's public origin; PayU returns the browser to <origin>/api/v1/payu/return.
    api_public_url: AnyHttpUrl | None = None

    # Admin round (docs/admin-round/contract.md): how long an admin session lasts. Admin accounts
    # live in the database, so no admin secret is configured here.
    admin_session_hours: int = Field(default=8, ge=1, le=24)

    # Conversation round (docs/conversation-round/contract.md): for households that agreed, every
    # WhatsApp message in and out is kept, with voice notes and photos in a private Cloudflare R2
    # bucket, and admins can read and open them. Off until the human releases it.
    conversation_log_enabled: bool = False
    r2_account_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    r2_access_key_id: SecretStr | None = None
    r2_secret_access_key: SecretStr | None = None
    r2_bucket: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")
    # The folder every key starts with. Unset means one per environment, so local development
    # never writes beside production's files.
    r2_prefix: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,62}/$")

    @field_validator(
        "resemble_api_key",
        "resemble_project_uuid",
        "resemble_voice_uuid_en",
        "resemble_voice_uuid_hi",
        "resemble_tts_model",
        "whatsapp_app_id",
        "whatsapp_app_secret",
        "whatsapp_verify_token",
        "whatsapp_access_token",
        "whatsapp_phone_number_id",
        "whatsapp_business_account_id",
        "whatsapp_graph_api_version",
        "whatsapp_sender_allowlist_json",
        "whatsapp_reminder_template",
        "whatsapp_checkin_template",
        "whatsapp_coach_template",
        "openai_api_key",
        "deepseek_api_key",
        "resend_api_key",
        "feedback_email",
        "openai_extraction_model",
        "openai_assistant_model",
        "openai_transcribe_model",
        "openai_vision_model",
        "openai_advisor_model",
        "openai_embedding_model",
        "groq_api_key",
        "groq_transcribe_model",
        "sarvam_api_key",
        "sarvam_stt_model",
        "sarvam_tts_model",
        "sarvam_tts_speaker_ml",
        "liquid_api_key",
        "liquid_decision_model",
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
        "billing_launch_date",
        "payu_merchant_key",
        "payu_merchant_salt",
        "api_public_url",
        "r2_account_id",
        "r2_access_key_id",
        "r2_secret_access_key",
        "r2_bucket",
        "r2_prefix",
        mode="before",
    )
    @classmethod
    def empty_optional_value(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("malayalam_tts_provider", mode="before")
    @classmethod
    def removed_malayalam_provider(cls, value: object) -> object:
        # An older .env still names the removed Gemini voice: Malayalam replies stay written.
        return "off" if value == "gemini" else value

    @field_validator(
        "resemble_tts_base_url",
        "groq_base_url",
        "sarvam_base_url",
        "liquid_base_url",
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

    @field_validator("payu_merchant_salt")
    @classmethod
    def require_salt(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not re.fullmatch(r"[\x21-\x7e]{8,128}", value.get_secret_value()):
            raise ValueError("PAYU_MERCHANT_SALT must be the salt copied from PayU")
        return value

    @model_validator(mode="after")
    def require_billing(self) -> Settings:
        if not self.billing_enabled:
            return self
        if not self.payu_merchant_key or not self.payu_merchant_salt or not self.api_public_url:
            raise ValueError("Billing requires PayU credentials and API_PUBLIC_URL")
        if not self.web_app_url or not self.token_encryption_key:
            raise ValueError("Billing requires WEB_APP_URL and TOKEN_ENCRYPTION_KEY")
        url = self.api_public_url
        if url.username or url.password or url.query or url.fragment or url.path not in {None, "/"}:
            raise ValueError("API_PUBLIC_URL must be an origin without a path")
        # PayU accepts at most 50 characters for surl, furl and curl.
        if len(self.payu_return_url) > 50:
            raise ValueError("API_PUBLIC_URL is too long for PayU's return URL")
        if self.environment == "production" and (
            self.payu_environment != "production"
            or url.scheme != "https"
            or self.billing_launch_date is None
        ):
            raise ValueError(
                "Production billing requires live PayU, an HTTPS API_PUBLIC_URL and a launch date"
            )
        return self

    @model_validator(mode="after")
    def require_conversation_store(self) -> Settings:
        if self.conversation_log_enabled and not (
            self.r2_account_id
            and self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_bucket
        ):
            raise ValueError("CONVERSATION_LOG_ENABLED requires the R2 account, keys and bucket")
        return self

    @property
    def media_prefix(self) -> str:
        if self.r2_prefix:
            return self.r2_prefix
        production = self.environment == "production"
        return "finboy-conversations/" if production else "finboy-conversations-dev/"

    @property
    def feedback_prefix(self) -> str:
        """Feedback screenshots sit in their own folder of the same private R2 bucket."""
        return "finboy-feedback/" if self.environment == "production" else "finboy-feedback-dev/"

    @property
    def payu_return_url(self) -> str:
        return str(self.api_public_url).rstrip("/") + "/api/v1/payu/return"

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
    def advisor_model(self) -> str | None:
        return self.advisor_model_for(self.assistant_provider)

    def advisor_model_for(self, provider: ModelProvider) -> str | None:
        return self.ai_model(provider, self.openai_advisor_model or self.openai_assistant_model)

    def ai_key(self, provider: ModelProvider) -> SecretStr | None:
        return self.deepseek_api_key if provider == "deepseek" else self.openai_api_key

    def ai_model(self, provider: ModelProvider, openai_model: str | None) -> str | None:
        return DEEPSEEK_MODEL if provider == "deepseek" else openai_model

    @property
    def coach_active(self) -> bool:
        """The coach runs only with the advisor, which writes its nudges."""
        return self.coach_enabled and self.advisor_enabled

    @property
    def allowed_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.cors_origins]
