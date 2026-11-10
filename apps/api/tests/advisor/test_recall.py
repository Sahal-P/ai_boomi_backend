"""Deeper recall: memories by relevance once there are many, and search over earlier chats."""

from datetime import UTC, datetime, timedelta

from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.advisor import HouseholdMemory
from finboy.services.advisor import embeddings, history, memory, summaries
from sqlalchemy import select, update

from .support import OTHER_USER, ConceptEmbedder, ScriptedModel, embedding_settings

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def add(session, kind: str, text: str, minutes: int, user_id=LOCAL_USER_ID) -> None:
    change = memory.remember(session, user_id, kind, text, "web", 300)
    assert change is not None and change.id is not None
    session.execute(
        update(HouseholdMemory)
        .where(HouseholdMemory.id == change.id)
        .values(updated_at=BASE + timedelta(minutes=minutes))
    )


def many(session, count: int = 50) -> None:
    for number in range(count):
        add(session, "note", f"Fact number {number}", minutes=number + 1)


def chat(session, question: str, answer: str, hours_ago: float, user_id=LOCAL_USER_ID):
    return history.save_turn(
        session,
        user_id=user_id,
        channel="web",
        thread=None,
        question=question,
        answer=answer,
        language="en",
        tool_names=[],
        now=datetime.now(UTC) - timedelta(hours=hours_ago),
    )


def test_every_memory_goes_in_while_there_are_few(session, settings) -> None:
    many(session, 5)
    session.commit()
    assert len(memory.recall(session, LOCAL_USER_ID, "anything", settings)) == 5


def test_with_many_the_newest_and_those_closest_to_the_question_go_in(session, settings) -> None:
    add(session, "person", "Riya's school fees of ₹12,000 are due every June", minutes=0)
    many(session)
    add(session, "person", "Ravi's rent is due on the 5th", minutes=0, user_id=OTHER_USER)
    session.commit()
    chosen = memory.recall(session, LOCAL_USER_ID, "When are Riya's school fees due?", settings)
    texts = [row.text for row in chosen]
    assert len(texts) == settings.advisor_memory_prompt
    assert texts[:10] == [f"Fact number {number}" for number in range(49, 39, -1)]
    assert "Riya's school fees of ₹12,000 are due every June" in texts
    assert not any("Ravi" in text for text in texts)


def test_meaning_recall_embeds_missing_memories_with_the_question(session, monkeypatch) -> None:
    settings = embedding_settings()
    embedder = ConceptEmbedder({"bike": 0, "motorcycle": 0})
    monkeypatch.setattr(embeddings, "embed", embedder)
    add(session, "goal", "Saving ₹40,000 for a bike by March 2027", minutes=0)
    many(session)
    session.commit()
    chosen = memory.recall(session, LOCAL_USER_ID, "how is my motorcycle plan going", settings)
    assert "Saving ₹40,000 for a bike by March 2027" in [row.text for row in chosen]
    assert len(embedder.calls) == 1 and len(embedder.calls[0]) == 52  # question + 51 memories
    models = set(session.scalars(select(HouseholdMemory.embedding_model)))
    assert models == {"synthetic-embedding"}
    memory.recall(session, LOCAL_USER_ID, "anything else", settings)
    assert embedder.calls[1] == ["anything else"]  # saved embeddings are reused
    bike = session.scalar(select(HouseholdMemory).where(HouseholdMemory.kind == "goal"))
    assert bike is not None
    memory.edit(session, LOCAL_USER_ID, bike.id, "Saving ₹50,000 for a bike by June 2027")
    session.commit()
    assert bike.embedding is None and bike.embedding_model is None


def test_past_chats_are_found_by_their_words_within_the_household(session) -> None:
    gold = chat(session, "Is a gold loan a good idea for the wedding?", "Compare the rate", 72)
    chat(session, "How much did I spend on food?", "₹4,200 this month", 48)
    current = chat(session, "Hi", "Hello! How can I help?", 0)
    chat(session, "gold loan for my shop", "Here is how they work", 24, user_id=OTHER_USER)
    session.commit()
    hits = history.search(session, LOCAL_USER_ID, "that gold loan we discussed", exclude=current.id)
    assert [hit.thread_id for hit in hits] == [gold.id]
    assert hits[0].excerpt == (
        "They asked: Is a gold loan a good idea for the wedding? FinBoy said: Compare the rate"
    )
    assert history.search(session, LOCAL_USER_ID, "gold loan", exclude=gold.id) == []


def test_past_chats_match_by_meaning_through_their_summaries(session) -> None:
    settings = embedding_settings()
    vector = embeddings.normalise([1.0] + [0.0] * 63)
    wedding = chat(session, "Shaadi ka kharcha kaise sambhale?", "Ek list banaiye", 72)
    wedding.summary = "They asked how to plan wedding costs."
    wedding.summarized_at = datetime.now(UTC)
    wedding.summary_embedding, wedding.embedding_model = vector, "synthetic-embedding"
    chat(session, "Food this month?", "₹4,200", 24)
    session.commit()
    hits = history.search(
        session, LOCAL_USER_ID, "marriage budget", settings=settings, query_vector=vector
    )
    assert [hit.thread_id for hit in hits] == [wedding.id]
    assert hits[0].summary == "They asked how to plan wedding costs."


def test_summaries_get_embeddings_and_continued_chats_are_summarised_again(
    factory, monkeypatch
) -> None:
    settings = embedding_settings()
    monkeypatch.setattr(embeddings, "embed", ConceptEmbedder({"bike": 0}))
    with factory() as session:
        thread_id = chat(session, "I want a bike", "How much can you keep each month?", 8).id
        session.commit()
    model = ScriptedModel(
        summaries.ChatSummary(summary="They want a bike.", title="Bike plan"),
        summaries.ChatSummary(summary="They want a bike and its insurance.", title="Bike"),
    )
    monkeypatch.setattr(summaries, "client_for", lambda _settings: model)
    summaries._summarize(factory.kw["bind"], settings, LOCAL_USER_ID, None)
    with factory() as session:
        row = history.find(session, LOCAL_USER_ID, thread_id)
        assert row.summary == "They want a bike." and row.embedding_model == "synthetic-embedding"
        assert row.summary_embedding is not None and row.summary_embedding[0] == 1.0
        row.summarized_at = datetime.now(UTC) - timedelta(hours=7)
        history.save_turn(
            session,
            user_id=LOCAL_USER_ID,
            channel="web",
            thread=row,
            question="And the bike insurance?",
            answer="Third-party cover is required by law.",
            language="en",
            tool_names=[],
            now=datetime.now(UTC) - timedelta(hours=1),
        )
        session.commit()
        quiet = history.quiet_unsummarized(session, LOCAL_USER_ID, None)
        assert [item.id for item in quiet] == [thread_id]
    summaries._summarize(factory.kw["bind"], settings, LOCAL_USER_ID, None)
    with factory() as session:
        row = history.find(session, LOCAL_USER_ID, thread_id)
        assert row.summary == "They want a bike and its insurance."
        assert row.summary_embedding is not None
        assert history.quiet_unsummarized(session, LOCAL_USER_ID, None) == []
