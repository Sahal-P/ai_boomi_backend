"""Pay links sent on WhatsApp (docs/subscription-round/contract.md).

`<WEB_APP_URL>/pay#<token>`: the token sits in the URL fragment, so neither the web server nor a
link preview ever sees it. It is a Fernet token under the session key naming one household, its
session epoch and its language for 7 days; "sign out everywhere" and deletion void it. It lets the
page show that household's price and start a checkout for it — nothing else.
"""

from dataclasses import dataclass
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.access import session_key
from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.core.languages import Language
from finboy.db.models.core import User

PREFIX = "finboy:pay:v1:"
SECONDS = 7 * 24 * 60 * 60
LANGUAGES = ("en", "hi", "ml")


@dataclass(frozen=True)
class Holder:
    user_id: UUID
    language: Language


def token(settings: Settings, user_id: UUID, epoch: int, language: str) -> str:
    language = language if language in LANGUAGES else "en"
    payload = f"{PREFIX}{user_id}:{epoch}:{language}".encode("ascii")
    return Fernet(session_key(settings)).encrypt(payload).decode()


def link(settings: Settings, user_id: UUID, epoch: int, language: str) -> str:
    base = str(settings.web_app_url).rstrip("/")
    return f"{base}/pay#{token(settings, user_id, epoch, language)}"


def read(session: Session, settings: Settings, value: str) -> Holder:
    """The household a pay link names, while it is fresh and the household still exists."""
    if not value or len(value) > 512:
        raise AccessError("link_expired")
    try:
        text = Fernet(session_key(settings)).decrypt(value.encode(), ttl=SECONDS).decode("ascii")
        if not text.startswith(PREFIX):
            raise ValueError
        user, epoch, language = text.removeprefix(PREFIX).split(":")
        user_id, epoch_number = UUID(user), int(epoch)
    except InvalidToken, ValueError, UnicodeError:
        raise AccessError("link_expired") from None
    row = session.execute(
        select(User.session_epoch, User.deleted_at, User.pilot).where(User.id == user_id)
    ).one_or_none()
    if row is None or row.deleted_at is not None or row.pilot or row.session_epoch != epoch_number:
        raise AccessError("link_expired")
    return Holder(user_id, language if language in LANGUAGES else "en")  # type: ignore[arg-type]
