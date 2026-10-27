from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from finboy.core.errors import ProviderUnavailable
from finboy.db.models.accounts import LoginRequest, SignupWaitlist
from finboy.db.models.core import User
from finboy.db.models.mail import AuditEvent
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.db.session import build_engine
from finboy.services.accounts import households
from finboy.services.whatsapp import pilot, processor
from finboy.services.whatsapp.config import channel_config
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from .support import OWNER, Meta, settings_for


@pytest.fixture
def world(monkeypatch) -> Iterator[tuple]:
    settings = settings_for()
    engine = build_engine(settings)
    pg = sessionmaker(engine, expire_on_commit=False)
    config = channel_config(settings)
    Meta.log = []
    monkeypatch.setattr(processor, "MetaClient", Meta)
    monkeypatch.setenv("FINBOY_EXTRACTION_MODE", "rules")

    def silent(**_kwargs):
        raise ProviderUnavailable("synthetic")

    monkeypatch.setattr(pilot.speech, "synthesize_speech", silent)
    started = datetime.now(UTC)
    try:
        yield settings, pg, config
    finally:
        with pg() as session:
            created = session.scalars(
                select(User.id).where(User.joined_via.is_not(None), User.created_at >= started)
            ).all()
            for user_id in created:
                households.remove_household_data(session, user_id)
                households.remove_sign_in(session, user_id)
                session.execute(delete(AuditEvent).where(AuditEvent.user_id == user_id))
                session.execute(delete(User).where(User.id == user_id))
            # The owner's synthetic binding cascades to its receipts, prompts and deliveries.
            session.execute(
                delete(WhatsAppBinding).where(
                    WhatsAppBinding.sender_hash == config.digest("sender", OWNER)
                )
            )
            session.execute(delete(SignupWaitlist).where(SignupWaitlist.joined_at >= started))
            session.execute(delete(LoginRequest).where(LoginRequest.created_at >= started))
            session.commit()
        engine.dispose()
