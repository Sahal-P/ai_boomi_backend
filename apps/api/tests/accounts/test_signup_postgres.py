"""Sign-up journeys through real PostgreSQL, the real API and the real WhatsApp processor.

Meta and speech are recording fakes; no message reaches a phone. Synthetic numbers only.
"""

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.core.errors import ProviderUnavailable
from finboy.db.models.accounts import LoginRequest, SignupWaitlist
from finboy.db.models.core import User
from finboy.db.models.mail import AuditEvent
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.db.session import build_engine
from finboy.main import create_app
from finboy.services.accounts import households
from finboy.services.whatsapp import english, hindi, pilot, processor
from finboy.services.whatsapp.config import ChannelConfig, channel_config
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.receipts import admit
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration
OWNER = "919000000001"
FIRST, SECOND, THIRD = "919000000071", "919000000072", "919000000073"  # synthetic only


class Meta:
    """Records what would reach WhatsApp; never sends."""

    log: list[dict] = []

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def send(self, recipient: str, *, text=None, media_id=None) -> str:
        self.log.append({"to": recipient, "text": text, "media_id": media_id})
        return "wamid.out." + uuid4().hex

    def send_buttons(self, recipient: str, *, text: str, buttons) -> str:
        self.log.append({"to": recipient, "text": text, "buttons": list(buttons)})
        return "wamid.out." + uuid4().hex

    def close(self) -> None:
        pass


def settings_for(**changes) -> Settings:
    base = Settings()
    url = make_url(base.database_url.get_secret_value())
    if (
        base.environment == "production"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database not in {"finboy_signup", "finboy_test"}
    ):
        pytest.fail("Sign-up integration tests require the disposable local finboy_signup database")
    return Settings(
        _env_file=None,
        **{
            **base.model_dump(),
            "environment": "development",
            "openai_api_key": None,
            "whatsapp_enabled": True,
            "whatsapp_app_id": "953180210789448",
            "whatsapp_graph_api_version": "v26.0",
            "whatsapp_app_secret": "synthetic-app-secret",
            "whatsapp_verify_token": "synthetic-verify",
            "whatsapp_access_token": "synthetic-access",
            "whatsapp_phone_number_id": "12345678",
            "whatsapp_business_account_id": "87654321",
            "token_encryption_key": "eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg=",
            "whatsapp_sender_allowlist_json": json.dumps({OWNER: str(LOCAL_USER_ID)}),
            "whatsapp_public_number": "919000000099",
            "signup_enabled": True,
            "signup_limit": 100,
            **changes,
        },
    )


class Phone:
    def __init__(self, pg, settings: Settings, config: ChannelConfig, number: str) -> None:
        self.pg, self.settings, self.config, self.number = pg, settings, config, number

    def send(self, question: InboundQuestion) -> list[dict]:
        before = len(Meta.log)
        with self.pg() as session:
            admitted = admit(session, self.config, [question], [], settings=self.settings)
        for item in admitted:
            processor.process_question(
                self.pg, self.settings, self.config, item.receipt_id, item.question
            )
        return Meta.log[before:]

    def say(self, text: str) -> list[dict]:
        return self.send(
            InboundQuestion("wamid." + uuid4().hex, self.number, datetime.now(UTC), "text", text)
        )

    def tap(self, replies: list[dict], choice: str) -> list[dict]:
        button = next(
            key
            for reply in reversed(replies)
            for key, _ in reply.get("buttons", [])
            if key.endswith(":" + choice)
        )
        return self.send(
            InboundQuestion(
                "wamid." + uuid4().hex, self.number, datetime.now(UTC), "button", button_id=button
            )
        )

    def household(self) -> UUID | None:
        with self.pg() as session:
            return session.scalar(
                select(WhatsAppBinding.user_id).where(
                    WhatsAppBinding.sender_hash == self.config.digest("sender", self.number)
                )
            )


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


def sign_in_with_whatsapp(client: TestClient, phone: Phone, *, choice: str = "yes") -> list[dict]:
    started = client.post("/api/v1/auth/whatsapp/start", json={})
    assert started.status_code == 200
    body = started.json()
    assert body["link"].startswith("https://wa.me/919000000099?text=FinBoy%20login%20code%20")
    assert client.get("/api/v1/auth/whatsapp/status").json()["state"] == "pending"
    (card,) = phone.say(f"FinBoy login code {body['code']}")
    assert card["to"] == phone.number and len(card["buttons"]) == 2
    return [card, *phone.tap([card], choice)]


def test_whatsapp_sign_up_from_the_website_end_to_end(world) -> None:
    settings, pg, config = world
    phone = Phone(pg, settings, config, FIRST)
    with TestClient(create_app(settings)) as browser:
        card, done = sign_in_with_whatsapp(browser, phone)
        # A new number gets the English consent in the card, then the account is created.
        assert card["text"].startswith(english.CONSENT) and "Chrome" not in card["text"]
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
