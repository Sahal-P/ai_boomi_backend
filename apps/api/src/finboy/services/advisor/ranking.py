"""Keyword ranking and rank fusion for the advisor's searches (advisor phase 2).

BM25 over simple tokens works for English, Hindi, Malayalam and their Latin spellings without a
language toolkit: text is case-folded and split on spaces and punctuation only, so Devanagari and
Malayalam vowel signs stay inside their words. Reciprocal rank fusion merges keyword and meaning
rankings without having to compare their scores.
"""

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping

SPLIT = re.compile(r"[\s.,;:!?()\[\]{}\"'“”‘’/\\|\-–—…।॥*#>+=%₹_]+")
# Common question words that say nothing about the topic, in English, Hinglish and Hindi.
STOP = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "the",
        "to",
        "what",
        "when",
        "which",
        "who",
        "why",
        "will",
        "with",
        "you",
        "your",
        "hai",
        "ka",
        "ki",
        "ke",
        "ko",
        "kya",
        "mein",
        "se",
        "है",
        "का",
        "की",
        "के",
        "को",
        "क्या",
        "में",
        "से",
        "और",
    ]
)
K1, B = 1.4, 0.75


def normal(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def tokens(text: str) -> list[str]:
    return [token for token in SPLIT.split(normal(text)) if token and token not in STOP]


def bm25(query: str, documents: Mapping[str, str]) -> dict[str, float]:
    """BM25 score per document id for the query; documents with no shared word score 0."""
    words = set(tokens(query))
    if not words or not documents:
        return {key: 0.0 for key in documents}
    bags = {key: Counter(tokens(text)) for key, text in documents.items()}
    average = sum(sum(bag.values()) for bag in bags.values()) / len(bags) or 1.0
    total = len(bags)
    scores: dict[str, float] = {}
    for key, bag in bags.items():
        length = sum(bag.values())
        score = 0.0
        for word in words:
            frequency = bag.get(word, 0)
            if not frequency:
                continue
            holders = sum(1 for other in bags.values() if word in other)
            idf = math.log(1 + (total - holders + 0.5) / (holders + 0.5))
            score += idf * frequency * (K1 + 1) / (frequency + K1 * (1 - B + B * length / average))
        scores[key] = score
    return scores


def phrase_hits(query: str, phrases: Iterable[str]) -> int:
    """How many of the phrases appear whole in the query (after case folding)."""
    folded = " " + " ".join(SPLIT.split(normal(query))) + " "
    count = 0
    for phrase in phrases:
        wanted = " ".join(SPLIT.split(normal(phrase))).strip()
        if wanted and f" {wanted} " in folded:
            count += 1
    return count


def fuse(*rankings: list[str], k: int = 60) -> list[str]:
    """Reciprocal rank fusion of ranked id lists, best first."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, key in enumerate(ranking):
            scores[key] = scores.get(key, 0.0) + 1 / (k + position + 1)
    return sorted(scores, key=lambda key: -scores[key])
