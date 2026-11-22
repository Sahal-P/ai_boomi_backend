"""Feedback email and erasure (docs/feedback-round/contract.md)."""

import pytest
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.core.errors import AccessError
from finboy.db.models.feedback import Feedback
from finboy.services.conversations import r2
from finboy.services.feedback import service
from sqlalchemy import select


def settings(**extra) -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
        cors_origins=["http://localhost:3000"],
        environment="test",
        web_app_url="http://localhost:3000",
        **extra,
    )


def test_the_owner_email_names_the_kind_and_links_never_the_words(factory, monkeypatch) -> None:
    sent: list[tuple[str, object]] = []
    monkeypatch.setattr(
        service.resend, "send", lambda _s, to, message, _id: sent.append((to, message))
    )
    with factory() as session:
        row = Feedback(user_id=LOCAL_USER_ID, kind="problem", message="my SBI card 4321")
        session.add(row)
        session.commit()
        feedback_id = row.id
    configured = settings(feedback_email="owner@example.test", resend_api_key="re_synthetic")
    service.notify(factory, configured, feedback_id)
    service.notify(factory, configured, feedback_id)  # sent once
    ((to, message),) = sent
    assert to == "owner@example.test" and "a problem" in message.subject
    assert "SBI" not in message.text + message.html and str(feedback_id) in message.text
    with factory() as session:
        assert session.get(Feedback, feedback_id).notified_at is not None


def test_no_email_without_an_address(factory, monkeypatch) -> None:
    monkeypatch.setattr(service.resend, "send", lambda *_args: pytest.fail("no email expected"))
    with factory() as session:
        row = Feedback(user_id=LOCAL_USER_ID, kind="idea", message="x")
        session.add(row)
        session.commit()
    service.notify(factory, settings(), row.id)


def test_erasure_removes_the_folder_then_the_rows(session, monkeypatch) -> None:
    removed: list[str] = []
    session.add(Feedback(user_id=LOCAL_USER_ID, kind="idea", message="x", screenshot_key="k"))
    session.commit()
    monkeypatch.setattr(r2, "configured", lambda _settings: True)
    monkeypatch.setattr(r2, "delete_folder", lambda _s, user, prefix: removed.append(prefix))
    assert service.remove_all(session, settings(), LOCAL_USER_ID) == 1
    assert removed == ["finboy-feedback-dev/"]
    assert session.scalars(select(Feedback)).all() == []


def test_erasure_waits_while_screenshots_cannot_be_removed(session) -> None:
    session.add(Feedback(user_id=LOCAL_USER_ID, kind="idea", message="x", screenshot_key="k"))
    session.commit()
    with pytest.raises(AccessError):
        service.remove_all(session, settings(), LOCAL_USER_ID)


@pytest.mark.parametrize(
    ("page", "expected"),
    [("/review?x=1", "/review"), ("https://evil.test/x", ""), ("//evil", ""), ("/a#b", "/a")],
)
def test_only_an_app_path_is_kept(page: str, expected: str) -> None:
    assert service.app_path(page) == expected
