"""A suspended household keeps no web session and gets no new sign-in, without a database."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from finboy.api import deps
from finboy.api.v1.auth import _usable
from finboy.core.access import USER_PREFIX, Claim, cookie_names, session_key
from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.services.accounts.households import active
from sqlalchemy.orm import Session

NOW = datetime(2026, 11, 5, 9, 30, tzinfo=UTC)


def household(**changes: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": uuid4(),
        "pilot": False,
        "session_epoch": 3,
        "deleted_at": None,
        "suspended_at": None,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def request_for(settings: Settings, claim: Claim) -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(claim=claim),
        app=SimpleNamespace(state=SimpleNamespace(settings=settings)),
    )


def test_only_a_household_neither_deleted_nor_suspended_is_active() -> None:
    assert active(household())
    assert not active(household(suspended_at=NOW))
    assert not active(household(deleted_at=NOW))


def test_a_suspended_household_cannot_use_its_web_session(settings: Settings) -> None:
    row = household(suspended_at=NOW)
    db = MagicMock(spec=Session)
    db.execute.return_value.one_or_none.return_value = row
    request = request_for(settings, Claim(row.id, row.session_epoch))
    with pytest.raises(AccessError, match="^account_suspended$"):
        deps.current_user_id(request, db)
    row.suspended_at = None  # restored
    assert deps.current_user_id(request, db) == row.id


def test_a_suspended_household_cannot_sign_in_again() -> None:
    with pytest.raises(AccessError, match="^account_suspended$"):
        _usable(household(suspended_at=NOW))
    with pytest.raises(AccessError, match="^invalid_sign_in$"):
        _usable(household(deleted_at=NOW, suspended_at=NOW))


@pytest.mark.parametrize(
    ("changes", "status", "expected"),
    [
        ({"suspended_at": NOW}, 403, "account_suspended"),
        ({"session_epoch": 4}, 401, "authentication_required"),  # signed out everywhere
    ],
)
@pytest.mark.anyio
async def test_money_routes_answer_a_paused_or_stale_session_with_its_own_code(
    settings: Settings,
    client: httpx.AsyncClient,
    session: MagicMock,
    changes: dict[str, object],
    status: int,
    expected: str,
) -> None:
    row = household()
    token = Fernet(session_key(settings)).encrypt(f"{USER_PREFIX}{row.id}:3".encode())
    client.cookies.set(cookie_names(settings)[0], token.decode())
    for name, value in changes.items():
        setattr(row, name, value)
    session.execute.return_value.one_or_none.return_value = row
    for path in ("/api/v1/money/summary", "/api/v1/transactions"):
        response = await client.get(path)
        assert response.status_code == status, path
        assert response.json()["error"]["code"] == expected
