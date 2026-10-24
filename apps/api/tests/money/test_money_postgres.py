from email import policy
from email.parser import BytesParser
from uuid import uuid4

import pytest
from finboy.db.models.ledger import (
    Commitment,
    EmailSource,
    SourceEvent,
    Transaction,
)
from finboy.db.models.mail import AuditEvent
from finboy.services.ingestion.pipeline import InboundMessage, ingest_messages
from finboy.services.money.engine import PeriodSpec, category_breakdown, money_summary
from finboy.services.money.models import Correction
from finboy.services.money.review import review_transaction
from sqlalchemy import func, select

pytestmark = pytest.mark.integration


def changed_message(message: InboundMessage, provider_id: str, replacements: dict[str, str]):
    parsed = BytesParser(policy=policy.default).parsebytes(message.raw_rfc822)
    body = parsed.get_content()
    for old, new in replacements.items():
        assert old in body
        body = body.replace(old, new)
    parsed.set_content(body, subtype=parsed.get_content_subtype())
    return InboundMessage("eml_upload", provider_id, parsed.as_bytes())


def message_for(api, reference: str) -> InboundMessage:
    for message in api.messages:
        parsed = BytesParser(policy=policy.default).parsebytes(message.raw_rfc822)
        if reference in parsed.get_content():
            return message
    raise AssertionError("Missing synthetic source reference")


def test_real_mailbox_apis_truth_evidence_and_category_correction(mailbox_api):
    api = mailbox_api
    response = api.client.get("/api/v1/transactions")
    assert response.status_code == 200 and isinstance(response.json(), list)
    transactions = response.json()
    assert len(transactions) == 26
    amazon = next(row for row in transactions if row["amount_minor"] == 79900)
    assert amazon["source_count"] == 3 and amazon["source_modes"] == ["eml_upload"]
    assert amazon["version"] != "0"
    arya = next(row for row in transactions if row["merchant"] == "HOTEL ARYA")
    detail = api.client.get(f"/api/v1/transactions/{amazon['id']}").json()
    assert set(detail) == {
        "transaction",
        "sources",
        "confidence_factors",
        "revisions",
        "version",
        "decisions",
    }
    assert len(detail["sources"]) == 3
    assert len({row["email_source_id"] for row in detail["sources"]}) == 3
    assert detail["confidence_factors"]["source_count"] == 3
    assert all(row["extraction_method"] == "rule" for row in detail["sources"])
    assert all(len(value) <= 80 for row in detail["sources"] for value in row["evidence"].values())
    assert all("raw_rfc822" not in row for row in detail["sources"])
    before = api.client.get("/api/v1/money/summary").json()
    assert (
        next(
            row["amount_minor"] for row in before["categories"] if row["category"] == "food_dining"
        )
        == 661000
    )
    correction = api.client.patch(
        f"/api/v1/transactions/{arya['id']}", json={"category": "food_dining"}
    )
    assert correction.status_code == 200
    assert any(
        row["field"] == "category"
        and row["old_value"] == "travel"
        and row["new_value"] == "food_dining"
        for row in correction.json()["revisions"]
    )
    after = api.client.get("/api/v1/money/summary").json()
    assert (
        next(row["amount_minor"] for row in after["categories"] if row["category"] == "food_dining")
        == 786000
    )
    assert (
        after["tracked_income_minor"],
        after["confirmed_outflows_minor"],
        after["upcoming_commitments_minor"],
        after["estimated_unallocated_minor"],
    ) == (6200000, 3742000, 980000, 1478000)
    assert after["pending_review_count"] == 2 and after["pending_review_minor"] == 234000
    assert before["estimated_unallocated_minor"] == after["estimated_unallocated_minor"]
    simulation = api.client.post(
        "/api/v1/money/simulations", json={"monthly_amount_minor": 500000}
    ).json()
    assert simulation["remaining_after_proposal_minor"] == 978000
    assert simulation["warnings"] == ["pending_review_items", "incomplete_coverage"]
    assert (
        sum(row["amount_minor"] for row in api.client.get("/api/v1/money/commitments").json())
        == 980000
    )
    with api.factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(EmailSource)
                .where(EmailSource.user_id == api.user_id)
            )
            == 42
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(SourceEvent)
                .where(SourceEvent.user_id == api.user_id)
            )
            == 36
        )
        assert (
            len(
                list(
                    session.scalars(
                        select(Transaction).where(
                            Transaction.user_id == api.user_id,
                            Transaction.linked_transaction_id.is_not(None),
                        )
                    )
                )
            )
            == 3
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Commitment)
                .where(Commitment.user_id == api.user_id, Commitment.status == "paid")
            )
            == 1
        )
        categories = category_breakdown(
            session, user_id=api.user_id, period=PeriodSpec(), category="food_dining"
        )
        assert categories[0].amount_minor == 786000


def test_filters_order_literal_search_and_missing_user_records(mailbox_api, monkeypatch):
    from finboy.api.v1 import money, transactions

    api = mailbox_api
    query = (
        "/api/v1/transactions?period=month&year=2026&month=10"
        "&category=food_dining&status=confirmed&q=SWIGGY&limit=1"
    )
    first = api.client.get(query)
    assert first.status_code == 200 and len(first.json()) == 1
    assert api.client.get(query).json() == first.json()
    assert api.client.get("/api/v1/transactions?q=%25").json() == []
    assert api.client.get("/api/v1/transactions?period=month&year=2026&month=9").json() == []
    own_id = first.json()[0]["id"]
    monkeypatch.setattr(transactions, "LOCAL_USER_ID", uuid4())
    monkeypatch.setattr(money, "LOCAL_USER_ID", uuid4())
    assert api.client.get("/api/v1/transactions").json() == []
    assert api.client.get("/api/v1/money/summary").json()["tracked_income_minor"] == 0
    assert api.client.get(f"/api/v1/transactions/{own_id}").status_code == 404
    for action in ("confirm", "reject", "keep-separate"):
        assert api.client.post(f"/api/v1/transactions/{own_id}/{action}").status_code == 404
    assert (
        api.client.patch(
            f"/api/v1/transactions/{own_id}", json={"merchant": "New name"}
        ).status_code
        == 404
    )
    assert (
        api.client.post(
            f"/api/v1/transactions/{own_id}/merge", json={"keep_id": str(uuid4())}
        ).status_code
        == 404
    )


def test_corrections_status_locks_and_reimports_preserve_source_claims(mailbox_api):
    api = mailbox_api
    rows = api.client.get("/api/v1/transactions").json()
    arya = next(row for row in rows if row["merchant"] == "HOTEL ARYA")
    review = next(row for row in rows if row["amount_minor"] == 184000)
    unknown = next(
        row for row in rows if row["amount_minor"] == 50000 and row["status"] == "needs_review"
    )
    path = f"/api/v1/transactions/{arya['id']}"
    corrected = api.client.patch(
        path,
        json={"category": "food_dining", "merchant": "Arya restaurant", "amount_minor": 125100},
    )
    assert corrected.status_code == 200
    assert corrected.json()["sources"][0]["amount_minor"] == 125000
    assert corrected.json()["sources"][0]["merchant"] == "HOTEL ARYA"
    assert api.client.post(f"/api/v1/transactions/{review['id']}/confirm").status_code == 200
    assert api.client.post(f"/api/v1/transactions/{unknown['id']}/reject").status_code == 200
    assert api.client.post(f"/api/v1/transactions/{unknown['id']}/confirm").status_code == 409
    again = ingest_messages(
        api.factory, user_id=api.user_id, import_run_id=api.run_id, messages=api.messages
    )
    assert again.transactions_created == 0 and again.events_extracted == 0
    altered = [
        InboundMessage(message.source, "fresh-" + message.provider_message_id, message.raw_rfc822)
        for message in api.messages
    ]
    again = ingest_messages(
        api.factory, user_id=api.user_id, import_run_id=api.run_id, messages=altered
    )
    assert again.failed == 0 and again.transactions_created == 0
    changed = api.client.get(path).json()
    assert changed["transaction"]["amount_minor"] == 125100
    assert changed["transaction"]["merchant"] == "Arya restaurant"
    assert changed["transaction"]["category"] == "food_dining"
    assert (
        api.client.get(f"/api/v1/transactions/{review['id']}").json()["transaction"]["status"]
        == "confirmed"
    )
    assert (
        api.client.get(f"/api/v1/transactions/{unknown['id']}").json()["transaction"]["status"]
        == "rejected"
    )
    with api.factory() as session:
        tx = session.get(Transaction, arya["id"])
        assert set(tx.user_locked_fields) >= {"merchant", "category", "amount_minor"}
        events = list(session.scalars(select(AuditEvent).where(AuditEvent.user_id == api.user_id)))
        assert len(events) == 3
        assert all(set(event.event_metadata) == {"action", "fields"} for event in events)
        assert events[0].event_metadata["fields"] == ["amount_minor", "category", "merchant"]


def test_duplicate_separation_confirmation_and_merge_preserve_evidence(mailbox_api):
    api = mailbox_api
    original = message_for(api, "SYN-AMAZON799")
    conflicting = changed_message(original, "conflicting-notification", {"799.00": "899.00"})
    result = ingest_messages(
        api.factory, user_id=api.user_id, import_run_id=api.run_id, messages=[conflicting]
    )
    assert result.transactions_created == 1
    rows = api.client.get("/api/v1/transactions").json()
    keep = next(row for row in rows if row["amount_minor"] == 79900)
    duplicate = next(row for row in rows if row["amount_minor"] == 89900)
    path = f"/api/v1/transactions/{duplicate['id']}"
    assert duplicate["possible_duplicate_of_id"] == keep["id"]
    separated = api.client.post(path + "/keep-separate")
    assert separated.status_code == 200
    assert separated.json()["transaction"]["status"] == "needs_review"
    assert separated.json()["transaction"]["possible_duplicate_of_id"] is None
    assert (
        api.client.post(path + "/keep-separate").json()["revisions"]
        == separated.json()["revisions"]
    )
    assert api.client.post(path + "/confirm").json()["transaction"]["status"] == "confirmed"
    merged = api.client.post(path + "/merge", json={"keep_id": keep["id"]})
    assert merged.status_code == 200 and merged.json()["transaction"]["status"] == "merged"
    assert api.client.post(path + "/merge", json={"keep_id": keep["id"]}).status_code == 200
    kept_detail = api.client.get(f"/api/v1/transactions/{keep['id']}").json()
    assert len(kept_detail["sources"]) == 4
    assert kept_detail["confidence_factors"]["source_count"] == 4
    assert kept_detail["confidence_factors"]["cross_source_agreement"] == 0
    assert kept_detail["transaction"]["status"] == "confirmed"
    assert any(row["field"] == "source_event_ids" for row in kept_detail["revisions"])
    assert api.client.post(path + "/confirm").status_code == 409
    assert (
        api.client.post(
            f"/api/v1/transactions/{keep['id']}/merge", json={"keep_id": keep["id"]}
        ).status_code
        == 409
    )


def test_merge_redirects_real_refund_and_paid_commitment_links(mailbox_api):
    api = mailbox_api
    original = message_for(api, "SYN-NETFLIX")
    duplicate = changed_message(
        original, "separate-netflix", {"SYN-NETFLIX": "SYN-SEPARATE-NETFLIX"}
    )
    refund = changed_message(
        original, "netflix-refund", {"Debited": "Refund credited", " to ": " from "}
    )
    result = ingest_messages(
        api.factory, user_id=api.user_id, import_run_id=api.run_id, messages=[duplicate, refund]
    )
    assert result.transactions_created == 2 and result.failed == 0
    rows = api.client.get("/api/v1/transactions").json()
    merge = next(
        row for row in rows if row["reference_id"] == "SYN-NETFLIX" and row["direction"] == "out"
    )
    keep = next(row for row in rows if row["reference_id"] == "SYN-SEPARATE-NETFLIX")
    returned = next(
        row for row in rows if row["reference_id"] == "SYN-NETFLIX" and row["kind"] == "refund"
    )
    assert returned["linked_transaction_id"] == merge["id"]
    response = api.client.post(
        f"/api/v1/transactions/{merge['id']}/merge", json={"keep_id": keep["id"]}
    )
    assert response.status_code == 200
    assert (
        api.client.get(f"/api/v1/transactions/{returned['id']}").json()["transaction"][
            "linked_transaction_id"
        ]
        == keep["id"]
    )
    assert len(api.client.get(f"/api/v1/transactions/{keep['id']}").json()["sources"]) == 2
    with api.factory() as session:
        paid = session.scalar(
            select(Commitment).where(Commitment.user_id == api.user_id, Commitment.status == "paid")
        )
        assert str(paid.paid_transaction_id) == keep["id"]


def test_reject_payment_reopens_obligation_and_failed_records_stay_excluded(mailbox_api):
    api = mailbox_api
    with api.factory() as session:
        paid = session.scalar(
            select(Commitment).where(Commitment.user_id == api.user_id, Commitment.status == "paid")
        )
        payment_id, commitment_id = paid.paid_transaction_id, paid.id
    assert api.client.post(f"/api/v1/transactions/{payment_id}/reject").status_code == 200
    with api.factory() as session:
        paid = session.get(Commitment, commitment_id)
        assert paid.status == "upcoming" and paid.paid_transaction_id is None
    failed = api.client.get("/api/v1/transactions?status=failed").json()[0]
    assert api.client.post(f"/api/v1/transactions/{failed['id']}/confirm").status_code == 409
    assert (
        api.client.patch(
            f"/api/v1/transactions/{failed['id']}", json={"amount_minor": 1}
        ).status_code
        == 409
    )


def test_mutation_failure_rolls_back_fields_revisions_and_audit(mailbox_api, monkeypatch):
    from finboy.services.money import review

    api = mailbox_api
    tx = api.client.get("/api/v1/transactions?q=HOTEL%20ARYA").json()[0]
    before = api.client.get(f"/api/v1/transactions/{tx['id']}").json()
    original_detail = review.transaction_detail

    def after_flush_failure(*args, **kwargs):
        raise RuntimeError("private rollback failure content")

    monkeypatch.setattr(review, "transaction_detail", after_flush_failure)
    with api.factory() as session:
        with pytest.raises(RuntimeError):
            review_transaction(
                session,
                user_id=api.user_id,
                transaction_id=tx["id"],
                action="correct",
                correction=Correction(category="food_dining"),
            )
        assert not session.in_transaction()
    monkeypatch.setattr(review, "transaction_detail", original_detail)
    assert api.client.get(f"/api/v1/transactions/{tx['id']}").json() == before
    with api.factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.user_id == api.user_id)
            )
            == 0
        )
        assert (
            money_summary(
                session, user_id=api.user_id, period=PeriodSpec()
            ).confirmed_outflows_minor
            == 3742000
        )
