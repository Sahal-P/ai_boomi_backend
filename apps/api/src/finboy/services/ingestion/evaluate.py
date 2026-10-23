"""Compare the shared extraction/reconciliation engine to an independent fixture oracle."""

import argparse
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from finboy.core.config import Settings
from finboy.services.ingestion.extract import prepare, record_prepared
from finboy.services.ingestion.normalize import minimize
from finboy.services.ingestion.render_demo_mailbox import FIXTURES, MAILBOX
from finboy.services.ledger.categories import normalize_merchant
from finboy.services.ledger.engine import Ledger
from finboy.services.ledger.matching import direction, kind


def evaluate(
    *, live: bool = False, rules_only: bool = False, settings: Settings | None = None
) -> dict[str, object]:
    settings = settings or Settings()
    if not settings.openai_extraction_model and not rules_only:
        manifest = json.loads((FIXTURES / "llm_cassettes" / "manifest.json").read_text())
        settings = settings.model_copy(update={"openai_extraction_model": manifest["model"]})
    oracle = json.loads((MAILBOX / "expected_ledger.json").read_text())
    paths = sorted(MAILBOX.glob("*.eml"))
    mode = "live" if live else "rules" if rules_only else "offline"
    with ThreadPoolExecutor(max_workers=4) as pool:
        prepared = list(
            pool.map(lambda path: prepare(path.read_bytes(), settings, mode=mode), paths)
        )
    ledger = Ledger()
    for path, item in zip(paths, prepared, strict=True):
        if live:
            record_prepared(item, settings.openai_extraction_model)
        for event in item.extraction.events:
            ledger.add(event, path.name, item.trusted)
    expected = oracle["transactions"]
    actual = ledger.records
    errors: list[str] = []
    amount_errors = direction_errors = 0
    matched: set[int] = set()
    for wanted in expected:
        candidates = [
            i
            for i, record in enumerate(actual)
            if record.event.reference_id == wanted["reference_id"]
            and record.event.event_type == wanted["event_type"]
        ]
        if not candidates:
            # Diagnose direction/type errors instead of only reporting a missing identity.
            candidates = [
                i
                for i, record in enumerate(actual)
                if i not in matched and record.event.reference_id == wanted["reference_id"]
            ]
            if len(candidates) == 1:
                errors.append("event_type")
        if len(candidates) != 1:
            errors.append("canonical_identity")
            continue
        index = candidates[0]
        matched.add(index)
        record = actual[index]
        amount_errors += record.event.amount_minor != wanted["amount_minor"]
        direction_errors += direction(record.event) != wanted["direction"]
        status = "failed" if record.event.event_type == "failed" else record.confidence.status
        if (
            status != wanted["status"]
            or record.confidence.review_reason != wanted["review_reason"]
            and status != "failed"
        ):
            errors.append("status_or_review_reason")
        if len(record.sources) != wanted["source_count"]:
            errors.append("source_count")
        if record.category != wanted["category"]:
            errors.append("category")
        if normalize_merchant(record.event.merchant) != normalize_merchant(
            minimize(wanted["merchant"])
        ):
            errors.append("merchant")
        if (
            not record.event.occurred_at
            or record.event.occurred_at.isoformat() != wanted["occurred_at"]
        ):
            errors.append("occurred_at")
        link = record.linked_index
        linked_ref = next(
            (row["reference_id"] for row in expected if row["id"] == wanted["linked_to"]), None
        )
        if (actual[link].event.reference_id if link is not None else None) != linked_ref:
            errors.append("refund_link")
    confirmed = [
        record
        for record in actual
        if record.confidence.status == "confirmed" and record.event.event_type != "failed"
    ]
    income = sum(
        record.event.amount_minor
        for record in confirmed
        if kind(record.event) in {"salary", "income_other"}
    )
    direction_totals = {
        value: sum(
            record.event.amount_minor for record in confirmed if direction(record.event) == value
        )
        for value in ("in", "out")
    }
    categories: dict[str, int] = defaultdict(int)
    for record in confirmed:
        event = record.event
        if kind(event) in {"salary", "income_other", "transfer"}:
            continue
        # Simulate the explicit demo correction without baking it into extraction.
        category = (
            "food_dining" if normalize_merchant(event.merchant) == "HOTEL ARYA" else record.category
        )
        categories[category] += event.amount_minor * (-1 if direction(event) == "in" else 1)
    categories = {key: value for key, value in categories.items() if value}
    upcoming = sum(
        event.amount_minor
        for event in ledger.commitments
        if not ledger.commitment_paid(event)
        and event.due_date
        and oracle["anchor"] <= event.due_date.isoformat()
    )
    false = len(actual) - len(matched)
    review = sum(
        record.confidence.status == "needs_review"
        for record in actual
        if record.event.event_type != "failed"
    )
    linked = sum(record.linked_index is not None for record in actual)
    for wanted in oracle["commitments"]:
        found = [
            event
            for event in ledger.commitments
            if event.amount_minor == wanted["amount_minor"]
            and event.merchant == wanted["merchant"]
            and event.due_date
            and event.due_date.isoformat() == wanted["due_date"]
        ]
        if (
            len(found) != 1
            or ("paid" if found and ledger.commitment_paid(found[0]) else "upcoming")
            != wanted["status"]
        ):
            errors.append("commitment_identity_or_status")
    if len(ledger.commitments) != len(oracle["commitments"]):
        errors.append("commitment_count")
    # Independently verify the uncorrected demo category, then the user's correction.
    before_food = sum(
        record.event.amount_minor for record in confirmed if record.category == "food_dining"
    )
    if before_food != 661000:
        errors.append("before_correction_food")
    metrics = {
        "mode": mode,
        "model": getattr(settings, "openai_extraction_model", None),
        "messages": len(paths),
        "canonical_count": len(actual),
        "expected_canonical_count": len(expected),
        "income_minor": income,
        "confirmed_totals_by_direction_minor": direction_totals,
        "outflows_minor": sum(categories.values()),
        "categories_after_correction": dict(categories),
        "upcoming_minor": upcoming,
        "before_correction_food_minor": before_food,
        "duplicates_merged": ledger.duplicates,
        "refunds_linked": linked,
        "review_items": review,
        "false_transactions": false,
        "amount_errors": amount_errors,
        "direction_errors": direction_errors,
        "errors": errors,
    }
    for key in (
        "income_minor",
        "outflows_minor",
        "categories_after_correction",
        "upcoming_minor",
        "duplicates_merged",
        "refunds_linked",
        "review_items",
    ):
        if metrics[key] != oracle[key]:
            errors.append(key)
    metrics["passed"] = (
        not errors
        and not amount_errors
        and not direction_errors
        and not false
        and len(actual) == len(expected)
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Call OpenAI and record actual structured responses"
    )
    parser.add_argument("--rules-only", action="store_true")
    args = parser.parse_args()
    result = evaluate(live=args.live, rules_only=args.rules_only)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
