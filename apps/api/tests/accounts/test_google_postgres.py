"""Google sign-up, sign-in and linking through the real API and PostgreSQL.

Google itself is replaced by a fake verifier that accepts only the nonce this browser was given;
the real token checks are covered in test_google_sign_in.py.
"""

import hashlib

import pytest
from fastapi.testclient import TestClient
from finboy.api.v1 import auth
from finboy.core.config import LOCAL_USER_ID
from finboy.core.errors import AccessError
from finboy.db.models.accounts import UserIdentity
from finboy.main import create_app
from finboy.services.accounts.google import GoogleAccount
from finboy.services.whatsapp import english
from sqlalchemy import delete, select

from .support import FIRST, Phone, settings_for

pytestmark = pytest.mark.integration
CLIENT = "123456-abcdefgh.apps.googleusercontent.com"


@pytest.fixture
def google(monkeypatch):
    """Tokens are "token-<subject>"; only the nonce handed to this browser is accepted."""

    def verify(token: str, *, client_id: str, nonce: str, certs) -> GoogleAccount:
        subject = token.removeprefix("token-")
        if client_id != CLIENT or not nonce or not token.startswith("token-"):
            raise AccessError("invalid_sign_in")
        verify.nonces.append(nonce)
        return GoogleAccount(
            hashlib.sha256(("google:" + subject).encode()).hexdigest(), "s***@***.test"
        )

    verify.nonces = []
    monkeypatch.setattr(auth, "verify_id_token", verify)
    return verify


def sign_in(client: TestClient, subject: str, **body):
    nonce = client.post("/api/v1/auth/google/start").json()["nonce"]
    response = client.post(
        "/api/v1/auth/google", json={"credential": f"token-{subject}-padding-xx", **body}
    )
    return nonce, response


def test_google_sign_up_then_sign_in_reaches_the_same_household(world, google) -> None:
    settings, pg, _ = world
    settings = settings_for(google_signin_client_id=CLIENT)
    app = create_app(settings)
    with TestClient(app) as first:
        nonce, response = sign_in(first, "alpha")
        assert response.status_code == 200 and google.nonces == [nonce]
        household = first.get("/api/v1/auth/session").json()["household"]
        assert household["joined_via"] == "google" and household["google"] == "s***@***.test"
    with TestClient(app) as second:
        _, again = sign_in(second, "alpha")
        assert again.status_code == 200
        assert second.get("/api/v1/auth/session").json()["household"] == household
    with pg() as session:
        rows = session.scalars(select(UserIdentity)).all()
        assert len([row for row in rows if row.email_masked == "s***@***.test"]) == 1


def test_google_needs_this_browsers_nonce_and_open_sign_up(world, google) -> None:
    settings = settings_for(google_signin_client_id=CLIENT)
    with TestClient(create_app(settings)) as browser:
        # No /google/start in this browser, so there is no nonce cookie to bind to.
        refused = browser.post(
            "/api/v1/auth/google", json={"credential": "token-beta-padding-xxxxxx"}
        )
        assert refused.status_code == 401 and refused.json()["error"]["code"] == "invalid_sign_in"
    closed = settings_for(google_signin_client_id=CLIENT, signup_enabled=False)
    with TestClient(create_app(closed)) as browser:
        _, response = sign_in(browser, "gamma")
        assert response.json()["error"]["code"] == "signup_unavailable"
    full = settings_for(google_signin_client_id=CLIENT, signup_limit=0)
    with TestClient(create_app(full)) as browser:
        _, response = sign_in(browser, "delta")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "signups_closed"
        assert browser.get("/api/v1/auth/session").json()["sign_in"]["signup_open"] is False


def test_a_google_household_links_its_whatsapp(world, google) -> None:
    _, pg, config = world
    settings = settings_for(google_signin_client_id=CLIENT)
    phone = Phone(pg, settings, config, FIRST)
    with TestClient(create_app(settings)) as browser:
        assert sign_in(browser, "epsilon")[1].status_code == 200
        started = browser.post("/api/v1/auth/whatsapp/start", json={"purpose": "link"}).json()
        (card,) = phone.say(f"FinBoy login code {started['code']}")
        assert card["text"] == english.link_card("a browser")
        (linked,) = phone.tap([card], "yes")
        assert linked["text"] == english.LINKED
        assert browser.post("/api/v1/auth/whatsapp/complete").json() == {"linked": True}
        household = browser.get("/api/v1/auth/session").json()["household"]
        assert household["joined_via"] == "google" and household["whatsapp"] == "•••• 0071"
        # The linked number now records into the Google household, saved at once.
        (saved,) = phone.say("Paid the milkman 500")
        assert saved["text"].startswith("✅ Saved: ₹500 paid")
        assert browser.get("/api/v1/money/summary").json()["confirmed_outflows_minor"] == 50000


def test_the_owner_links_google_and_later_signs_in_with_it(world, google) -> None:
    settings = settings_for(google_signin_client_id=CLIENT)
    _, pg, _ = world
    app = create_app(settings)
    try:
        with TestClient(app) as owner:  # development: no session acts as the owner
            _, linked = sign_in(owner, "zeta", link=True)
            assert linked.json() == {"linked": True}
        with TestClient(app) as browser:
            assert sign_in(browser, "zeta")[1].status_code == 200
            assert browser.get("/api/v1/auth/session").json()["household"]["owner"] is True
    finally:
        with pg() as session:
            session.execute(delete(UserIdentity).where(UserIdentity.user_id == LOCAL_USER_ID))
            session.commit()
