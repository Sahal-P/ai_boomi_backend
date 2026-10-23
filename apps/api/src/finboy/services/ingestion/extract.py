from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from finboy.core.config import Settings
from finboy.services.ingestion.classifier import classify, trusted_domain
from finboy.services.ingestion.llm import (
    LLMResult,
    cassette_extract,
    live_extract,
    merge_evidence,
    record,
    supported_events,
)
from finboy.services.ingestion.normalize import NormalizedMessage, normalize
from finboy.services.ingestion.rules import extract_rules
from finboy.services.ingestion.types import Classification, Extraction


@dataclass(frozen=True)
class Prepared:
    message: NormalizedMessage
    classification: Classification
    extraction: Extraction
    trusted: bool
    llm_result: LLMResult | None = None


def prepare(
    raw: bytes,
    settings: Settings,
    *,
    mode: Literal["rules", "offline", "live"] = "rules",
    received_at: datetime | None = None,
) -> Prepared:
    message = normalize(raw, received_at)
    classification = classify(message)
    if classification in {"promotional", "non_financial"}:
        return Prepared(message, classification, Extraction(not_transaction=True), False)
    rules = extract_rules(message)
    if rules.not_transaction or mode == "rules":
        return Prepared(message, classification, rules, trusted_domain(message.sender_domain))
    result = (
        live_extract(message, settings)
        if mode == "live"
        else cassette_extract(message, settings.openai_extraction_model)
    )
    return Prepared(
        message,
        classification,
        merge_evidence(rules, supported_events(result, message)),
        trusted_domain(message.sender_domain),
        result,
    )


def record_prepared(item: Prepared, model: str) -> None:
    if item.llm_result:
        record(item.message, item.llm_result, model)
