"""Text embeddings for semantic search (advisor phase 2, docs/advisor-round/contract.md).

OpenAI embeddings at `ADVISOR_EMBEDDING_DIMENSIONS`, normalised to unit length so a dot product
is the cosine similarity. Without `OPENAI_EMBEDDING_MODEL` (or when a call fails) callers fall back
to keyword search; nothing is logged but the outcome. The vectors are small and few (a few hundred
per household, about forty guides), so they are compared in Python rather than in the database.
"""

import logging
import math
from collections.abc import Sequence

from finboy.core.config import Settings
from finboy.services.advisor.client import _client

logger = logging.getLogger(__name__)
TIMEOUT_SECONDS = 8
BATCH = 64


def available(settings: Settings) -> bool:
    key = settings.openai_api_key
    return bool(key and key.get_secret_value() and settings.openai_embedding_model)


def normalise(vector: Sequence[float]) -> list[float]:
    length = math.sqrt(math.fsum(value * value for value in vector))
    return [value / length for value in vector] if length else list(vector)


def similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two unit vectors; mismatched lengths never match."""
    if len(a) != len(b):
        return 0.0
    return math.fsum(x * y for x, y in zip(a, b, strict=True))


def embed(texts: Sequence[str], settings: Settings) -> list[list[float]] | None:
    """One unit vector per text, in order, or None when embeddings are off or fail."""
    if not texts or not available(settings):
        return None
    dimensions = settings.advisor_embedding_dimensions
    client = _client(settings.openai_api_key.get_secret_value(), settings.provider_max_retries)
    vectors: list[list[float]] = []
    try:
        for start in range(0, len(texts), BATCH):
            batch = [text[:8000] for text in texts[start : start + BATCH]]
            response = client.embeddings.create(
                model=settings.openai_embedding_model,
                input=batch,
                dimensions=dimensions,
                timeout=TIMEOUT_SECONDS,
            )
            rows = sorted(response.data, key=lambda row: row.index)
            if len(rows) != len(batch):
                raise ValueError("embedding_count")
            vectors.extend(normalise(row.embedding) for row in rows)
    except Exception:
        logger.warning("advisor.embedding", extra={"outcome": "failed", "count": len(texts)})
        return None
    if any(len(vector) != dimensions for vector in vectors):
        logger.warning("advisor.embedding", extra={"outcome": "wrong_size", "count": len(texts)})
        return None
    return vectors
