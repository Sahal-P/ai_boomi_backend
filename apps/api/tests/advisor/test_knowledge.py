"""Money guides: the reviewed library, keyword and meaning search, and the guide tool."""

import json
import re
from datetime import date

import pytest
from finboy.db.models.advisor import KnowledgeEmbedding
from finboy.services import providers
from finboy.services.advisor import embeddings, knowledge, ranking, tools
from sqlalchemy import func, select

from .support import ConceptEmbedder, FixtureToolbox, embedding_settings, make_settings

TODAY = date(2026, 11, 7)
GUIDE = """---
id: {id}
title: {title}
title_hi: हिंदी शीर्षक
title_ml: മലയാളം തലക്കെട്ട്
terms: {terms}
sources: https://example.gov.in/guide
reviewed_on: {reviewed}
---
{body}
"""


def guide(
    id: str = "sample",
    title: str = "Sample guide",
    terms: str = "sample words",
    body: str = "Body text.",
    reviewed: str = "2026-11-07",
) -> str:
    return GUIDE.format(id=id, title=title, terms=terms, body=body, reviewed=reviewed)


def test_a_guide_file_needs_every_field_and_https_sources() -> None:
    parsed = knowledge.parse(guide())
    assert parsed.id == "sample" and parsed.title("hi") == "हिंदी शीर्षक"
    assert parsed.title("xx") == "Sample guide" and parsed.reviewed_on == TODAY
    assert parsed.sources == ("https://example.gov.in/guide",)
    assert knowledge.parse(guide(reviewed="")).reviewed_on is None
    for broken in (
        "no front matter",
        guide().replace("https://", "http://"),
        guide().replace("title_ml: മലയാളം തലക്കെട്ട്\n", ""),
        guide(body=""),
        guide(reviewed="soon"),
    ):
        with pytest.raises(knowledge.GuideError):
            knowledge.parse(broken)


def test_the_library_covers_its_topics_in_three_languages() -> None:
    guides = knowledge.library()
    assert len(guides) >= 30
    for item in guides:
        assert item.titles["en"] and item.titles["hi"] and item.titles["ml"], item.id
        assert item.sources and item.body and len(item.terms) >= 3, item.id
        terms = " ".join(item.terms)
        assert re.search("[ऀ-ॿ]", terms) and re.search("[ഀ-ൿ]", terms), item.id


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("How do I build an emergency fund?", "emergency-fund"),
        ("pm kisan ki kist nahi aayi", "pm-kisan"),
        ("किसान सम्मान निधि का पैसा कब आएगा", "pm-kisan"),
        ("ആയുഷ്മാൻ കാർഡ് എങ്ങനെ കിട്ടും", "ayushman-bharat"),
        ("someone asked for my UPI PIN to send me money", "upi-safety"),
        ("an instant loan app is harassing my contacts", "loan-apps-safety"),
        ("what is PMJJBY", "pmjjby"),
    ],
)
def test_keywords_find_the_guide_in_any_language(query: str, expected: str) -> None:
    hits = knowledge.search(query)
    assert hits and hits[0].guide.id == expected and hits[0].by == "keywords"


def test_production_serves_only_reviewed_guides(monkeypatch) -> None:
    reviewed = knowledge.parse(guide(id="reviewed"))
    draft = knowledge.parse(guide(id="draft", reviewed=""))
    monkeypatch.setattr(knowledge, "library", lambda: (reviewed, draft))
    production = make_settings().model_copy(update={"environment": "production"})
    assert [item.id for item in knowledge.serving(production)] == ["reviewed"]
    assert [item.id for item in knowledge.serving(make_settings())] == ["reviewed", "draft"]


def test_meaning_finds_a_guide_without_shared_words_and_is_cached(session, monkeypatch) -> None:
    apples = knowledge.parse(guide(id="apples", title="Apples", terms="apples", body="Apples."))
    bananas = knowledge.parse(
        guide(id="bananas", title="Bananas", terms="bananas", body="Bananas.")
    )
    monkeypatch.setattr(knowledge, "library", lambda: (apples, bananas))
    embedder = ConceptEmbedder({"apple": 0, "doctor": 0, "banana": 1})
    monkeypatch.setattr(embeddings, "embed", embedder)
    settings = embedding_settings()
    query = "what keeps the doctor away"
    vector = embedder.vector(query)
    hits = knowledge.search(query, settings=settings, session=session, query_vector=vector)
    assert [(hit.guide.id, hit.by) for hit in hits] == [("apples", "meaning")]
    assert session.scalar(select(func.count()).select_from(KnowledgeEmbedding)) == 2
    knowledge.search(query, settings=settings, session=session, query_vector=vector)
    assert len(embedder.calls) == 1  # the guides once; the cache serves them after that


def test_the_guide_tool_keeps_what_it_found_for_citing() -> None:
    ctx = tools.Context(today=TODAY)
    box = FixtureToolbox()
    found = json.loads(
        tools.run(box, "search_knowledge", json.dumps({"query": "PM-KISAN instalment"}), ctx).output
    )
    assert found["guides"][0]["id"] == "pm-kisan" and "pm-kisan" in ctx.guides
    assert found["guides"][0]["official_sources"] == ["https://pmkisan.gov.in"]
    nothing = json.loads(
        tools.run(box, "search_knowledge", json.dumps({"query": "xyzzy plugh"}), ctx).output
    )
    assert nothing["guides"] == [] and "No FinBoy guide" in nothing["note"]
    blank = tools.run(box, "search_knowledge", json.dumps({"query": " "}), ctx)
    assert "query" in json.loads(blank.output)["error"]


def test_the_guides_are_offered_only_once_released() -> None:
    off = make_settings()
    on = off.model_copy(update={"knowledge_enabled": True})

    def names(settings) -> list[str]:
        return [item["function"]["name"] for item in tools.definitions(settings)]

    assert "search_knowledge" not in names(off) and "search_knowledge" in names(on)
    ctx = tools.Context(today=TODAY)
    refused = tools.run(FixtureToolbox(), "search_knowledge", '{"query": "ppf"}', ctx, off)
    assert json.loads(refused.output) == {"error": "unknown tool"}


def test_ranking_keeps_indic_words_whole_and_fuses_by_rank() -> None:
    assert "किस्त" in ranking.tokens("किसान की किस्त")
    assert ranking.tokens("ആയുഷ്മാൻ കാർഡ്") == ["ആയുഷ്മാൻ", "കാർഡ്"]
    assert ranking.bm25("bike", {"a": "bike loan", "b": "gold"})["b"] == 0
    assert ranking.phrase_hits("PM Kisan ki kist", ["pm kisan", "jan dhan"]) == 1
    assert ranking.fuse(["a", "b"], ["b", "c"]) == ["b", "a", "c"]


def test_readiness_says_whether_there_are_guides_to_serve(monkeypatch) -> None:
    monkeypatch.setattr(knowledge, "library", lambda: (knowledge.parse(guide(reviewed="")),))
    off = make_settings()
    on = off.model_copy(update={"knowledge_enabled": True})
    production = on.model_copy(update={"environment": "production"})
    assert providers.knowledge(off) == "off" and providers.knowledge(on) == "configured"
    assert providers.knowledge(production) == "missing"  # nothing reviewed to serve yet
