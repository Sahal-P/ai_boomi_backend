"""Settings and constants shared by the billing tests."""

from cryptography.fernet import Fernet
from finboy.core.config import Settings

KEY = "tEsTkY"
SALT = "s4ltForTestsOnly0123456789abcdef"
ENCRYPTION_KEY = Fernet.generate_key().decode()


def billing_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "database_url": "postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        "cors_origins": ["http://127.0.0.1:3071"],
        "environment": "test",
        "web_app_url": "http://127.0.0.1:3071",
        "token_encryption_key": ENCRYPTION_KEY,
        "billing_enabled": True,
        "billing_owner_included": False,
        "payu_merchant_key": KEY,
        "payu_merchant_salt": SALT,
        "api_public_url": "http://127.0.0.1:8071",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]
