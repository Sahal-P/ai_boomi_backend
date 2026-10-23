"""Pure matching decisions shared by persistence and the offline evaluator."""

from dataclasses import dataclass
from datetime import timedelta

from finboy.services.ingestion.types import Event
from finboy.services.ledger.categories import normalize_merchant


def direction(event: Event) -> str:
    return "in" if event.event_type in {"credit", "salary", "refund", "reversal"} else "out"


def kind(event: Event) -> str:
    return {"debit": "purchase", "credit": "income_other", "failed": "purchase"}.get(
        event.event_type, event.event_type
    )


def compatible(left: Event, right: Event) -> bool:
    if left.event_type in {"refund", "reversal", "failed"} or right.event_type in {
        "refund",
        "reversal",
        "failed",
    }:
        return left.event_type == right.event_type
    return direction(left) == direction(right) and (
        left.event_type == right.event_type
        or {left.event_type, right.event_type} <= {"debit", "investment", "transfer", "fee"}
    )


@dataclass(frozen=True)
class Match:
    index: int | None = None
    possible_index: int | None = None
    reason: str | None = None


def choose_match(event: Event, existing: list[Event], *, excluded: set[int] | None = None) -> Match:
    indices = [
        i
        for i, item in enumerate(existing)
        if i not in (excluded or set()) and compatible(event, item)
    ]
    refs = [
        i for i in indices if event.reference_id and event.reference_id == existing[i].reference_id
    ]
    exact = [
        i
        for i in refs
        if existing[i].amount_minor == event.amount_minor and existing[i].currency == event.currency
    ]
    if len(exact) == 1:
        return Match(index=exact[0], reason="reference")
    if refs:
        return Match(possible_index=refs[0], reason="conflicting_reference")
    equal = [
        i
        for i in indices
        if existing[i].amount_minor == event.amount_minor
        and existing[i].currency == event.currency
        and event.occurred_at
        and existing[i].occurred_at
    ]
    # Distinct known references describe distinct purchases, even at the same merchant.
    equal = [
        i
        for i in equal
        if not (
            event.reference_id
            and existing[i].reference_id
            and event.reference_id != existing[i].reference_id
        )
    ]
    instrument = [
        i
        for i in equal
        if event.account_last4
        and event.payment_instrument
        and event.account_last4 == existing[i].account_last4
        and event.payment_instrument.lower() == (existing[i].payment_instrument or "").lower()
        and abs(event.occurred_at - existing[i].occurred_at) <= timedelta(minutes=10)
    ]
    if len(instrument) == 1:
        return Match(index=instrument[0], reason="instrument_time")
    merchant = [
        i
        for i in equal
        if event.merchant
        and normalize_merchant(event.merchant).casefold()
        == (normalize_merchant(existing[i].merchant) or "").casefold()
        and abs(event.occurred_at - existing[i].occurred_at) <= timedelta(hours=48)
    ]
    if len(merchant) == 1 and not instrument:
        return Match(index=merchant[0], reason="merchant_time")
    ambiguous = instrument or merchant
    return Match(possible_index=ambiguous[0], reason="ambiguous") if ambiguous else Match()


def original_for(event: Event, existing: list[Event]) -> int | None:
    if event.event_type not in {"refund", "reversal"}:
        return None
    candidates = [
        i
        for i, item in enumerate(existing)
        if direction(item) == "out"
        and item.event_type not in {"failed", "transfer"}
        and item.currency == event.currency
        and item.amount_minor == event.amount_minor
        and event.occurred_at
        and item.occurred_at
        and timedelta(0) <= event.occurred_at - item.occurred_at <= timedelta(days=90)
    ]
    refs = [
        i
        for i in candidates
        if event.reference_id and event.reference_id == existing[i].reference_id
    ]
    if len(refs) == 1:
        return refs[0]
    merchants = [
        i
        for i in candidates
        if event.merchant
        and normalize_merchant(event.merchant) == normalize_merchant(existing[i].merchant)
    ]
    return merchants[0] if len(merchants) == 1 else None
