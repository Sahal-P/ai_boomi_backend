from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from finboy.core.access import session_key
from finboy.core.config import LOCAL_USER_ID
from finboy.core.errors import AccessError
from finboy.services.billing import contact, links, plans

from .support import billing_settings

NOW = datetime(2026, 12, 20, 6, 0, tzinfo=UTC)
SIGNED_UP = datetime(2026, 12, 1, 4, 30, tzinfo=UTC)


def household(**changes: object) -> SimpleNamespace:
    values = {"pilot": False, "created_at": SIGNED_UP, "consented_at": SIGNED_UP}
    values.update(changes)
    return SimpleNamespace(**values)


def session_with(user: object = None, subscription: object = None) -> MagicMock:
    session = MagicMock()
    session.execute.return_value.one_or_none.return_value = user
    session.get.return_value = subscription
    return session


def subscription(**changes: object) -> SimpleNamespace:
    values = {
        "paid_through": None,
        "grace_until": None,
        "renewal": "manual",
        "next_charge_on": None,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_everyone_is_included_while_billing_is_off() -> None:
    settings = billing_settings(billing_enabled=False)
    plan = plans.plan_for(session_with(household()), settings, uuid4(), NOW)
    assert plan.state == "included" and plan.premium and not plan.can_pay(NOW)


def test_owner_and_pilot_households_never_pay() -> None:
    settings = billing_settings(billing_owner_included=True)
    assert plans.plan_for(session_with(household()), settings, LOCAL_USER_ID, NOW).state == (
        "included"
    )
    pilot = plans.plan_for(session_with(household(pilot=True)), settings, uuid4(), NOW)
    assert pilot.state == "included"


def test_thirty_days_from_sign_up_then_free() -> None:
    settings = billing_settings()
    plan = plans.plan_for(session_with(household()), settings, uuid4(), NOW)
    assert plan.state == "trial" and plan.trial_ends_at == SIGNED_UP + timedelta(days=30)
    assert plan.can_pay(NOW)  # 11 days left, plus a month: within the pay-ahead window
    later = NOW + timedelta(days=12)
    plan = plans.plan_for(session_with(household()), settings, uuid4(), later)
    assert plan.state == "free" and not plan.premium and plan.can_pay(later)


def test_households_from_before_launch_get_thirty_days_from_launch() -> None:
    settings = billing_settings(billing_launch_date="2026-12-15")
    plan = plans.plan_for(session_with(household()), settings, uuid4(), NOW)
    # 15 December, 00:00 IST.
    assert plan.trial_ends_at == datetime(2026, 12, 14, 18, 30, tzinfo=UTC) + timedelta(days=30)


def test_paid_grace_and_autopay_states() -> None:
    settings = billing_settings()
    after_trial = SIGNED_UP + timedelta(days=40)
    paid = subscription(paid_through=after_trial + timedelta(days=20))
    plan = plans.plan_for(session_with(household(), paid), settings, uuid4(), after_trial)
    assert plan.state == "active" and plan.can_pay(after_trial)
    ahead = subscription(paid_through=after_trial + timedelta(days=40))
    plan = plans.plan_for(session_with(household(), ahead), settings, uuid4(), after_trial)
    assert not plan.can_pay(after_trial)  # already paid more than 35 days ahead
    autopay = subscription(
        paid_through=after_trial + timedelta(days=5), renewal="autopay", next_charge_on=date.today()
    )
    plan = plans.plan_for(session_with(household(), autopay), settings, uuid4(), after_trial)
    assert plan.state == "active" and not plan.can_pay(after_trial)
    grace = subscription(
        paid_through=after_trial - timedelta(days=1),
        grace_until=after_trial + timedelta(days=2),
        renewal="autopay",
    )
    plan = plans.plan_for(session_with(household(), grace), settings, uuid4(), after_trial)
    assert plan.state == "grace" and plan.premium and plan.can_pay(after_trial)


def test_a_payment_never_starts_inside_time_already_covered() -> None:
    trial = plans.Plan("trial", trial_ends_at=NOW + timedelta(days=9))
    assert trial.starts_next(NOW) == NOW + timedelta(days=9)
    both = plans.Plan(
        "trial", trial_ends_at=NOW + timedelta(days=9), paid_through=NOW + timedelta(days=39)
    )
    assert both.starts_next(NOW) == NOW + timedelta(days=39)
    assert plans.Plan("free").starts_next(NOW) == NOW


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (datetime(2027, 1, 31, 6, 30, tzinfo=UTC), datetime(2027, 2, 28, 6, 30, tzinfo=UTC)),
        (datetime(2028, 1, 31, 6, 30, tzinfo=UTC), datetime(2028, 2, 29, 6, 30, tzinfo=UTC)),
        (datetime(2026, 12, 15, 6, 30, tzinfo=UTC), datetime(2027, 1, 15, 6, 30, tzinfo=UTC)),
        # 20:00 UTC on 30 November is 1 December in India: a month later is 1 January IST.
        (datetime(2026, 11, 30, 20, 0, tzinfo=UTC), datetime(2026, 12, 31, 20, 0, tzinfo=UTC)),
    ],
)
def test_months_are_calendar_months_in_india(start: datetime, end: datetime) -> None:
    assert plans.add_month(start) == end


def test_premium_features_refuse_the_free_plan() -> None:
    settings = billing_settings()
    free = session_with(household(consented_at=SIGNED_UP - timedelta(days=90)))
    with pytest.raises(AccessError) as refused:
        plans.require_premium(free, settings, uuid4())
    assert refused.value.code == "premium_required" and refused.value.status == 402
    plans.require_premium(
        session_with(household()), billing_settings(billing_enabled=False), uuid4()
    )


@pytest.mark.parametrize(
    ("typed", "kept"),
    [
        ("someone@example.in", "someone@example.in"),
        ("  first.last_1-x@mail.example.co.in ", "first.last_1-x@mail.example.co.in"),
        ("plus+tag@example.in", None),  # PayU does not accept "+"
        ("two..dots@example.in", None),
        ("no-at-sign.example.in", None),
        ("a" * 45 + "@ex.in", None),  # over PayU's 50 characters
    ],
)
def test_emails_follow_what_payu_accepts(typed: str, kept: str | None) -> None:
    assert contact.clean_email(typed) == kept


@pytest.mark.parametrize(
    ("typed", "kept"),
    [
        ("+91 98765 43210", "9876543210"),
        ("919876543210", "9876543210"),
        ("09876543210", "9876543210"),
        ("9876543210", "9876543210"),
        ("5876543210", None),
        ("12345", None),
        ("+44 7700 900123", "447700900123"),
        ("98765abc10", None),
    ],
)
def test_phones(typed: str, kept: str | None) -> None:
    assert contact.clean_phone(typed) == kept


def test_contact_is_shown_masked() -> None:
    known = contact.Contact("someone@example.in", "9876543210")
    assert known.masked_email == "s•••@example.in" and known.masked_phone == "•••• 3210"


def test_saving_rejects_bad_contact_before_touching_the_database() -> None:
    session = MagicMock()
    with pytest.raises(AccessError) as refused:
        contact.save(session, billing_settings(), uuid4(), email="not-an-email", phone=None)
    assert refused.value.code == "invalid_contact"
    session.get.assert_not_called()


def link_session(epoch: int = 3, **changes: object) -> MagicMock:
    row = SimpleNamespace(session_epoch=epoch, deleted_at=None, pilot=False)
    for name, value in changes.items():
        setattr(row, name, value)
    session = MagicMock()
    session.execute.return_value.one_or_none.return_value = row
    return session


def test_pay_links_name_one_household_while_fresh() -> None:
    settings = billing_settings(web_session_key=Fernet.generate_key().decode())
    user = uuid4()
    url = links.link(settings, user, 3, "hi")
    assert url.startswith("http://127.0.0.1:3071/pay#")
    holder = links.read(link_session(), settings, url.split("#", 1)[1])
    assert holder.user_id == user and holder.language == "hi"
    token = links.token(settings, user, 3, "xx")
    assert links.read(link_session(), settings, token).language == "en"


@pytest.mark.parametrize(
    "session",
    [
        link_session(epoch=4),  # signed out everywhere since
        link_session(pilot=True),
        link_session(deleted_at=datetime(2026, 12, 1, tzinfo=UTC)),
    ],
)
def test_pay_links_die_with_the_session_epoch(session: MagicMock) -> None:
    settings = billing_settings(web_session_key=Fernet.generate_key().decode())
    token = links.token(settings, uuid4(), 3, "en")
    with pytest.raises(AccessError) as refused:
        links.read(session, settings, token)
    assert refused.value.code == "link_expired"


def test_pay_links_expire_and_cannot_be_forged() -> None:
    settings = billing_settings(web_session_key=Fernet.generate_key().decode())
    fernet = Fernet(session_key(settings))
    stale = fernet.encrypt_at_time(
        f"{links.PREFIX}{uuid4()}:3:en".encode(), int(NOW.timestamp()) - 8 * 24 * 3600
    ).decode()
    other_purpose = fernet.encrypt(f"finboy:user:v2:{uuid4()}:3".encode()).decode()
    forged = Fernet(Fernet.generate_key()).encrypt(f"{links.PREFIX}{uuid4()}:3:en".encode())
    for token in (stale, other_purpose, forged.decode(), "x" * 600, ""):
        with pytest.raises(AccessError):
            links.read(link_session(), settings, token)
