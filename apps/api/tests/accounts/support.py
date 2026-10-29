"""Shared fakes and helpers for the sign-up integration tests. Synthetic numbers only."""

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.services.whatsapp import processor
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.meta import MetaUnavailable
from finboy.services.whatsapp.receipts import admit
from sqlalchemy import select
from sqlalchemy.engine import make_url

OWNER = "919000000001"
FIRST, SECOND, THIRD = "919000000071", "919000000072", "919000000073"  # synthetic only


class Meta:
    """Records what would reach WhatsApp; never sends. Like the real client, it refuses a number
    outside the private allowlist unless the caller vouched for it (a self-serve household)."""

    log: list[dict] = []

    def __init__(self, config: ChannelConfig, *_args, **_kwargs) -> None:
        self.allowlist, self.vouched = config.allowlist, set()

    def allow(self, recipient: str) -> None:
        self.vouched.add(recipient)

    def _check(self, recipient: str) -> None:
        if recipient not in self.allowlist and recipient not in self.vouched:
            raise MetaUnavailable

    def send(self, recipient: str, *, text=None, media_id=None) -> str:
        self._check(recipient)
        self.log.append({"to": recipient, "text": text, "media_id": media_id})
        return "wamid.out." + uuid4().hex

    def send_buttons(self, recipient: str, *, text: str, buttons) -> str:
        self._check(recipient)
        self.log.append({"to": recipient, "text": text, "buttons": list(buttons)})
        return "wamid.out." + uuid4().hex

    def send_list(self, recipient: str, *, text: str, button: str, section: str, rows) -> str:
        self._check(recipient)
        self.log.append({"to": recipient, "text": text, "rows": list(rows)})
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


def sign_in_with_whatsapp(client: TestClient, phone: Phone, *, choice: str = "yes") -> list[dict]:
    started = client.post("/api/v1/auth/whatsapp/start", json={})
    assert started.status_code == 200
    body = started.json()
    assert body["link"].startswith("https://wa.me/919000000099?text=FinBoy%20login%20code%20")
    assert client.get("/api/v1/auth/whatsapp/status").json()["state"] == "pending"
    (card,) = phone.say(f"FinBoy login code {body['code']}")
    assert card["to"] == phone.number and len(card["buttons"]) == 2
    return [card, *phone.tap([card], choice)]
