"""Erasing a household: one sequence for "Delete my account" and an admin's erase.

docs/signup-round/contract.md and docs/admin-round/contract.md. Both paths follow the same rules,
so an operator can never erase more, or less, than the household itself could.
"""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.db.models.mail import MailConnection
from finboy.services.accounts.households import discard_pending, erase_household
from finboy.services.billing import mandates
from finboy.services.imports.locking import import_lock
from finboy.services.mail.oauth import OAuthConfig
from finboy.services.mail.security import MailError, decrypt
from finboy.services.pilot import households as pilot_households
from finboy.services.privacy.audit import audit


def _nothing() -> None:
    return None


def revoke_gmail(session: Session, settings: Settings, user_id: UUID) -> None:
    """Best effort: FinBoy deletes the grant either way; a failed revoke is audited."""
    tokens = session.scalars(
        select(MailConnection).where(
            MailConnection.user_id == user_id, MailConnection.encrypted_refresh_token.is_not(None)
        )
    ).all()
    if not tokens:
        return
    try:
        config = OAuthConfig.from_settings(settings)
    except MailError:
        return
    google = config.google()
    try:
        for connection in tokens:
            try:
                google.revoke(decrypt(config.encryption_key, connection.encrypted_refresh_token))
                audit(session, "gmail.revoked", "connection", connection.id, user_id=user_id)
            except MailError:
                audit(
                    session,
                    "gmail.revoke_failed",
                    "connection",
                    connection.id,
                    user_id=user_id,
                    result="failure",
                )
    finally:
        google.close()


def erase_self_serve(
    session: Session,
    settings: Settings,
    engine: Engine,
    user_id: UUID,
    *,
    also: Callable[[], None] = _nothing,
) -> dict[str, int]:
    """AutoPay off at the bank, Gmail revoked, records erased and audited, in one commit.

    AutoPay goes first because `mandates.turn_off` commits or rolls back by itself, which would
    otherwise drop audit rows added before it. `also` adds the caller's own audit entry to the
    same transaction. Raises MailError("import_busy") while an import runs, and ValueError for
    the owner or a household that isn't self-serve.
    """
    with import_lock(engine, user_id):
        mandates.revoke_before_erasure(session, settings, user_id)
        revoke_gmail(session, settings, user_id)
        try:
            counts = erase_household(session, user_id)
        except ValueError:
            session.rollback()
            raise
        audit(session, "account.deleted", "user", user_id, user_id=user_id)
        also()
        session.commit()
    return counts


def erase_pilot(
    session: Session, engine: Engine, user_id: UUID, *, also: Callable[[], None] = _nothing
) -> dict[str, int]:
    """A pilot household's records and WhatsApp state, as `pilot.cli erase` does. Raises
    PilotError or MailError("import_busy"); `pilot_households.erase` commits `also` with it."""
    with import_lock(engine, user_id):
        also()
        return pilot_households.erase(session, user_id)


def discard(session: Session, user_id: UUID, *, also: Callable[[], None] = _nothing) -> None:
    """A sign-up that never agreed: nothing is kept, as when the person answers No."""
    discard_pending(session, user_id)
    also()
    session.commit()
