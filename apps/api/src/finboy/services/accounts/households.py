"""Self-serve households (docs/signup-round/contract.md): admission, capacity and erasure.

A household has no personal name. Sign-in identities are digests and masked labels only.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.db.models.accounts import LoginRequest, UsageCounter, UserIdentity
from finboy.db.models.core import User
from finboy.db.models.ledger import (
    Commitment,
    EmailSource,
    ExtractionCache,
    ReviewDecision,
    SourceEvent,
    Transaction,
    TransactionRevision,
)
from finboy.db.models.mail import ImportRun, MailConnection, OAuthState
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppPrompt

# Households that started on WhatsApp but have not agreed yet; newer unknown numbers wait.
PENDING_LIMIT = 200
SIGNUP_LOCK = 0x46424F59534E55  # serializes "is there room?" with the agreement that fills it


def agreed_count(session: Session) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.joined_via.is_not(None),
                User.consented_at.is_not(None),
                User.deleted_at.is_(None),
            )
        )
        or 0
    )


def pending_count(session: Session) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.joined_via.is_not(None),
                User.consented_at.is_(None),
                User.deleted_at.is_(None),
            )
        )
        or 0
    )


def signup_open(session: Session, settings: Settings) -> bool:
    return settings.signup_enabled and agreed_count(session) < settings.signup_limit


def lock_signups(session: Session) -> None:
    """Held until the transaction ends, so two agreements cannot both take the last place."""
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": SIGNUP_LOCK})


def new_household(session: Session, *, joined_via: str, agreed: bool) -> User:
    user = User(
        id=uuid4(),
        display_name="Household",
        joined_via=joined_via,
        consented_at=datetime.now(UTC) if agreed else None,
    )
    session.add(user)
    session.flush()
    return user


def is_self_serve(session: Session, user_id: UUID) -> bool:
    row = session.execute(
        select(User.joined_via, User.deleted_at).where(User.id == user_id)
    ).one_or_none()
    return row is not None and row.joined_via is not None and row.deleted_at is None


def agree(session: Session, settings: Settings, user: User) -> bool:
    """Record a pending household's agreement if there is still room; False when full."""
    if user.consented_at is not None:
        return True
    lock_signups(session)
    if not signup_open(session, settings):
        return False
    user.consented_at = datetime.now(UTC)
    return True


def mask_number(number: str) -> str:
    return "•••• " + number[-4:] if len(number) >= 4 else "••••"


def remove_household_data(session: Session, user_id: UUID) -> dict[str, int]:
    """Delete one household's records, sources, dues and WhatsApp state. Audit history stays."""
    transactions = select(Transaction.id).where(Transaction.user_id == user_id)
    counts: dict[str, int] = {}

    def remove(name: str, statement) -> None:
        counts[name] = session.execute(statement).rowcount or 0

    # Bindings cascade to prompts, reminders, receipts and deliveries.
    remove("whatsapp_bindings", delete(WhatsAppBinding).where(WhatsAppBinding.user_id == user_id))
    remove("review_decisions", delete(ReviewDecision).where(ReviewDecision.user_id == user_id))
    remove("commitments", delete(Commitment).where(Commitment.user_id == user_id))
    remove(
        "transaction_revisions",
        delete(TransactionRevision).where(TransactionRevision.transaction_id.in_(transactions)),
    )
    remove("source_events", delete(SourceEvent).where(SourceEvent.user_id == user_id))
    session.execute(
        update(Transaction)
        .where(Transaction.user_id == user_id)
        .values(possible_duplicate_of_id=None, linked_transaction_id=None, merged_into_id=None)
    )
    remove("transactions", delete(Transaction).where(Transaction.user_id == user_id))
    remove("email_sources", delete(EmailSource).where(EmailSource.user_id == user_id))
    remove("import_runs", delete(ImportRun).where(ImportRun.user_id == user_id))
    remove("mail_connections", delete(MailConnection).where(MailConnection.user_id == user_id))
    # The shared, regenerable extraction cache is cleared as privacy deletion does.
    session.execute(delete(ExtractionCache))
    return counts


def remove_sign_in(session: Session, user_id: UUID) -> None:
    """Sign-in state that only matters while the household exists."""
    session.execute(delete(WhatsAppPrompt).where(WhatsAppPrompt.user_id == user_id))
    session.execute(delete(LoginRequest).where(LoginRequest.user_id == user_id))
    session.execute(delete(UserIdentity).where(UserIdentity.user_id == user_id))
    session.execute(delete(OAuthState).where(OAuthState.user_id == user_id))
    session.execute(delete(UsageCounter).where(UsageCounter.user_id == user_id))


def discard_pending(session: Session, user_id: UUID) -> None:
    """A household that never agreed keeps nothing, not even its row."""
    user = session.get(User, user_id, with_for_update=True)
    if user is None or user.joined_via is None or user.consented_at is not None:
        return
    remove_household_data(session, user_id)
    remove_sign_in(session, user_id)
    session.delete(user)


def erase_household(session: Session, user_id: UUID) -> dict[str, int]:
    """Delete my account: everything goes except the numbered row and audit counts."""
    if user_id == LOCAL_USER_ID:
        raise ValueError("owner_household")
    user = session.get(User, user_id, with_for_update=True)
    if user is None or user.joined_via is None or user.deleted_at is not None:
        raise ValueError("not_found")
    counts = remove_household_data(session, user_id)
    remove_sign_in(session, user_id)
    user.deleted_at = datetime.now(UTC)
    user.session_epoch += 1
    user.data_version += 1
    return counts
