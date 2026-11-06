"""The disposable local database for the admin integration tests, and what each test leaves.

Synthetic households, numbers and admins only. Everything a test creates is removed afterwards.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from finboy.core.access import USER_PREFIX, cookie_names
from finboy.core.config import Settings
from finboy.db.models.admin import AdminEvent, AdminUser
from finboy.db.models.core import User
from finboy.db.models.mail import AuditEvent
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.db.session import build_engine
from finboy.services.accounts import households
from finboy.services.admin import auth
from finboy.services.whatsapp.config import keyed_digest
from sqlalchemy import delete, or_, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

SESSION_KEY = Fernet.generate_key().decode()
ENCRYPTION_KEY = Fernet.generate_key().decode()
PASSWORD = "synthetic-admin-password"
LOGIN = "/api/v1/admin/login"
# Households and admins each test made, removed afterwards.
CREATED: list[UUID] = []
ADMINS: list[UUID] = []


def local_settings(**changes: object) -> Settings:
    base = Settings()
    url = make_url(base.database_url.get_secret_value())
    if (
        base.environment == "production"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database
        not in {"finboy_admin", "finboy_signup", "finboy_billing", "finboy_advisor", "finboy_test"}
    ):
        pytest.fail("Admin integration tests require a disposable local database")
    return Settings(
        _env_file=None,
        **{
            **base.model_dump(),
            "environment": "development",
            "openai_api_key": None,
            "whatsapp_enabled": False,
            "cors_origins": ["http://127.0.0.1:3081"],
            "web_app_url": "http://127.0.0.1:3081",
            "web_session_key": SESSION_KEY,
            "token_encryption_key": ENCRYPTION_KEY,
            "signup_enabled": True,
            "billing_enabled": True,
            "billing_launch_date": None,
            "billing_owner_included": False,
            "payu_environment": "test",
            "payu_merchant_key": "tEsTkY",
            "payu_merchant_salt": "s4ltForTestsOnly0123456789abcdef",
            "payu_autopay_enabled": False,
            "api_public_url": "http://127.0.0.1:8081",
            **changes,
        },
    )


def open_world() -> Iterator[tuple[Settings, sessionmaker]]:
    settings = local_settings()
    engine = build_engine(settings)
    pg = sessionmaker(engine, expire_on_commit=False)
    CREATED.clear()
    ADMINS.clear()
    try:
        yield settings, pg
    finally:
        with pg() as session:
            named = [str(admin_id) for admin_id in ADMINS]
            session.execute(
                delete(AdminEvent).where(
                    or_(
                        AdminEvent.admin_id.in_(ADMINS),
                        AdminEvent.household_id.in_(CREATED),
                        AdminEvent.detail["admin"].astext.in_(named),
                    )
                )
            )
            session.execute(delete(AdminUser).where(AdminUser.id.in_(ADMINS)))
            for user_id in CREATED:
                if session.get(User, user_id) is None:
                    continue  # a discarded sign-up keeps nothing
                households.remove_household_data(session, user_id)
                households.remove_sign_in(session, user_id)
                session.execute(delete(AuditEvent).where(AuditEvent.user_id == user_id))
                session.execute(delete(User).where(User.id == user_id))
            session.commit()
        engine.dispose()


def create_admin(pg: sessionmaker, email: str, password: str = PASSWORD) -> UUID:
    with pg() as session:
        admin = auth.create_admin(
            session, email=email, password=password, created_by=None, must_change_password=False
        )
        session.commit()
        ADMINS.append(admin.id)
        return admin.id


def admin_id(pg: sessionmaker, email: str) -> UUID:
    with pg() as session:
        found = session.scalar(select(AdminUser.id).where(AdminUser.email == email))
    assert found is not None
    return found


def household(
    pg: sessionmaker,
    *,
    kind: str = "self_serve",
    joined_days_ago: int = 3,
    phone: str | None = None,
) -> UUID:
    """A synthetic household; `phone` (digits with country code) adds a WhatsApp binding."""
    joined = datetime.now(UTC) - timedelta(days=joined_days_ago)
    with pg() as session:
        user = User(
            id=uuid4(),
            display_name="SENSITIVE NAME",
            pilot=kind == "pilot",
            joined_via=None if kind == "pilot" else "whatsapp",
            consented_at=None if kind == "pending" else joined,
            created_at=joined,
        )
        session.add(user)
        session.flush()
        if phone is not None:
            session.add(
                WhatsAppBinding(
                    user_id=user.id,
                    sender_hash=keyed_digest(ENCRYPTION_KEY.encode(), "sender", phone),
                    language="hi",
                    last_inbound_at=joined,
                )
            )
        session.commit()
    CREATED.append(user.id)
    return user.id


def epoch(pg: sessionmaker, user_id: UUID) -> int:
    with pg() as session:
        value = session.scalar(select(User.session_epoch).where(User.id == user_id))
    assert value is not None
    return value


def household_cookie(settings: Settings, user_id: UUID, session_epoch: int) -> dict[str, str]:
    """The household's own web session, as sign-in would issue it."""
    token = Fernet(SESSION_KEY).encrypt(f"{USER_PREFIX}{user_id}:{session_epoch}".encode())
    return {cookie_names(settings)[0]: token.decode()}


def signed_in(app, email: str, password: str = PASSWORD) -> TestClient:
    browser = TestClient(app)
    response = browser.post(LOGIN, json={"email": email, "password": password})
    assert response.status_code == 200, response.json()
    return browser
