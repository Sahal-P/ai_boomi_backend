"""Quiet chats get a short summary and title for later chats to draw on."""

from datetime import UTC, datetime, timedelta

from finboy.core.config import LOCAL_USER_ID
from finboy.services.advisor import history, summaries

from .support import ScriptedModel


def test_a_quiet_chat_is_summarised_and_titled(factory, settings, monkeypatch) -> None:
    earlier = datetime.now(UTC) - timedelta(hours=8)
    with factory() as session:
        old = history.save_turn(
            session,
            user_id=LOCAL_USER_ID,
            channel="whatsapp",
            thread=None,
            question="I want to buy a bike next year",
            answer="Let's plan it: how much can you keep each month?",
            language="en",
            tool_names=[],
            now=earlier,
        )
        session.commit()
        old_id = old.id
    model = ScriptedModel(
        summaries.ChatSummary(summary="They plan to buy a bike next year.", title="Bike plan")
    )
    monkeypatch.setattr(summaries, "client_for", lambda _settings: model)
    summaries._summarize(factory.kw["bind"], settings, LOCAL_USER_ID, None)
    with factory() as session:
        row = history.find(session, LOCAL_USER_ID, old_id)
        assert (row.summary, row.title) == ("They plan to buy a bike next year.", "Bike plan")
        assert row.summarized_at is not None
        assert history.earlier(session, LOCAL_USER_ID, None)[0].title == "Bike plan"
    transcript = model.calls[0]["input"][1]["content"]
    assert transcript.startswith("Household: I want to buy a bike next year")


def test_a_failed_summary_is_logged_without_content(factory, settings, monkeypatch, caplog):
    with factory() as session:
        history.save_turn(
            session,
            user_id=LOCAL_USER_ID,
            channel="web",
            thread=None,
            question="Secret question about Ramesh",
            answer="An answer",
            language="en",
            tool_names=[],
            now=datetime.now(UTC) - timedelta(hours=1),
        )
        session.commit()
    model = ScriptedModel(RuntimeError("provider said something sensitive"))
    monkeypatch.setattr(summaries, "client_for", lambda _settings: model)
    summaries._summarize(factory.kw["bind"], settings, LOCAL_USER_ID, None)
    assert "Ramesh" not in caplog.text and "sensitive" not in caplog.text
