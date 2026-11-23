"""From a page visit to a household's first record, through real PostgreSQL, the real API and the
real WhatsApp processor (docs/ad-journey-round/contract.md).

Meta and speech are recording fakes; no message reaches a phone. Synthetic numbers and refs only.
"""

import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from finboy.db.models.core import User
from finboy.db.models.visits import SignupVisit
from finboy.main import create_app
from finboy.services.accounts import households, login, visits
from finboy.services.whatsapp import english, malayalam
from finboy.services.whatsapp.events import InboundQuestion
from sqlalchemy import delete, select, update

from .support import FIRST, SECOND, Phone

pytestmark = pytest.mark.integration

INSTAGRAM_ANDROID = (
    "Mozilla/5.0 (Linux; Android 14; SM-A146B; wv) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Version/4.0 Chrome/131.0 Mobile Safari/537.36 Instagram 360.0.0.30.109 Android"
)


def new_ref() -> str:
    return "".join(secrets.choice(login.ALPHABET) for _ in range(6))


def greet(phone: Phone, text: str) -> list[dict]:
    """What the webhook hands on: the greeting without its ref, and the ref."""
    body, ref = visits.split_ref(text)
    return phone.send(
        InboundQuestion(
            "wamid." + uuid4().hex, phone.number, datetime.now(UTC), "text", body, ref=ref
        )
    )


def test_a_malayalam_ad_visit_becomes_a_household_with_its_first_record(world) -> None:
    settings, pg, config = world
    ref, later = new_ref(), new_ref()
    try:
        with TestClient(create_app(settings)) as browser:
            opened = browser.post(
                "/api/v1/visits",
                json={
                    "ref": ref,
                    "landing": "/ml",
                    "language": "ml",
                    "source": "instagram",
                    "medium": "paid_social",
                    "campaign": "journey-test",
                },
                headers={"user-agent": INSTAGRAM_ANDROID},
            )
            assert opened.status_code == 204
            # A reload in the same tab sends the same ref; it stays one visit.
            assert (
                browser.post("/api/v1/visits", json={"ref": ref, "landing": "/ml"}).status_code
                == 204
            )
            assert browser.post("/api/v1/visits/tap", json={"ref": ref}).status_code == 204

        phone = Phone(pg, settings, config, FIRST)
        (welcome,) = greet(phone, f"നമസ്കാരം FinBoy (ref {ref})")
        assert welcome["text"] == malayalam.WELCOME
        # Offline the reader needs a verb; the live model also reads a bare "ചായ 20"
        # (fixtures/diary/cases.json, `pnpm eval:diary`).
        (saved,) = phone.say("ചായയ്ക്ക് 20 കൊടുത്തു")
        assert saved["text"].startswith("✅ ചേർത്തു: ₹20")
        assert saved["text"].endswith(malayalam.FIRST_SAVED)
        (second,) = phone.say("ഓട്ടോയ്ക്ക് 50 കൊടുത്തു")
        assert malayalam.FIRST_SAVED not in second["text"]

        user_id = phone.household()
        with pg() as session:
            visit = session.scalar(select(SignupVisit).where(SignupVisit.ref == ref))
            assert visit is not None and visit.user_id == user_id
            assert visit.joined_at is not None and visit.tapped_at is not None
            assert (visit.source, visit.medium, visit.campaign) == (
                "instagram",
                "paid_social",
                "journey-test",
            )
            assert (visit.landing, visit.language, visit.browser, visit.platform) == (
                "/ml",
                "ml",
                "instagram",
                "android",
            )
            (row,) = [
                item
                for item in visits.funnel(session, visit.created_at - timedelta(seconds=1))
                if item.campaign == "journey-test"
            ]
            assert (row.opened, row.tapped, row.signed_up, row.agreed, row.first_record) == (
                1,
                1,
                1,
                1,
                1,
            )
            user = session.get(User, user_id)
            assert user is not None
            journey = visits.journey(session, user)
            assert journey.campaign == "journey-test" and journey.opened == visit.created_at
            assert journey.agreed is not None and journey.whatsapp_linked is not None
            assert journey.first_record is not None and journey.first_record >= journey.agreed

        # A greeting from a number that is already a household claims no visit.
        with TestClient(create_app(settings)) as browser:
            assert (
                browser.post("/api/v1/visits", json={"ref": later, "landing": "/ml"}).status_code
                == 204
            )
        greet(phone, f"നമസ്കാരം FinBoy (ref {later})")
        with pg() as session:
            again = session.scalar(select(SignupVisit).where(SignupVisit.ref == later))
            assert again is not None and again.user_id is None and again.joined_at is None

        # Deleting the account keeps the visit only as an anonymous count.
        with pg() as session:
            households.erase_household(session, user_id, settings)
            session.commit()
            visit = session.scalar(select(SignupVisit).where(SignupVisit.ref == ref))
            assert visit is not None and visit.user_id is None and visit.joined_at is not None
    finally:
        with pg() as session:
            session.execute(delete(SignupVisit).where(SignupVisit.ref.in_([ref, later])))
            session.commit()


def test_a_sign_in_code_from_a_page_carries_its_visit(world) -> None:
    settings, pg, config = world
    ref = new_ref()
    try:
        with TestClient(create_app(settings)) as browser:
            assert (
                browser.post("/api/v1/visits", json={"ref": ref, "landing": "/"}).status_code == 204
            )
            started = browser.post("/api/v1/auth/whatsapp/start", json={"ref": ref})
            assert started.status_code == 200
            body = started.json()
            assert body["link"].endswith(f"%20%28ref%20{ref}%29")
            phone = Phone(pg, settings, config, SECOND)
            (card,) = greet(phone, f"FinBoy login code {body['code']} (ref {ref})")
            assert len(card["buttons"]) == 2  # the sign-up card, as without a ref
            (done,) = phone.tap([card], "yes")
            assert done["text"] == english.SIGNED_IN
        with pg() as session:
            visit = session.scalar(select(SignupVisit).where(SignupVisit.ref == ref))
            assert visit is not None and visit.tapped_at is not None
            assert visit.user_id == phone.household() and visit.source is None
            assert visit.landing == "/" and visit.browser == "other"
    finally:
        with pg() as session:
            session.execute(delete(SignupVisit).where(SignupVisit.ref == ref))
            session.commit()


def test_visits_that_led_nowhere_are_forgotten_after_90_days(world) -> None:
    _settings, pg, _config = world
    old, fresh = new_ref(), new_ref()
    with pg() as session:
        try:
            for ref in (old, fresh):
                assert visits.record(
                    session, ref=ref, tags=visits.Tags(), landing="/", language=None, user_agent=""
                )
            session.execute(
                update(SignupVisit)
                .where(SignupVisit.ref == old)
                .values(created_at=datetime.now(UTC) - timedelta(days=91))
            )
            session.commit()
            assert visits.tidy(session) >= 1
            session.commit()
            kept = set(
                session.scalars(select(SignupVisit.ref).where(SignupVisit.ref.in_([old, fresh])))
            )
            assert kept == {fresh}
        finally:
            session.execute(delete(SignupVisit).where(SignupVisit.ref.in_([old, fresh])))
            session.commit()
