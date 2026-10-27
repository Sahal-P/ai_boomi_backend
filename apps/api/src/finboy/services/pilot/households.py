"""Hand enrollment and operator-run erasure of pilot households. Counts only, never content."""

from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.core import User
from finboy.services.accounts.households import remove_household_data
from finboy.services.privacy.audit import audit
from finboy.services.whatsapp.config import MAX_PILOT_HOUSEHOLDS


class PilotError(Exception):
    """Fixed operator error code; never includes household data."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def enroll(session: Session) -> User:
    """Create the next "Pilot household N". No personal name or phone number is stored."""
    active = session.scalar(
        select(func.count()).select_from(User).where(User.pilot.is_(True), User.id != LOCAL_USER_ID)
    )
    if (active or 0) >= MAX_PILOT_HOUSEHOLDS:
        raise PilotError("pilot_limit")
    # Erased households keep their row, so numbers are never reused.
    number = (
        session.scalar(
            select(func.count())
            .select_from(User)
            # Self-serve households are numbered apart (docs/signup-round/contract.md).
            .where(User.id != LOCAL_USER_ID, User.joined_via.is_(None))
        )
        or 0
    ) + 1
    user = User(id=uuid4(), display_name=f"Pilot household {number}", pilot=True)
    session.add(user)
    session.flush()
    audit(session, "pilot.enrolled", "user", user.id, user_id=user.id)
    session.commit()
    return user


def set_owner_pilot(session: Session, *, enabled: bool) -> None:
    """The owner's dogfood week: the owner's WhatsApp number gets the pilot flows."""
    owner = session.get(User, LOCAL_USER_ID, with_for_update=True)
    if owner is None:
        raise PilotError("owner_missing")
    owner.pilot = enabled
    session.commit()


def erase(session: Session, user_id: UUID) -> dict[str, int]:
    """Delete one pilot household's records and WhatsApp state; keep the audit trail.

    The household row stays (audit events reference it) with `pilot` cleared, so its number
    is ignored until it is enrolled again. The shared, regenerable extraction cache is cleared
    as privacy deletion does, so no derived content can survive.
    """
    if user_id == LOCAL_USER_ID:
        raise PilotError("owner_refused")
    user = session.get(User, user_id, with_for_update=True)
    if user is None:
        raise PilotError("not_found")
    counts = remove_household_data(session, user_id)
    user.pilot = False
    user.data_version += 1
    audit(session, "pilot.erased", "user", user_id, user_id=user_id)
    session.commit()
    return counts
