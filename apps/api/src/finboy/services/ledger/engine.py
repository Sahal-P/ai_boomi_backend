from dataclasses import dataclass, field

from finboy.core.clock import IST
from finboy.services.ingestion.types import Event
from finboy.services.ledger.categories import category_for
from finboy.services.ledger.confidence import Confidence, confidence_for
from finboy.services.ledger.matching import choose_match, claims_agree, direction, original_for


@dataclass
class Canonical:
    event: Event
    trusted: bool
    sources: set[str]
    confidence: Confidence
    category: str
    linked_index: int | None = None
    possible_index: int | None = None
    agreement: bool = True


@dataclass
class Ledger:
    records: list[Canonical] = field(default_factory=list)
    commitments: list[Event] = field(default_factory=list)
    duplicates: int = 0

    def add(self, event: Event, source: str, trusted: bool) -> None:
        if event.event_type in {"bill_due", "emi_due"}:
            if not any(
                (item.reference_id, item.amount_minor, item.due_date)
                == (event.reference_id, event.amount_minor, event.due_date)
                for item in self.commitments
            ):
                self.commitments.append(event)
            return
        events = [record.event for record in self.records]
        match = choose_match(event, events)
        if match.index is not None:
            existing = self.records[match.index]
            if source in existing.sources:
                return
            existing.sources.add(source)
            existing.agreement = existing.agreement and claims_agree(existing.event, event)
            # A settled notification supplies stronger evidence than a receipt.
            if event.payment_proof and not existing.event.payment_proof:
                existing.event = event
                existing.trusted = trusted
            existing.confidence = confidence_for(
                existing.event,
                trusted=existing.trusted,
                source_count=len(existing.sources),
                agreement=existing.agreement,
            )
            self.duplicates += 1
        else:
            confidence = confidence_for(event, trusted=trusted)
            if match.possible_index is not None:
                confidence = Confidence(
                    confidence.value, confidence.factors, "needs_review", "possible_duplicate"
                )
            self.records.append(
                Canonical(
                    event,
                    trusted,
                    {source},
                    confidence,
                    category_for(event),
                    possible_index=match.possible_index,
                )
            )
        # Relink both directions of import order: a refund may arrive before its debit.
        events = [record.event for record in self.records]
        for record in self.records:
            record.linked_index = original_for(record.event, events)

    def commitment_paid(self, event: Event) -> bool:
        candidates = [
            record
            for record in self.records
            if record.event.payment_proof
            and direction(record.event) == "out"
            and record.event.event_type not in {"failed", "transfer"}
            and record.confidence.status == "confirmed"
            and record.event.amount_minor == event.amount_minor
            and record.event.merchant == event.merchant
            and record.event.occurred_at
            and event.due_date
            and abs((record.event.occurred_at.astimezone(IST).date() - event.due_date).days) <= 7
        ]
        return len(candidates) == 1
