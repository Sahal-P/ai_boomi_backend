"""Feedback on PostgreSQL (docs/feedback-round/contract.md): migration 0022's checks, a report
with its screenshot in a fake R2, and erasure removing the files before the rows. Synthetic words
only."""

from collections.abc import Iterator
from uuid import UUID

import pytest
from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.db.models.core import User
from finboy.db.models.feedback import Feedback
from finboy.db.session import build_engine
from finboy.services.accounts import households
from finboy.services.conversations import r2
from finboy.services.feedback import service
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration
DISPOSABLE = {"finboy_signup", "finboy_admin", "finboy_advisor", "finboy_test"}
PNG = b"\x89PNG\r\n\x1a\n" + bytes(32)


@pytest.fixture
def pg() -> Iterator[tuple[Settings, sessionmaker[Session]]]:
    base = Settings()
    url = make_url(base.database_url.get_secret_value())
    if (
        base.environment == "production"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database not in DISPOSABLE
    ):
        pytest.fail("Feedback tests require a disposable local FinBoy integration database")
    settings = Settings(
        **{
            **base.model_dump(),
            "r2_account_id": "0" * 32,
            "r2_access_key_id": "synthetic-access",
            "r2_secret_access_key": "synthetic-secret",
            "r2_bucket": "synthetic-bucket",
        },
        _env_file=None,
    )
    engine = build_engine(settings)
    try:
        yield settings, sessionmaker(engine, expire_on_commit=False)
    finally:
        engine.dispose()


@pytest.fixture
def bucket(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    files: dict[str, bytes] = {}

    def put(_settings: Settings, key: str, data: bytes, _content_type: str) -> None:
        files[key] = data

    def delete_folder(settings: Settings, user_id: UUID, prefix: str | None = None) -> int:
        folder = f"{prefix}{user_id}/" if prefix else r2.folder(settings, user_id)
        doomed = [key for key in files if key.startswith(folder)]
        for key in doomed:
            del files[key]
        return len(doomed)

    monkeypatch.setattr(r2, "put", put)
    monkeypatch.setattr(r2, "delete_folder", delete_folder)
    return files


def test_a_report_keeps_its_screenshot_until_the_household_is_erased(pg, bucket) -> None:
    settings, factory = pg
    with factory() as session:
        user = households.new_household(session, joined_via="whatsapp", agreed=True)
        session.commit()
        try:
            row, kept = service.create(
                session,
                settings,
                user.id,
                kind="problem",
                message="synthetic words",
                page="/review",
                image=("image/png", PNG),
            )
            assert kept and row.screenshot_key == f"finboy-feedback-dev/{user.id}/{row.id}.png"
            assert bucket == {row.screenshot_key: PNG} and row.status == "new"
            # The database refuses what the API never sends.
            session.add(Feedback(user_id=user.id, kind="complaint", message="x"))
            with pytest.raises(IntegrityError):
                session.flush()
            session.rollback()
            # Without R2 settings, a household with screenshots waits instead of orphaning them.
            with pytest.raises(AccessError):
                households.remove_household_data(session, user.id)
            session.rollback()
            counts = households.erase_household(session, user.id, settings)
            session.commit()
            assert counts["feedback"] == 1 and bucket == {}
            left = select(func.count()).select_from(Feedback).where(Feedback.user_id == user.id)
            assert session.scalar(left) == 0
        finally:
            session.rollback()
            session.execute(delete(Feedback).where(Feedback.user_id == user.id))
            session.execute(delete(User).where(User.id == user.id))
            session.commit()
