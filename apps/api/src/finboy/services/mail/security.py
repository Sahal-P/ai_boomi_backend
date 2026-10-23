import base64
import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken


class MailError(Exception):
    """Only fixed, application-owned codes may cross the service boundary."""

    CODES = frozenset(
        {
            "gmail_not_configured",
            "invalid_state",
            "consent_denied",
            "oauth_failed",
            "scope_missing",
            "refresh_token_missing",
            "gmail_unavailable",
            "reconnect_required",
            "revoke_failed",
            "connection_inactive",
            "import_failed",
            "import_cancelled",
            "demo_unavailable",
            "invalid_eml",
            "upload_limit",
            "import_busy",
        }
    )

    def __init__(self, code: str) -> None:
        self.code = code if code in self.CODES else "import_failed"
        super().__init__(self.code)


def sha256(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def pkce_challenge(verifier: str) -> str:
    return (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )


def random_secret() -> str:
    return secrets.token_urlsafe(48)


def cipher(key: str) -> Fernet:
    try:
        return Fernet(key.encode())
    except ValueError, TypeError:
        raise MailError("gmail_not_configured") from None


def encrypt(key: str, value: str) -> bytes:
    return cipher(key).encrypt(value.encode())


def decrypt(key: str, value: bytes) -> str:
    try:
        return cipher(key).decrypt(value).decode()
    except InvalidToken, UnicodeError:
        raise MailError("reconnect_required") from None


def mask_email(address: str) -> str:
    local, separator, domain = address.partition("@")
    if not separator or not local or not domain or len(address) > 254:
        raise MailError("oauth_failed")
    # The domain can also identify a person; keep only its final suffix.
    suffix = domain.rsplit(".", 1)[-1]
    return f"{local[0]}***@***.{suffix}" if suffix.isalpha() else f"{local[0]}***@***"
