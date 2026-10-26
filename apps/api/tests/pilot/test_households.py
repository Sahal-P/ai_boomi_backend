from uuid import uuid4

import pytest
from finboy.core.config import LOCAL_USER_ID
from finboy.db.models import User
from finboy.db.models.ledger import (
    Commitment,
    EmailSource,
    ExtractionCache,
    ReviewDecision,
    SourceEvent,
    Transaction,
    TransactionRevision,
)
from finboy.db.models.mail import AuditEvent, ImportRun
from finboy.db.models.whatsapp import (
    WhatsAppBinding,
    WhatsAppDelivery,
    WhatsAppPrompt,
    WhatsAppReceipt,
)
from finboy.services.imports.locking import IMPORT_LOCK, lock_key
from finboy.services.pilot import households
from finboy.services.whatsapp.config import MAX_PILOT_HOUSEHOLDS
from sqlalchemy import func, select

from .conftest import make_household, make_ledger


def count(session, model, *where) -> int:
    return session.scalar(select(func.count()).select_from(model).where(*where)) or 0


def test_enroll_numbers_households_without_personal_data_and_is_bounded(pilot_factory) -> None:
    with pilot_factory() as session:
        created = [households.enroll(session) for _ in range(MAX_PILOT_HOUSEHOLDS)]
        assert [user.display_name for user in created] == [
            f"Pilot household {number}" for number in range(1, MAX_PILOT_HOUSEHOLDS + 1)
        ]
        assert all(user.pilot for user in created)
        with pytest.raises(households.PilotError, match="pilot_limit"):
            households.enroll(session)
        enrolled = session.scalars(
            select(AuditEvent.event_type).where(AuditEvent.event_type == "pilot.enrolled")
        ).all()
        assert len(enrolled) == MAX_PILOT_HOUSEHOLDS


def test_owner_dogfood_flag_switches_only_the_owner(pilot_factory) -> None:
    with pilot_factory() as session:
        households.set_owner_pilot(session, enabled=True)
        assert session.get(User, LOCAL_USER_ID).pilot is True
        households.set_owner_pilot(session, enabled=False)
        assert session.get(User, LOCAL_USER_ID).pilot is False


def test_erase_refuses_the_owner_and_unknown_households(pilot_factory) -> None:
    with pilot_factory() as session:
        with pytest.raises(households.PilotError, match="owner_refused"):
            households.erase(session, LOCAL_USER_ID)
        with pytest.raises(households.PilotError, match="not_found"):
            households.erase(session, uuid4())


def test_erase_removes_one_household_and_keeps_the_owner_and_audit(pilot_factory) -> None:
    with pilot_factory() as session:
        pilot = make_household(session)
        other = make_household(session, name="Pilot household 2")
        make_ledger(session, pilot)
        make_ledger(session, other)
        make_ledger(session, LOCAL_USER_ID)
        session.commit()

        counts = households.erase(session, pilot)

        assert counts["transactions"] == 1 and counts["whatsapp_bindings"] == 1
        assert counts["commitments"] == counts["review_decisions"] == 1
        user = session.get(User, pilot)
        assert user is not None and user.pilot is False, "an erased household's number is ignored"
        for model in (Transaction, Commitment, ReviewDecision, SourceEvent, EmailSource, ImportRun):
            assert count(session, model, model.user_id == pilot) == 0
            assert count(session, model, model.user_id == other) == 1
            assert count(session, model, model.user_id == LOCAL_USER_ID) == 1
        assert count(session, WhatsAppBinding, WhatsAppBinding.user_id == pilot) == 0
        assert count(session, WhatsAppPrompt, WhatsAppPrompt.user_id == pilot) == 0
        # Receipts and deliveries cascade from the erased binding only.
        assert count(session, WhatsAppReceipt) == 2 and count(session, WhatsAppDelivery) == 2
        assert count(session, TransactionRevision) == 2
        assert count(session, ExtractionCache) == 0, "derived content in the shared cache is gone"
        assert count(session, AuditEvent, AuditEvent.event_type == "pilot.erased") == 1


def test_import_locks_are_per_household_and_keep_the_owner_key() -> None:
    first, second = uuid4(), uuid4()
    assert lock_key(LOCAL_USER_ID) == IMPORT_LOCK
    assert lock_key(first) == lock_key(first)
    assert len({lock_key(first), lock_key(second), IMPORT_LOCK}) == 3
    # The pipeline's per-household transaction lock uses a different digest: no self-deadlock.
    import hashlib

    pipeline = int.from_bytes(hashlib.sha256(first.bytes).digest()[:8], "big", signed=True)
    assert lock_key(first) != pipeline
