from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode
from uuid import UUID

from cryptography.fernet import InvalidToken
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from finboy.core.clock import now_ist
from finboy.core.config import Settings
from finboy.db.models.mail import MailConnection, OAuthState
from finboy.services.mail.google import READ_SCOPE, GoogleClient
from finboy.services.mail.security import (
    MailError,
    cipher,
    decrypt,
    encrypt,
    mask_email,
    pkce_challenge,
    random_secret,
    sha256,
)

HANDOFF_SECONDS = 60
HANDOFF_PREFIX = "finboy:gmail-handoff:v1:"


@dataclass(frozen=True, repr=False)
class OAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    encryption_key: str

    @classmethod
    def from_settings(cls, settings: Settings) -> OAuthConfig:
        if not (
            settings.google_oauth_client_id
            and settings.google_oauth_client_secret
            and settings.google_oauth_redirect_uri
            and settings.token_encryption_key
            and settings.web_app_url
        ):
            raise MailError("gmail_not_configured")
        return cls(
            settings.google_oauth_client_id,
            settings.google_oauth_client_secret.get_secret_value(),
            str(settings.google_oauth_redirect_uri),
            settings.token_encryption_key.get_secret_value(),
        )

    def google(self) -> GoogleClient:
        return GoogleClient(self.client_id, self.client_secret, self.redirect_uri)


def create_state(
    session: Session, config: OAuthConfig, *, lifetime: timedelta, user_id: UUID
) -> tuple[str, str]:
    state, verifier = random_secret(), random_secret()
    session.add(
        OAuthState(
            user_id=user_id,
            state_sha256=sha256(state),
            encrypted_code_verifier=encrypt(config.encryption_key, verifier),
            expires_at=now_ist() + lifetime,
        )
    )
    session.commit()
    return state, verifier


def create_authorization_handoff(session: Session, config: OAuthConfig, user_id: UUID) -> str:
    state, _ = create_state(
        session, config, lifetime=timedelta(seconds=HANDOFF_SECONDS), user_id=user_id
    )
    return encrypt(config.encryption_key, HANDOFF_PREFIX + state).decode()


def consume_authorization_handoff(
    session: Session, config: OAuthConfig, ticket: str
) -> tuple[str, str]:
    if not ticket or len(ticket) > 1024:
        raise MailError("invalid_state")
    try:
        payload = (
            cipher(config.encryption_key).decrypt(ticket.encode(), ttl=HANDOFF_SECONDS).decode()
        )
    except InvalidToken, UnicodeError:
        raise MailError("invalid_state") from None
    if not payload.startswith(HANDOFF_PREFIX):
        raise MailError("invalid_state")
    _, user_id = consume_state(session, config, payload.removeprefix(HANDOFF_PREFIX))
    # Use a fresh OAuth state: the cross-host handoff cannot replace the callback cookie.
    return authorize(session, config, user_id)


def authorize(session: Session, config: OAuthConfig, user_id: UUID) -> tuple[str, str]:
    state, verifier = create_state(session, config, lifetime=timedelta(minutes=10), user_id=user_id)
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": READ_SCOPE,
            "state": state,
            "code_challenge": pkce_challenge(verifier),
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "false",
        }
    ), state


def consume_state(session: Session, config: OAuthConfig, state: str) -> tuple[str, UUID]:
    """The PKCE verifier and the household that started this authorization."""
    if not state or len(state) > 256:
        raise MailError("invalid_state")
    # Conditional UPDATE makes reuse fail even across simultaneous callbacks/workers.
    row = session.execute(
        update(OAuthState)
        .where(
            OAuthState.state_sha256 == sha256(state),
            OAuthState.used_at.is_(None),
            OAuthState.expires_at > now_ist(),
        )
        .values(used_at=now_ist())
        .execution_options(synchronize_session=False)
        .returning(OAuthState.encrypted_code_verifier, OAuthState.user_id)
    ).first()
    session.commit()
    if row is None:
        raise MailError("invalid_state")
    return decrypt(config.encryption_key, row[0]), row[1]


def finish_connection(
    session: Session,
    config: OAuthConfig,
    google: GoogleClient,
    *,
    code: str,
    verifier: str,
    user_id: UUID,
) -> MailConnection:
    tokens = google.exchange(code, verifier)
    scopes = tokens.get("scope", "")
    if not isinstance(scopes, str) or set(scopes.split()) != {READ_SCOPE}:
        raise MailError("scope_missing")
    refresh, access = tokens.get("refresh_token"), tokens.get("access_token")
    if not isinstance(refresh, str) or not refresh:
        raise MailError("refresh_token_missing")
    if not isinstance(access, str) or not access:
        raise MailError("oauth_failed")
    profile = google.get("profile", access)
    email = profile.get("emailAddress")
    if not isinstance(email, str):
        raise MailError("oauth_failed")
    digest = sha256(email.strip().lower())
    # Revoked rows are reused too, preserving their historical audit identifiers.
    connection = session.scalar(
        select(MailConnection)
        .where(
            MailConnection.user_id == user_id,
            MailConnection.account_email_sha256 == digest,
        )
        .with_for_update()
    )
    if connection is None:
        connection = MailConnection(user_id=user_id, provider="gmail", account_email_sha256=digest)
        session.add(connection)
    connection.account_email_masked = mask_email(email)
    connection.encrypted_refresh_token = encrypt(config.encryption_key, refresh)
    connection.scopes = [READ_SCOPE]
    connection.status = "active"
    connection.connected_at = now_ist()
    connection.revoked_at = None
    session.flush()
    return connection
