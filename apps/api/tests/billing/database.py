"""Database helpers for the billing integration tests: the disposable local database only."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.db.models.billing import BillingPayment, BillingProfile, Subscription
from finboy.db.models.core import User
from finboy.db.session import build_engine
from finboy.services.billing.payu import response_hash
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from .support import ENCRYPTION_KEY, KEY, SALT

# Households each test made, removed with their billing rows afterwards.
CREATED: list[UUID] = []


def local_settings(**changes: object) -> Settings:
    base = Settings()
    url = make_url(base.database_url.get_secret_value())
    if (
        base.environment == "production"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database not in {"finboy_billing", "finboy_signup", "finboy_admin", "finboy_test"}
    ):
        pytest.fail("Billing tests require a disposable local database")
    return Settings(
        _env_file=None,
        **{
            **base.model_dump(),
            "environment": "development",
            "openai_api_key": None,
            "whatsapp_enabled": False,
            "cors_origins": ["http://127.0.0.1:3071"],
            "web_app_url": "http://127.0.0.1:3071",
            "token_encryption_key": ENCRYPTION_KEY,
            "billing_enabled": True,
            "billing_launch_date": None,
            "billing_owner_included": False,
            "payu_environment": "test",
            "payu_merchant_key": KEY,
            "payu_merchant_salt": SALT,
            "payu_autopay_enabled": False,
            "api_public_url": "http://127.0.0.1:8071",
            **changes,
        },
    )


def open_world() -> Iterator[tuple[Settings, sessionmaker]]:
    settings = local_settings()
    engine = build_engine(settings)
    pg = sessionmaker(engine, expire_on_commit=False)
    CREATED.clear()
    try:
        yield settings, pg
    finally:
        with pg() as session:
            for user_id in [*CREATED, LOCAL_USER_ID]:
                session.execute(delete(BillingPayment).where(BillingPayment.user_id == user_id))
                session.execute(delete(Subscription).where(Subscription.user_id == user_id))
                session.execute(delete(BillingProfile).where(BillingProfile.user_id == user_id))
            for user_id in CREATED:
                session.execute(delete(User).where(User.id == user_id))
            session.commit()
        engine.dispose()


def household(pg: sessionmaker, *, joined_days_ago: int) -> UUID:
    with pg() as session:
        user = User(
            id=uuid4(),
            display_name="Household",
            joined_via="google",
            consented_at=datetime.now(UTC) - timedelta(days=joined_days_ago),
        )
        session.add(user)
        session.commit()
        CREATED.append(user.id)
        return user.id


def result(txnid: str, **overrides: str) -> dict[str, str]:
    fields = {
        "key": KEY,
        "txnid": txnid,
        "amount": "299.00",
        "productinfo": "FinBoy Premium monthly",
        "firstname": "FinBoy",
        "email": "someone@example.in",
        "status": "success",
        "mihpayid": str(int(uuid4().int % 10**15)),
        "mode": "UPI",
        "payment_source": "payu",
        "error": "E000",
    }
    fields.update(overrides)
    fields["hash"] = response_hash(fields, SALT)
    return fields
