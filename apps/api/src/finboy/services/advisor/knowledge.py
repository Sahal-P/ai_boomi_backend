"""FinBoy's money guides: a small reviewed library the advisor searches (advisor phase 2).

Guides live in Git as Markdown (`apps/api/knowledge/*.md`) with titles in English, Hindi and
Malayalam and search terms in all three languages and their Latin spellings, so a question in any
of them finds the right guide. Production serves only guides a person has reviewed
(`reviewed_on`). Search ranks guides by keywords and, when embeddings are configured, by meaning;
guide embeddings are cached in `knowledge_embeddings` and computed on first use or by
`pnpm knowledge:index`. Guides explain ideas and schemes; they never recommend products.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.db.models.advisor import KnowledgeEmbedding
from finboy.services.advisor import embeddings, ranking

LIBRARY = Path(__file__).resolve().parents[4] / "knowledge"
LIMIT = 3
# Below this cosine similarity a guide is not about the question, whatever its rank.
MEANING_FLOOR = 0.25
# A keyword match far weaker than the best one is noise (a shared word like "loan").
KEYWORD_SHARE = 0.35


class GuideError(ValueError):
    """A guide file that does not follow the format."""


@dataclass(frozen=True)
class Guide:
    id: str
    titles: dict[str, str]
    terms: tuple[str, ...]
    sources: tuple[str, ...]
    reviewed_on: date | None
    body: str

    def title(self, language: str = "en") -> str:
        return self.titles.get(language) or self.titles["en"]

    @property
    def search_text(self) -> str:
        return "\n".join([*self.titles.values(), " · ".join(self.terms), self.body])

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.search_text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Hit:
    guide: Guide
    by: str  # "keywords", "meaning" or "both"


def parse(text: str) -> Guide:
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise GuideError("missing front matter")
    head, body = text[4:].split("\n---\n", 1)
    fields: dict[str, str] = {}
    for line in head.splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            raise GuideError(f"bad line: {line}")
        fields[key.strip()] = value.strip()
    try:
        reviewed = date.fromisoformat(fields["reviewed_on"]) if fields.get("reviewed_on") else None
        guide = Guide(
            id=fields["id"],
            titles={"en": fields["title"], "hi": fields["title_hi"], "ml": fields["title_ml"]},
            terms=tuple(term.strip() for term in fields["terms"].split("|") if term.strip()),
            sources=tuple(url.strip() for url in fields["sources"].split("|") if url.strip()),
            reviewed_on=reviewed,
            body=body.strip(),
        )
    except (KeyError, ValueError) as error:
        raise GuideError(str(error)) from None
    if not guide.id or not guide.body or not guide.terms:
        raise GuideError("id, terms and body are required")
    if any(not url.startswith("https://") for url in guide.sources):
        raise GuideError("sources must be https links")
    return guide


@lru_cache(maxsize=1)
def library() -> tuple[Guide, ...]:
    guides = tuple(parse(path.read_text()) for path in sorted(LIBRARY.glob("*.md")))
    ids = [guide.id for guide in guides]
    if len(ids) != len(set(ids)):
        raise GuideError("duplicate guide ids")
    return guides


def serving(settings: Settings | None) -> tuple[Guide, ...]:
    """The guides people may see: in production, only reviewed ones."""
    guides = library()
    if settings is not None and settings.environment == "production":
        return tuple(guide for guide in guides if guide.reviewed_on is not None)
    return guides


def by_id(guide_id: str) -> Guide | None:
    return next((guide for guide in library() if guide.id == guide_id), None)


def keyword_ranking(query: str, guides: tuple[Guide, ...]) -> list[str]:
    scores = ranking.bm25(query, {guide.id: guide.search_text for guide in guides})
    for guide in guides:
        # A guide's own terms ("pm kisan", "सुकन्या समृद्धि") count much more than body words.
        scores[guide.id] += 4 * ranking.phrase_hits(query, [*guide.terms, *guide.titles.values()])
    best = max(scores.values(), default=0.0)
    floor = max(best * KEYWORD_SHARE, 1e-9)
    ordered = sorted(scores.items(), key=lambda item: -item[1])
    return [key for key, score in ordered if score >= floor]


def vectors(
    guides: tuple[Guide, ...], session: Session, settings: Settings
) -> dict[str, list[float]]:
    """Guide embeddings from the cache, computing and saving the missing ones."""
    model, dimensions = settings.openai_embedding_model, settings.advisor_embedding_dimensions
    hashes = {guide.content_hash: guide for guide in guides}
    cached = {
        row.content_hash: list(row.embedding)
        for row in session.scalars(
            select(KnowledgeEmbedding).where(
                KnowledgeEmbedding.content_hash.in_(list(hashes)),
                KnowledgeEmbedding.model == model,
                KnowledgeEmbedding.dimensions == dimensions,
            )
        )
    }
    missing = [guide for content, guide in hashes.items() if content not in cached]
    if missing:
        computed = embeddings.embed([guide.search_text for guide in missing], settings)
        if computed is not None:
            for guide, vector in zip(missing, computed, strict=True):
                session.merge(
                    KnowledgeEmbedding(
                        content_hash=guide.content_hash,
                        model=model,
                        dimensions=dimensions,
                        embedding=vector,
                    )
                )
                cached[guide.content_hash] = vector
            session.commit()
    return {
        guide.id: cached[guide.content_hash] for guide in guides if guide.content_hash in cached
    }


def meaning_ranking(
    query_vector: list[float] | None,
    guides: tuple[Guide, ...],
    session: Session | None,
    settings: Settings | None,
) -> list[str]:
    if query_vector is None or session is None or settings is None:
        return []
    found = vectors(guides, session, settings)
    scored = sorted(
        ((key, embeddings.similarity(query_vector, vector)) for key, vector in found.items()),
        key=lambda item: -item[1],
    )
    return [key for key, score in scored if score >= MEANING_FLOOR]


def search(
    query: str,
    *,
    settings: Settings | None = None,
    session: Session | None = None,
    query_vector: list[float] | None = None,
    limit: int = LIMIT,
) -> list[Hit]:
    """The best guides for a question: keywords always, meaning when embeddings are on."""
    guides = serving(settings)
    by_keywords = keyword_ranking(query, guides)
    by_meaning = meaning_ranking(query_vector, guides, session, settings)
    found = {guide.id: guide for guide in guides}
    hits: list[Hit] = []
    for key in ranking.fuse(by_keywords, by_meaning)[:limit]:
        both = key in by_keywords and key in by_meaning
        by = "both" if both else "keywords" if key in by_keywords else "meaning"
        hits.append(Hit(found[key], by))
    return hits


def tool_output(hits: list[Hit]) -> dict[str, Any]:
    if not hits:
        return {
            "guides": [],
            "note": "No FinBoy guide covers this. Explain briefly in general terms without "
            "figures, or say you don't know.",
        }
    return {
        "guides": [
            {
                "id": hit.guide.id,
                "title": hit.guide.title("en"),
                "title_hi": hit.guide.title("hi"),
                "title_ml": hit.guide.title("ml"),
                "text": hit.guide.body,
                "official_sources": list(hit.guide.sources),
                "reviewed_on": hit.guide.reviewed_on.isoformat() if hit.guide.reviewed_on else None,
            }
            for hit in hits
        ],
        "how_to_cite": "Put the ids of the guides you used in sources and name each one, like "
        '"(FinBoy guide: Emergency fund)", in the reply language.',
    }


def index(session: Session, settings: Settings) -> int:
    """Embed every served guide that has no cached embedding; returns how many were cached."""
    if not embeddings.available(settings):
        return 0
    return len(vectors(serving(settings), session, settings))


def main() -> None:
    """`pnpm knowledge:index`: check every guide parses and warm the embedding cache."""
    from finboy.db.session import build_engine

    guides = library()
    settings = Settings()  # type: ignore[call-arg]
    served = serving(settings)
    summary: dict[str, Any] = {"guides": len(guides), "served": len(served)}
    if embeddings.available(settings):
        engine = build_engine(settings)
        with Session(engine) as session:
            summary["embedded"] = index(session, settings)
        engine.dispose()
    else:
        summary["embedded"] = "off (OPENAI_EMBEDDING_MODEL unset): keyword search only"
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
