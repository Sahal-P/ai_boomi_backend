from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from finboy.core.config import Settings
from finboy.services.ingestion.evaluate import evaluate
from finboy.services.ingestion.types import Event
from finboy.services.ledger.confidence import confidence_for
from finboy.services.ledger.engine import Ledger
from finboy.services.ledger.matching import choose_match


def event(**changes):
    return Event(
        event_type="debit",
        amount_minor=79900,
        merchant="Amazon",
        occurred_at=datetime(2026, 10, 10, 12, tzinfo=ZoneInfo("Asia/Kolkata")),
        reference_id="SYN-799",
        account_last4="1234",
        payment_instrument="card",
        payment_proof=True,
        evidence={"amount_minor": "INR 799", "occurred_at": "10-10-26"},
        rule_fields=["amount_minor", "occurred_at"],
    ).model_copy(update=changes)


def test_rules_oracle():
    result = evaluate(
        rules_only=True,
        settings=Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
            environment="test",
        ),
    )
    assert result["passed"], result


def test_confidence_uses_evidence_not_self_scores():
    item = event()
    before = confidence_for(item, trusted=True)
    item.field_confidence = {"amount_minor": 0, "merchant": 0}
    assert confidence_for(item, trusted=True) == before
    assert before.status == "confirmed"
    assert confidence_for(event(rule_fields=[]), trusted=True).status == "needs_review"
    assert (
        confidence_for(event(payment_proof=False), trusted=True).review_reason
        == "unverified_payment"
    )
    assert (
        confidence_for(event(merchant="Unknown VPA"), trusted=True).review_reason
        == "merchant_uncertain"
    )
    assert confidence_for(item, trusted=False).status == "needs_review"


def test_reference_instrument_merchant_ladder_and_conflicts():
    one = event()
    assert choose_match(event(), [one]).index == 0
    assert choose_match(event(amount_minor=50000), [one]).possible_index == 0
    assert choose_match(event(reference_id=None), [one]).index == 0
    assert choose_match(event(reference_id=None, account_last4=None), [one]).index == 0
    assert choose_match(event(reference_id=None), [one, one]).possible_index == 0
    assert choose_match(event(reference_id="SYN-DIFFERENT"), [one]).index is None
    assert (
        choose_match(
            event(reference_id=None, occurred_at=one.occurred_at + timedelta(days=3)), [one]
        ).index
        is None
    )
    assert choose_match(event(event_type="refund"), [one]).index is None
    assert choose_match(event(event_type="failed"), [one]).index is None


def test_reverse_order_refund_link_and_receipt_dedupe():
    ledger = Ledger()
    ledger.add(
        event(event_type="refund", occurred_at=event().occurred_at + timedelta(days=2)),
        "refund",
        True,
    )
    ledger.add(event(payment_proof=False), "order", True)
    ledger.add(event(), "bank", True)
    assert len(ledger.records) == 2 and ledger.duplicates == 1
    assert ledger.records[0].linked_index == 1
    assert ledger.records[1].confidence.status == "confirmed"
    ledger.add(event(), "bank", True)
    assert ledger.duplicates == 1


def test_disagreement_does_not_raise_confidence_and_separation_allows_exact_reimport():
    ledger = Ledger()
    ledger.add(event(), "bank", True)
    ledger.add(event(merchant="Bookshop"), "receipt", True)
    assert ledger.records[0].confidence.status == "needs_review"
    assert ledger.records[0].confidence.factors["cross_source_agreement"] == 0
    assert choose_match(event(), [event()], excluded={0}).index == 0
    assert choose_match(event(reference_id=None), [event()], excluded={0}).index is None


def test_evaluator_reports_a_direction_error(monkeypatch):
    from finboy.services.ingestion import evaluate as evaluator

    original = evaluator.prepare

    def flipped(*args, **kwargs):
        prepared = original(*args, **kwargs)
        for item in prepared.extraction.events:
            if item.event_type == "salary":
                item.event_type = "debit"
        return prepared

    monkeypatch.setattr(evaluator, "prepare", flipped)
    result = evaluator.evaluate(
        rules_only=True,
        settings=Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test:test@127.0.0.1:1/finboy_test",
            environment="test",
        ),
    )
    assert not result["passed"] and result["direction_errors"] == 1
