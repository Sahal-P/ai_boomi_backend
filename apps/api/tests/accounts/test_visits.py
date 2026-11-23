"""Where sign-ups come from (docs/ad-journey-round/contract.md), without PostgreSQL.

Synthetic refs, tags and User-Agents only.
"""

import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import httpx
import pytest
from cryptography.fernet import Fernet
from finboy.api.v1 import visits as visit_routes
from finboy.core.access import password_hash
from finboy.core.config import Settings
from finboy.db.session import get_session
from finboy.main import create_app
from finboy.services.accounts import login, visits
from finboy.services.accounts.visits import Step, Tags
from sqlalchemy.orm import Session

INSTAGRAM_ANDROID = (
    "Mozilla/5.0 (Linux; Android 14; SM-A146B; wv) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Version/4.0 Chrome/131.0 Mobile Safari/537.36 Instagram 360.0.0.30.109 Android"
)
INSTAGRAM_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/22B83 Instagram 360.0.0.30.109 (iPhone14,7; iOS 18_1)"
)
FACEBOOK_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/22B83 [FBAN/FBIOS;FBAV/480.0.0.40.104]"
)
DESKTOP = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0"
ORIGIN = {"origin": "https://finboy.io"}


def test_tags_are_cleaned_and_never_refused() -> None:
    tags = visits.clean_tags(" Instagram ", "paid_social", "2026-11-ML-Reel", "reel 4035")
    # A space is not allowed in a kept tag, so that one is dropped rather than refused.
    assert tags == Tags("instagram", "paid_social", "2026-11-ml-reel", None)
    assert visits.clean_tag("x" * 65) is None and visits.clean_tag("<b>") is None
    # A Meta click without tags: the page saw an fbclid and sent only that it did.
    assert visits.clean_tags(None, None, None, None, meta_click=True) == Tags("meta", "click")
    assert visits.clean_tags("instagram", None, None, None, meta_click=True).source == "instagram"


def test_browser_and_phone_classes_are_coarse() -> None:
    assert visits.classify(INSTAGRAM_ANDROID) == ("instagram", "android")
    assert visits.classify(INSTAGRAM_IPHONE) == ("instagram", "ios")
    assert visits.classify(FACEBOOK_IPHONE) == ("facebook", "ios")
    assert visits.classify(DESKTOP) == ("other", "desktop")
    assert visits.classify("") == ("other", "other")


@pytest.mark.parametrize(
    ("text", "clean", "ref"),
    [
        ("നമസ്കാരം FinBoy (ref K7Q2MX)", "നമസ്കാരം FinBoy", "K7Q2MX"),
        ("Hi FinBoy (ref k7q2mx)", "Hi FinBoy", "K7Q2MX"),
        ("Hi FinBoy\n(ref K7Q2MX) ", "Hi FinBoy", "K7Q2MX"),
        ("FinBoy login code ABCD-EFGH (ref K7Q2MX)", "FinBoy login code ABCD-EFGH", "K7Q2MX"),
        # Only the ref was left: the greeting's words were deleted.
        ("(ref K7Q2MX)", "hi", "K7Q2MX"),
        # A ref inside a sentence, a short one, or one with letters a ref never has stays text.
        ("chai 20 (ref K7Q2MX) and auto 50", "chai 20 (ref K7Q2MX) and auto 50", None),
        ("Hi FinBoy (ref K7Q2M)", "Hi FinBoy (ref K7Q2M)", None),
        ("Hi FinBoy (ref K7Q2MO)", "Hi FinBoy (ref K7Q2MO)", None),
        ("chai 20", "chai 20", None),
    ],
)
def test_only_a_trailing_ref_is_read(text: str, clean: str, ref: str | None) -> None:
    assert visits.split_ref(text) == (clean, ref)


def test_a_login_code_is_still_read_once_its_ref_is_gone(settings: Settings) -> None:
    text, ref = visits.split_ref("FinBoy login code ABCD-EFGH (ref K7Q2MX)")
    assert login.read_code(text) == "ABCD-EFGH" and ref == "K7Q2MX"
    public = settings.model_copy(update={"whatsapp_public_number": "919000000099"})
    assert login.message_link(public, "ABCD-EFGH", "K7Q2MX") == (
        "https://wa.me/919000000099?text=FinBoy%20login%20code%20ABCD-EFGH%20%28ref%20K7Q2MX%29"
    )
    assert login.message_link(public, "ABCD-EFGH") == (
        "https://wa.me/919000000099?text=FinBoy%20login%20code%20ABCD-EFGH"
    )


def at(minutes: float) -> datetime:
    return datetime(2026, 11, 23, 9, 0, tzinfo=UTC) + timedelta(minutes=minutes)


def test_the_funnel_counts_each_step_and_its_median_minutes() -> None:
    steps = [
        Step("instagram", "paid_social", "ml-reel", at(0), at(1), at(3), at(3), at(10)),
        Step("instagram", "paid_social", "ml-reel", at(0), at(2), at(6), at(6), None),
        # The tap's ping was lost, but sending the greeting means the button was tapped.
        Step("instagram", "paid_social", "ml-reel", at(0), None, at(5), at(5), None),
        Step("instagram", "paid_social", "ml-reel", at(0), at(4), None, None, None),
        Step("instagram", "paid_social", "ml-reel", at(0), None, None, None, None),
        Step("ig", "social", None, at(0), None, None, None, None),
        # A sign-up that came with no visit (a shared number, a QR code, an old link).
        Step(None, None, None, None, None, at(0), at(0), at(30)),
    ]
    reel, bio, direct = visits.summarize(steps)
    assert (reel.source, reel.medium, reel.campaign) == ("instagram", "paid_social", "ml-reel")
    assert not reel.direct
    counts = (reel.opened, reel.tapped, reel.signed_up, reel.agreed, reel.first_record)
    assert counts == (5, 4, 3, 3, 1)
    assert reel.minutes_to_tap == 2.0  # 1, 2 and 4 minutes
    assert reel.minutes_to_sign_up == 3.0  # 2 and 4
    assert reel.minutes_to_record == 7.0
    # Instagram tags its own bio-link clicks ig/social, so they never join the ad's row.
    assert (bio.source, bio.medium, bio.opened, bio.tapped, bio.minutes_to_tap) == (
        "ig",
        "social",
        1,
        0,
        None,
    )
    assert direct.direct and direct.source is None and direct.opened == 0
    assert (direct.signed_up, direct.agreed, direct.first_record) == (1, 1, 1)
    assert direct.minutes_to_record == 30.0


def production() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        environment="production",
        cors_origins=["https://finboy.io"],
        web_app_url="https://finboy.io",
        web_session_key=Fernet.generate_key().decode(),
        household_password_hash=password_hash("synthetic-household-password"),
    )


@pytest.fixture
async def public(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[tuple[httpx.AsyncClient, list]]:
    calls: list[tuple[str, dict]] = []

    def record(_session, **kwargs) -> bool:
        calls.append(("visit", kwargs))
        return True

    def tap(_session, ref) -> bool:
        calls.append(("tap", {"ref": ref}))
        return False  # an unknown ref is ignored, and the answer is the same

    monkeypatch.setattr(visit_routes.visits, "record", record)
    monkeypatch.setattr(visit_routes.visits, "tap", tap)
    app = create_app(production())
    session = MagicMock(spec=Session)
    app.dependency_overrides[get_session] = lambda: session
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="https://finboy-api.example"
    ) as client:
        yield client, calls
    app.state.engine.dispose()


VISIT = {
    "ref": "K7Q2MX",
    "landing": "/ml",
    "language": "ml",
    "source": "Instagram",
    "medium": "paid_social",
    "campaign": "2026-11-ml-reel",
    "content": None,
    "meta_click": True,
}


@pytest.mark.anyio
async def test_a_visit_needs_no_sign_in_but_needs_the_web_origin(public, caplog) -> None:
    client, calls = public
    caplog.set_level(logging.INFO)
    refused = await client.post("/api/v1/visits", json=VISIT)
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "origin_not_allowed"
    answered = await client.post(
        "/api/v1/visits", json=VISIT, headers={**ORIGIN, "user-agent": INSTAGRAM_ANDROID}
    )
    assert answered.status_code == 204 and answered.content == b""
    ((kind, kept),) = calls
    assert kind == "visit" and kept["ref"] == "K7Q2MX" and kept["landing"] == "/ml"
    assert kept["tags"] == Tags("instagram", "paid_social", "2026-11-ml-reel", None)
    assert kept["language"] == "ml" and kept["user_agent"] == INSTAGRAM_ANDROID
    tapped = await client.post("/api/v1/visits/tap", json={"ref": "K7Q2MX"}, headers=ORIGIN)
    assert tapped.status_code == 204
    # Logs carry the stage and outcome, never the ref or the User-Agent.
    logged = " ".join(f"{record.getMessage()} {record.__dict__}" for record in caplog.records)
    assert "K7Q2MX" not in logged and "Instagram 360" not in logged
    assert any(getattr(record, "stage", None) == "tap" for record in caplog.records)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "body",
    [
        {**VISIT, "ref": "K7Q2M"},
        {**VISIT, "ref": "K7Q2MO"},
        {**VISIT, "language": "ta"},
        {**VISIT, "fbclid": "IwAR0synthetic"},  # the click ID is never accepted
        {**VISIT, "campaign": "x" * 201},
    ],
)
async def test_bad_visits_are_refused(public, body) -> None:
    client, calls = public
    response = await client.post("/api/v1/visits", json=body, headers=ORIGIN)
    assert response.status_code == 422 and calls == []


@pytest.mark.anyio
async def test_visits_are_small_and_throttled_per_address(public) -> None:
    client, _calls = public
    large = json.dumps({**VISIT, "campaign": "x" * 3000})
    too_large = await client.post(
        "/api/v1/visits",
        content=large,
        headers={**ORIGIN, "content-type": "application/json"},
    )
    assert too_large.status_code == 413
    answers = [
        (
            await client.post("/api/v1/visits/tap", json={"ref": "K7Q2MX"}, headers=ORIGIN)
        ).status_code
        for _ in range(31)
    ]
    assert answers[:30] == [204] * 30 and answers[30] == 429
