from dataclasses import dataclass

from finboy.services.ingestion.types import Event
from finboy.services.ledger.categories import category_for


@dataclass(frozen=True)
class Confidence:
    value: float
    factors: dict[str, float | int | None]
    status: str
    review_reason: str | None


def confidence_for(event: Event, *, trusted: bool, source_count: int = 1) -> Confidence:
    # A missing second source is unavailable evidence, not evidence of disagreement.
    # Normalize over applicable weights; a known disagreement receives zero instead.
    factors: dict[str, float | int | None] = {
        "trusted_sender_template": 0.25
        if trusted and event.extractor_id.startswith("rules")
        else 0,
        "deterministic_amount_date": 0.25
        if {"amount_minor", "occurred_at"} <= set(event.rule_fields)
        else 0,
        "unique_reference": 0.20 if event.reference_id else 0,
        "cross_source_agreement": 0.15 if source_count > 1 else None,
        "merchant_category_quality": 0.15
        if event.merchant and category_for(event) != "other"
        else 0,
        "source_count": source_count,
    }
    weight = 1 if source_count > 1 else 0.85
    value = round(
        sum(float(v) for k, v in factors.items() if k != "source_count" and v is not None) / weight,
        3,
    )
    reason = None
    if not event.payment_proof and event.event_type not in {"bill_due", "emi_due", "failed"}:
        reason = "unverified_payment"
    elif not event.merchant or "unknown" in event.merchant.lower() or "[address]" in event.merchant:
        reason = "merchant_uncertain"
    elif category_for(event) == "other":
        reason = "category_uncertain"
    elif value < 0.90:
        reason = "low_confidence"
    return Confidence(value, factors, "needs_review" if reason else "confirmed", reason)
