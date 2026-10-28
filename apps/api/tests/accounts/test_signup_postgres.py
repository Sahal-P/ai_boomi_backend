"""Sign-up journeys through real PostgreSQL, the real API and the real WhatsApp processor.

Meta and speech are recording fakes; no message reaches a phone. Synthetic numbers only.
"""

import pytest
from fastapi.testclient import TestClient
from finboy.db.models.accounts import SignupWaitlist
from finboy.db.models.core import User
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.main import create_app
from finboy.services.whatsapp import english, hindi
from sqlalchemy import select

from .support import FIRST, OWNER, SECOND, THIRD, Phone, sign_in_with_whatsapp

pytestmark = pytest.mark.integration


def test_whatsapp_sign_up_from_the_website_end_to_end(world) -> None:
    settings, pg, config = world
    phone = Phone(pg, settings, config, FIRST)
    with TestClient(create_app(settings)) as browser:
        card, done = sign_in_with_whatsapp(browser, phone)
        # A new number gets the English consent in the card, then the account is created.
        assert card["text"].startswith(english.SELF_CONSENT) and "Chrome" not in card["text"]
        assert done["text"] == english.SIGNED_IN
        assert browser.get("/api/v1/auth/whatsapp/status").json()["state"] == "confirmed"
        assert browser.post("/api/v1/auth/whatsapp/complete").status_code == 200
        view = browser.get("/api/v1/auth/session").json()
        assert view["authenticated"] is True
        assert view["household"] == {
            "owner": False,
            "joined_via": "whatsapp",
            "whatsapp": "•••• 0071",
            "google": None,
        }
        # The confirmed request is used once.
        replay = browser.post("/api/v1/auth/whatsapp/complete")
        assert replay.status_code == 410 and replay.json()["error"]["code"] == "login_expired"

        # The new household records money in English on WhatsApp, and sees it on the web.
        (record,) = phone.say("Paid the milkman 500")
        assert record["text"].startswith("💸 ₹500 paid")
        (added,) = phone.tap([record], "yes")
        assert added["text"].startswith("✅ Added: ₹500 paid")
        summary = browser.get("/api/v1/money/summary").json()
        assert summary["confirmed_outflows_minor"] == 50000
        own = browser.get("/api/v1/transactions").json()
        assert [row["amount_minor"] for row in own] == [50000]
        record_id = own[0]["id"]

    with pg() as session:
        user = session.get(User, phone.household())
        assert user is not None and user.joined_via == "whatsapp"
        assert user.consented_at is not None and user.display_name == "Household"
        binding = session.scalars(
            select(WhatsAppBinding).where(WhatsAppBinding.user_id == user.id)
        ).one()
        assert binding.consented_at is not None and binding.language == "en"
        assert (
            binding.encrypted_sender is not None and FIRST.encode() not in binding.encrypted_sender
        )

    # Another household, signed in on another browser, cannot see or touch that record.
    other = Phone(pg, settings, config, SECOND)
    with TestClient(create_app(settings)) as stranger:
        sign_in_with_whatsapp(stranger, other)
        assert stranger.post("/api/v1/auth/whatsapp/complete").status_code == 200
        assert stranger.get(f"/api/v1/transactions/{record_id}").status_code == 404
        assert stranger.post(f"/api/v1/transactions/{record_id}/confirm").status_code == 404
        assert stranger.get("/api/v1/money/summary").json()["confirmed_outflows_minor"] == 0
        assert stranger.get("/api/v1/transactions").json() == []
    # And the owner's household (no session in development) does not see it either.
    with TestClient(create_app(settings)) as owner:
        assert owner.get(f"/api/v1/transactions/{record_id}").status_code == 404


def test_only_the_browser_that_started_can_finish(world) -> None:
    settings, pg, config = world
    phone = Phone(pg, settings, config, FIRST)
    app = create_app(settings)
    with TestClient(app) as browser, TestClient(app) as attacker:
        sign_in_with_whatsapp(browser, phone)
        refused = attacker.post("/api/v1/auth/whatsapp/complete")
        assert refused.status_code == 410
        assert attacker.get("/api/v1/auth/whatsapp/status").json()["state"] == "expired"
        assert browser.post("/api/v1/auth/whatsapp/complete").status_code == 200


def test_no_on_the_card_keeps_nothing(world) -> None:
    settings, pg, config = world
    phone = Phone(pg, settings, config, FIRST)
    with TestClient(create_app(settings)) as browser:
        _, declined = sign_in_with_whatsapp(browser, phone, choice="no")
        assert declined["text"] == english.LOGIN_DECLINED
        assert browser.get("/api/v1/auth/whatsapp/status").json()["state"] == "declined"
        assert browser.post("/api/v1/auth/whatsapp/complete").status_code == 410
    assert phone.household() is None, "a household that never agreed keeps nothing"


def test_sign_up_inside_whatsapp_in_hindi(world) -> None:
    settings, pg, config = world
    phone = Phone(pg, settings, config, FIRST)
    (consent,) = phone.say("नमस्ते FinBoy")
    assert consent["text"] == hindi.SELF_CONSENT
    assert phone.tap([consent], "agree")[0]["text"] == hindi.WELCOME
    with pg() as session:
        user = session.get(User, phone.household())
        assert user is not None and user.consented_at is not None
    # A second "नमस्ते" is now part of the diary, not another consent card.
    assert phone.say("नमस्ते")[0]["text"] == hindi.UNCLEAR


def test_full_then_join_keeps_only_a_place_in_line(world) -> None:
    settings, pg, config = world
    full = settings.model_copy(update={"signup_limit": 0})
    phone = Phone(pg, full, config, THIRD)
    (reply,) = phone.say("Hi FinBoy")
    assert reply["text"] == english.FULL and "buttons" not in reply
    (joined,) = phone.say("JOIN")
    assert joined["text"] == english.JOINED
    assert phone.household() is None
    with pg() as session:
        row = session.scalars(
            select(SignupWaitlist).where(
                SignupWaitlist.sender_hash == config.digest("sender", THIRD)
            )
        ).one()
        assert THIRD.encode() not in row.encrypted_sender and row.language == "en"


def test_sign_up_stays_off_by_default(world) -> None:
    settings, pg, config = world
    phone = Phone(pg, settings.model_copy(update={"signup_enabled": False}), config, THIRD)
    assert phone.say("Hi FinBoy") == []
    assert phone.household() is None


def test_the_owner_signs_in_with_the_allowlisted_number(world) -> None:
    settings, pg, config = world
    owner = Phone(pg, settings, config, OWNER)
    with TestClient(create_app(settings)) as browser:
        card, done = sign_in_with_whatsapp(browser, owner)
        assert card["text"] == english.sign_in_card("a browser")
        assert done["text"] == english.SIGNED_IN
        assert browser.post("/api/v1/auth/whatsapp/complete").status_code == 200
        assert browser.get("/api/v1/auth/session").json()["household"]["owner"] is True
