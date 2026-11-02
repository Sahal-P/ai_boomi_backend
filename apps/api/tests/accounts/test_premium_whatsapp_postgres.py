"""FinBoy Premium on WhatsApp through real PostgreSQL and the real processor.

docs/subscription-round/contract.md. Meta is a recording fake; no message reaches a phone, and no
audio or photo is downloaded on the Free plan. Synthetic numbers only.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from finboy.db.models.billing import BillingProfile, Subscription
from finboy.db.models.core import User
from finboy.db.models.whatsapp import WhatsAppReceipt
from finboy.services.billing import links
from finboy.services.whatsapp import english, hindi
from finboy.services.whatsapp.events import InboundQuestion
from sqlalchemy import delete, select

from .support import FIRST, SECOND, Phone

pytestmark = pytest.mark.integration


def billing(settings):
    return settings.model_copy(
        update={
            "billing_enabled": True,
            "billing_launch_date": None,
            "web_app_url": "http://127.0.0.1:3071",
            "cors_origins": [*settings.cors_origins, "http://127.0.0.1:3071"],
            "payu_merchant_key": "tEsTkY",
            "payu_merchant_salt": "s4ltForTestsOnly0123456789abcdef",
            "api_public_url": "http://127.0.0.1:8071",
        }
    )


def joined(pg, settings, config, number: str, *, days_ago: int) -> Phone:
    """A household that signed up on WhatsApp `days_ago` days ago."""
    phone = Phone(pg, settings, config, number)
    (consent,) = phone.say("Hi FinBoy")
    phone.tap([consent], "agree")
    with pg() as session:
        user = session.get(User, phone.household())
        user.consented_at = datetime.now(UTC) - timedelta(days=days_ago)
        session.commit()
    return phone


def media(phone: Phone, kind: str) -> list[dict]:
    return phone.send(
        InboundQuestion(
            "wamid." + uuid4().hex,
            phone.number,
            datetime.now(UTC),
            kind,
            media_id="1234567890",
            mime_type="audio/ogg" if kind == "audio" else "image/jpeg",
        )
    )


@pytest.fixture
def cleanup(world):
    yield world
    _settings, pg, _config = world
    with pg() as session:
        for number in (FIRST, SECOND):
            user_id = Phone(pg, _settings, _config, number).household()
            if user_id is not None:
                session.execute(delete(BillingProfile).where(BillingProfile.user_id == user_id))
                session.execute(delete(Subscription).where(Subscription.user_id == user_id))
        session.commit()


def test_the_free_plan_explains_premium_instead_of_a_dead_end(cleanup) -> None:
    settings, pg, config = cleanup
    settings = billing(settings)
    phone = joined(pg, settings, config, FIRST, days_ago=40)
    (voice,) = media(phone, "audio")
    assert voice["text"].startswith(english.PREMIUM_VOICE.split("{link}")[0])
    token = voice["text"].rsplit("/pay#", 1)[1]
    with pg() as session:
        assert links.read(session, settings, token).user_id == phone.household()
        errors = session.scalars(
            select(WhatsAppReceipt.error_code).order_by(WhatsAppReceipt.received_at.desc())
        ).first()
        assert errors == "premium_required"
    (photo,) = media(phone, "image")
    assert photo["text"].startswith(english.PREMIUM_PHOTO.split("{link}")[0])
    (question,) = phone.say("How much did I spend on food?")
    assert question["text"].startswith(english.PREMIUM_ASK.split("{link}")[0])
    # Typed entries and check-ups stay free.
    saved = phone.say("milk 200")
    assert saved and "Premium" not in saved[0]["text"]
    today = phone.say("today")
    assert today and "Premium" not in today[0]["text"]


def test_the_trial_nudge_comes_once_in_the_persons_language(cleanup) -> None:
    settings, pg, config = cleanup
    settings = billing(settings)
    phone = joined(pg, settings, config, SECOND, days_ago=28)
    phone.say("hindi")
    first = phone.say("दूध 200")
    nudges = [reply for reply in first if reply["text"].startswith("⭐")]
    assert len(nudges) == 1
    assert nudges[0]["text"].startswith(hindi.TRIAL_ENDING.split("{days}")[0])
    # Premium features still work in the trial, and the nudge is not repeated.
    second = phone.say("चाय 20")
    assert not [reply for reply in second if reply["text"].startswith("⭐")]
    with pg() as session:
        profile = session.get(BillingProfile, phone.household())
        assert profile is not None and profile.last_nudge == "trial_3d"


def test_nothing_changes_while_billing_is_off(cleanup) -> None:
    settings, pg, config = cleanup
    settings = settings.model_copy(update={"billing_enabled": False})
    phone = joined(pg, settings, config, FIRST, days_ago=400)
    replies = phone.say("How much did I spend on food?")
    assert replies and all("Premium" not in reply["text"] for reply in replies)
