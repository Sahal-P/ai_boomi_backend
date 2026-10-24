"""Synthetic eligibility regressions: monetary text alone is not a financial event."""

from email.message import EmailMessage

import pytest
from finboy.core.config import Settings
from finboy.services.ingestion import extract
from finboy.services.ingestion.classifier import classify
from finboy.services.ingestion.llm import (
    ExtractionUnavailable,
    LLMEvent,
    LLMResult,
    merge_evidence,
    supported_events,
)
from finboy.services.ingestion.normalize import normalize
from finboy.services.ingestion.rules import extract_rules
from finboy.services.ingestion.types import EventType
from finboy.services.ledger.confidence import confidence_for


def notification(
    body: str,
    *,
    subject: str = "Synthetic notification",
    sender: str = "notify@alerts.hdfcbank.test",
    html: bool = False,
) -> bytes:
    message = EmailMessage()
    message["From"] = sender
    message["Subject"] = subject
    message.set_content(body, subtype="html" if html else "plain")
    return message.as_bytes()


NON_EVENTS = [
    pytest.param(
        "Python developer vacancy. Salary ₹8,50,000 per year. Benefits: paid time off.",
        id="job-paid-time-off",
    ),
    pytest.param(
        "Engineering jobs: salary INR 600000 to INR 900000; paid vacation included.",
        id="salary-range",
    ),
    pytest.param(
        "Hiring a payments engineer. Salary INR 700000 is credited monthly after joining.",
        id="advertised-future-salary-credit",
    ),
    pytest.param(
        "Learn to build payment receipts. Course price INR 799; paid training available.",
        id="advertised-price",
    ),
    pytest.param(
        "Loan calculator example: EMI INR 1000 due 30-10-26. Apply for a personal loan.",
        id="loan-calculator-example",
    ),
    pytest.param(
        "Sample bill INR 1200 due 30-10-26. This example explains how billing works.",
        id="example-bill",
    ),
    pytest.param(
        "Your credit card limit is INR 200000. Available credit INR 90000.",
        id="credit-limit",
    ),
    pytest.param("Available balance INR 9000. No account activity.", id="balance-only"),
    pytest.param(
        "Refund policy: purchases up to INR 799 may qualify. No refund has been issued.",
        id="refund-policy",
    ),
    pytest.param("INR 799 has not been paid. Pay now.", id="negated-paid"),
    pytest.param("OTP for a payment of INR 799. This is not a completed payment.", id="otp"),
    pytest.param(
        "Get INR 500 cashback on your next payment. Limited offer.", id="prospective-cashback"
    ),
    pytest.param("Salary not credited INR 62000 from Synthetic Works.", id="salary-not-credited"),
    pytest.param(
        "Salary INR 62000 will be credited on 30-10-26 from Synthetic Works.",
        id="salary-will-be-credited",
    ),
    pytest.param(
        "Bill amount INR 799 is not due on 30-10-26; Biller: Electricity.",
        id="bill-not-due",
    ),
    pytest.param("Get paid INR 799 for every friend you refer.", id="referral-advert"),
    pytest.param(
        "You are eligible for a refund of INR 799. Submit a request to claim it.",
        id="refund-eligibility",
    ),
    pytest.param("Please send an invoice for INR 799; Merchant: Amazon.", id="invoice-request"),
    pytest.param("Can you issue an invoice for INR 799; Merchant: Amazon?", id="invoice-question"),
    pytest.param(
        "Example notification\nDebited INR 799 to Amazon on 10-10-26; Ref: SYN-799.",
        id="example-heading-before-debit",
    ),
    pytest.param(
        "Developer jobs\nSalary credited INR 70000 every month. Paid time off included.",
        id="jobs-heading-before-recurring-salary",
    ),
]


@pytest.mark.parametrize("body", NON_EVENTS)
@pytest.mark.parametrize("sender", ["jobs@example.test", "notify@alerts.hdfcbank.test"])
def test_monetary_non_events_never_become_rule_events(
    body: str, sender: str, settings: Settings
) -> None:
    raw = notification(body, sender=sender)
    assert not extract_rules(normalize(raw)).events
    assert not extract.prepare(raw, settings, mode="rules").extraction.events


@pytest.mark.parametrize("body", NON_EVENTS)
def test_unavailable_model_cannot_resurrect_advertised_or_example_amounts(
    body: str, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(*args: object, **kwargs: object) -> LLMResult:
        raise ExtractionUnavailable("extraction_unavailable")

    monkeypatch.setattr(extract, "live_extract", unavailable)
    prepared = extract.prepare(notification(body), settings, mode="live")
    assert not prepared.extraction.events
    assert prepared.extraction.not_transaction


REAL_EVENTS = [
    pytest.param("Debited INR 799 to Amazon", "debit", True, id="debit"),
    pytest.param(
        "Paid successfully INR 799 to Amazon", "debit", True, id="settled-merchant-payment"
    ),
    pytest.param("Credited INR 799 from Synthetic Works", "credit", True, id="credit"),
    pytest.param("Salary credited INR 799 from Synthetic Works", "salary", True, id="salary"),
    pytest.param(
        "Salary for May credited INR 799 from Synthetic Works", "salary", True, id="salary-for-may"
    ),
    pytest.param("Debited INR 799 to May Stores", "debit", True, id="merchant-may-stores"),
    pytest.param("Debited INR 799 to Jobs India", "debit", True, id="merchant-jobs-india"),
    pytest.param("Payment failed INR 799 to Amazon", "failed", False, id="failed"),
    pytest.param("Refund credited INR 799 from Amazon", "refund", True, id="refund"),
    pytest.param("Reversed and credited INR 799 from Amazon", "reversal", True, id="reversal"),
    pytest.param(
        "Credit-card bill payment debited INR 799 to Credit Card",
        "transfer",
        True,
        id="card-bill-transfer",
    ),
    pytest.param("SIP debited INR 799 to Synthetic Fund", "investment", True, id="sip"),
    pytest.param(
        "Invoice INR 799; Merchant: Amazon; Order ID: SYN-799",
        "debit",
        False,
        id="issued-invoice",
    ),
    pytest.param(
        "Order confirmation INR 799; Merchant: Amazon; Order ID: SYN-799",
        "debit",
        False,
        id="placed-order",
    ),
    pytest.param(
        "Receipt INR 799; Merchant: Amazon; Order ID: SYN-799",
        "debit",
        False,
        id="receipt-without-settlement",
    ),
    pytest.param(
        "Bill amount INR 799 due 30-10-26; Biller: Electricity",
        "bill_due",
        False,
        id="issued-bill",
    ),
    pytest.param(
        "EMI amount INR 799 due 30-10-26; Biller: Synthetic Loan",
        "emi_due",
        False,
        id="emi-due",
    ),
]

UNRELATED_FOOTERS = [
    pytest.param("", id="no-footer"),
    pytest.param("Special offer: win INR 500 cashback on a future purchase.", id="promo"),
    pytest.param("Careers: developer jobs, paid time off, salary INR 800000.", id="jobs"),
    pytest.param("Refund policy: contact support to request a refund.", id="refund-policy"),
    pytest.param("If a login failed, contact support. Never share an OTP.", id="login-help"),
]


@pytest.mark.parametrize(("claim", "event_type", "payment_proof"), REAL_EVENTS)
@pytest.mark.parametrize("footer", UNRELATED_FOOTERS)
def test_real_notification_survives_unrelated_footer_keywords(
    claim: str,
    event_type: EventType,
    payment_proof: bool,
    footer: str,
    settings: Settings,
) -> None:
    body = f"{claim}; Date: 10-10-26 12:05; Ref: SYN-799; XX1234 via card;\n{footer}"
    raw = notification(body)
    assert classify(normalize(raw)) not in {"non_financial", "promotional"}
    events = extract.prepare(raw, settings, mode="rules").extraction.events
    assert len(events) == 1
    event = events[0]
    assert (event.event_type, event.amount_minor, event.payment_proof) == (
        event_type,
        79900,
        payment_proof,
    )


@pytest.mark.parametrize("sender", ["notify@alerts.hdfcbank.test", "notify@unknown-bank.test"])
@pytest.mark.parametrize("html", [False, True])
def test_real_multiline_notification_does_not_require_a_sender_allowlist(
    sender: str, html: bool, settings: Settings
) -> None:
    body = "Debited\nINR 799\nto Amazon on 10-10-26; UTR: SYN-799; XX1234 via card;"
    if html:
        body = "".join(f"<p>{line}</p>" for line in body.splitlines())
    events = extract.prepare(
        notification(body, sender=sender, html=html), settings, mode="rules"
    ).extraction.events
    assert len(events) == 1
    assert (events[0].event_type, events[0].amount_minor) == ("debit", 79900)


@pytest.mark.parametrize(
    ("subject", "prefix"),
    [
        ("Available balance INR 9000", ""),
        ("Account alert", "Your available balance INR 9000.\n"),
        ("Account alert", "Developer salary INR 800000 per year; paid time off.\n"),
    ],
)
def test_unrelated_earlier_amount_is_never_attached_to_a_real_debit(
    subject: str, prefix: str, settings: Settings
) -> None:
    raw = notification(
        prefix + "Debited INR 799 to Amazon on 10-10-26; UTR: SYN-799; XX1234 via card;",
        subject=subject,
    )
    events = extract.prepare(raw, settings, mode="rules").extraction.events
    # Rejecting an ambiguous message is safer than inventing a larger transaction.
    assert all(event.event_type == "debit" and event.amount_minor == 79900 for event in events)


def model_event(
    event_type: EventType,
    amount_minor: int,
    event_snippet: str,
    amount_snippet: str,
    proof_snippet: str | None = None,
) -> LLMEvent:
    evidence: list[dict[str, str | float]] = [
        {"field": "event_type", "snippet": event_snippet, "confidence": 1.0},
        {"field": "amount_minor", "snippet": amount_snippet, "confidence": 1.0},
    ]
    if proof_snippet:
        evidence.append({"field": "payment_proof", "snippet": proof_snippet, "confidence": 1.0})
    return LLMEvent.model_validate(
        {
            "event_type": event_type,
            "amount_minor": amount_minor,
            "currency": "INR",
            "merchant": None,
            "occurred_at": None,
            "due_date": None,
            "reference_id": None,
            "payment_instrument": None,
            "account_last4": None,
            "category": None,
            "payment_proof": proof_snippet is not None,
            "evidence": evidence,
        }
    )


def test_model_cannot_claim_credit_using_a_debit_quote() -> None:
    message = normalize(notification("Debited INR 799 to Amazon on 10-10-26."))
    result = LLMResult(
        events=[model_event("credit", 79900, "Debited", "INR 799", "Debited")],
        not_transaction=False,
    )
    assert not supported_events(result, message).events


def test_model_cannot_join_salary_amount_to_paid_time_off() -> None:
    message = normalize(
        notification("Developer vacancy. Salary INR 800000 per year. Benefits: paid time off.")
    )
    result = LLMResult(
        events=[model_event("debit", 80000000, "paid time off", "INR 800000")],
        not_transaction=False,
    )
    assert not supported_events(result, message).events


def test_model_cannot_use_available_balance_as_a_debit_amount() -> None:
    message = normalize(
        notification("Available balance INR 9000. Debited INR 799 to Amazon on 10-10-26.")
    )
    result = LLMResult(
        events=[model_event("debit", 900000, "Debited", "INR 9000", "Debited")],
        not_transaction=False,
    )
    assert not supported_events(result, message).events


@pytest.mark.parametrize("claim", ["Order confirmation", "Invoice", "Receipt"])
def test_explicit_model_nontransaction_veto_suppresses_unverified_commerce_claim(
    claim: str,
) -> None:
    message = normalize(
        notification(f"{claim} INR 799; Merchant: Amazon; Order ID: SYN-799; Date: 10-10-26 12:05;")
    )
    rules = extract_rules(message)
    assert len(rules.events) == 1 and not rules.events[0].payment_proof
    model = supported_events(LLMResult(events=[], not_transaction=True), message)
    merged = merge_evidence(rules, model)
    assert not merged.events and merged.not_transaction


def test_independent_settlement_survives_veto_only_with_visible_uncertainty() -> None:
    message = normalize(
        notification("Debited INR 799 to Amazon on 10-10-26 12:05; UTR: SYN-799; XX1234 via card;")
    )
    rules = extract_rules(message)
    assert len(rules.events) == 1
    model = supported_events(LLMResult(events=[], not_transaction=True), message)
    merged = merge_evidence(rules, model)
    assert len(merged.events) == 1
    event = merged.events[0]
    assert (event.event_type, event.amount_minor) == ("debit", 79900)
    confidence = confidence_for(event, trusted=True)
    assert confidence.status == "needs_review"
    assert confidence.value < 0.9
    assert confidence.factors != confidence_for(rules.events[0], trusted=True).factors


def test_model_vetoed_obligation_is_a_conflict_without_a_deductible_event() -> None:
    message = normalize(
        notification(
            "Bill amount INR 799 due 30-10-26; Biller: Electricity; "
            "Date: 10-10-26 12:05; Ref: SYN-BILL; XX1234 via card;"
        )
    )
    rules = extract_rules(message)
    assert len(rules.events) == 1 and rules.events[0].event_type == "bill_due"
    model = supported_events(LLMResult(events=[], not_transaction=True), message)
    merged = merge_evidence(rules, model)
    assert not merged.events
    # A conflicting issued bill needs recovery, not a claim that no bill existed.
    assert not merged.not_transaction


def test_generic_unanchored_debit_does_not_override_explicit_model_veto() -> None:
    message = normalize(notification("Debited INR 799"))
    model = supported_events(LLMResult(events=[], not_transaction=True), message)
    merged = merge_evidence(extract_rules(message), model)
    assert not merged.events
    assert merged.not_transaction


@pytest.mark.parametrize(
    "claim",
    [
        "Your payment of INR 799 has failed",
        "Your payment of INR 799 was unsuccessful",
        "Your transaction of INR 799 failed",
    ],
)
def test_failure_verbs_after_the_amount_do_not_create_spending(
    claim: str, settings: Settings
) -> None:
    events = extract.prepare(
        notification(f"{claim}; Merchant: Amazon; Date: 10-10-26 12:05; Ref: SYN-799;"),
        settings,
        mode="rules",
    ).extraction.events
    assert len(events) == 1
    assert (events[0].event_type, events[0].amount_minor, events[0].payment_proof) == (
        "failed",
        79900,
        False,
    )


@pytest.mark.parametrize("future", ["will be debited", "is scheduled to be debited"])
def test_invoice_with_future_debit_stays_unverified(future: str, settings: Settings) -> None:
    raw = notification(
        "Invoice INR 799; Merchant: Amazon; Invoice ID: SYN-799; Date: 10-10-26 12:05;\n"
        f"Your card {future} INR 799 on 30-10-26."
    )
    events = extract.prepare(raw, settings, mode="rules").extraction.events
    assert len(events) == 1
    assert (events[0].event_type, events[0].amount_minor, events[0].payment_proof) == (
        "debit",
        79900,
        False,
    )


@pytest.mark.parametrize("separator", [", ", "; ", "\n"])
def test_unrelated_invoice_cannot_borrow_another_transactions_proof_or_merchant(
    separator: str, settings: Settings
) -> None:
    raw = notification(
        "Debited INR 100 to Amazon" + separator + "Invoice INR 799 from OtherMerchant"
    )
    events = extract.prepare(raw, settings, mode="rules").extraction.events
    assert len(events) <= 2
    for event in events:
        assert event.event_type == "debit"
        if event.amount_minor == 10000:
            assert event.merchant in {None, "Amazon"}
        else:
            assert event.amount_minor == 79900
            assert event.merchant in {None, "OtherMerchant"}
            assert not event.payment_proof
