"""Checkout, settlement, AutoPay and erasure against the disposable local database."""

import threading
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from finboy.core.config import Settings
from finboy.db.models.billing import BillingPayment, BillingProfile, Subscription
from finboy.main import create_app
from finboy.services.accounts import households
from finboy.services.billing import checkout, mandates, plans
from finboy.services.billing.payu import PayUClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .database import household, local_settings, result
from .support import SALT

pytestmark = pytest.mark.integration


def start(settings: Settings, pg: sessionmaker, user_id: UUID) -> checkout.Started:
    with pg() as session:
        return checkout.start(
            session, settings, user_id, email="someone@example.in", phone="9876543210", via="web"
        )


def test_a_paid_month_counts_once(world) -> None:
    settings, pg = world
    user_id = household(pg, joined_days_ago=40)
    started = start(settings, pg, user_id)
    assert started.fields["amount"] == "299.00" and "hash" in started.fields
    with pg() as session:
        profile = session.get(BillingProfile, user_id)
        assert profile is not None and b"someone@example.in" not in profile.encrypted_email
        payment, reason = checkout.receive(session, settings, result(started.fields["txnid"]))
        assert reason == "settled" and payment is not None and payment.status == "paid"
        first = session.get(Subscription, user_id).paid_through
        assert first is not None and first - datetime.now(UTC) > timedelta(days=27)
        assert plans.plan_for(session, settings, user_id).state == "active"
    with pg() as session:  # the webhook arriving later changes nothing
        checkout.receive(session, settings, result(started.fields["txnid"]))
        assert session.get(Subscription, user_id).paid_through == first


def test_paying_in_the_trial_keeps_every_trial_day(world) -> None:
    settings, pg = world
    user_id = household(pg, joined_days_ago=10)
    started = start(settings, pg, user_id)
    with pg() as session:
        trial_end = plans.plan_for(session, settings, user_id).trial_ends_at
        payment, _ = checkout.receive(session, settings, result(started.fields["txnid"]))
        assert payment.covers_from == trial_end
        assert payment.covers_to == plans.add_month(trial_end)
        plan = plans.plan_for(session, settings, user_id)
        assert plan.state == "trial" and not plan.can_pay(datetime.now(UTC))


def test_outcomes_only_move_forward(world) -> None:
    settings, pg = world
    user_id = household(pg, joined_days_ago=40)
    txnid = start(settings, pg, user_id).fields["txnid"]
    with pg() as session:
        payment, _ = checkout.receive(session, settings, result(txnid, status="pending"))
        assert payment.status == "pending"
        payment, _ = checkout.receive(
            session, settings, result(txnid, status="failure", error="E308")
        )
        assert payment.status == "failed" and payment.error_code == "E308"
        # Someone retrying on PayU's page under the same txnid can still succeed.
        payment, _ = checkout.receive(session, settings, result(txnid))
        assert payment.status == "paid" and payment.error_code is None
        payment, _ = checkout.receive(session, settings, result(txnid, status="failure"))
        assert payment.status == "paid"
    other = start(settings, pg, user_id).fields["txnid"]
    with pg() as session:
        payment, reason = checkout.receive(session, settings, result(other, amount="1.00"))
        assert payment is None and reason == "unknown_txnid"
        assert session.scalar(
            select(BillingPayment.status).where(BillingPayment.txnid == other)
        ) == ("started")


def test_a_return_and_a_webhook_together_settle_once(world) -> None:
    settings, pg = world
    user_id = household(pg, joined_days_ago=40)
    fields = result(start(settings, pg, user_id).fields["txnid"])
    barrier = threading.Barrier(2)

    def deliver() -> None:
        with pg() as session:
            barrier.wait()
            checkout.receive(session, settings, fields)

    threads = [threading.Thread(target=deliver) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    with pg() as session:
        payment = session.scalar(select(BillingPayment).where(BillingPayment.user_id == user_id))
        assert session.get(Subscription, user_id).paid_through == payment.covers_to
        assert payment.covers_to == plans.add_month(payment.covers_from)


def test_autopay_registers_then_turns_off_at_the_bank(world) -> None:
    settings, pg = world
    settings = local_settings(payu_autopay_enabled=True)
    user_id = household(pg, joined_days_ago=40)
    started = start(settings, pg, user_id)
    assert started.fields["si"] == "4" and "si_details" in started.fields
    mandate = "403993715599000001"
    with pg() as session:
        checkout.receive(
            session,
            settings,
            result(started.fields["txnid"], payment_source="sist", mihpayid=mandate),
        )
        subscription = session.get(Subscription, user_id)
        assert subscription.renewal == "autopay" and subscription.mandate_payuid == mandate
        assert subscription.mandate_kind == "upi" and subscription.mandate_seq == 1
        assert subscription.next_charge_on is not None
        assert not plans.plan_for(session, settings, user_id).can_pay(datetime.now(UTC))
        paid_through = subscription.paid_through
    calls: list[str] = []

    def payu(request: httpx.Request) -> httpx.Response:
        calls.append(request.content.decode())
        return httpx.Response(200, json={"status": 1, "action": "MANDATE_REVOKE"})

    with pg() as session:
        client = PayUClient(settings, transport=httpx.MockTransport(payu))
        mandates.turn_off(session, settings, user_id, client)
        subscription = session.get(Subscription, user_id)
        assert subscription.renewal == "off" and subscription.mandate_payuid is None
        assert subscription.paid_through == paid_through  # Premium lasts the paid month
    assert "upi_mandate_revoke" in calls[0]


def test_deleting_an_account_keeps_only_sales_records(world) -> None:
    settings, pg = world
    user_id = household(pg, joined_days_ago=40)
    txnid = start(settings, pg, user_id).fields["txnid"]
    with pg() as session:
        checkout.receive(session, settings, result(txnid))
    with pg() as session:
        households.erase_household(session, user_id)
        session.commit()
        assert session.get(BillingProfile, user_id) is None
        assert session.get(Subscription, user_id) is None
        payment = session.scalar(select(BillingPayment).where(BillingPayment.txnid == txnid))
        assert payment.status == "paid" and payment.amount_minor == 29900


def test_the_whole_web_flow(world) -> None:
    settings, _pg = world
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1:8071") as client:
        session_view = client.get("/api/v1/auth/session").json()
        assert session_view["plan"]["contact"] == {
            "email": None,
            "phone": None,
            "phone_from_whatsapp": False,
        }
        missing = client.post("/api/v1/billing/checkout", json={"email": "someone@example.in"})
        assert missing.status_code == 422 and missing.json()["error"]["code"] == "contact_required"
        started = client.post(
            "/api/v1/billing/checkout", json={"email": "someone@example.in", "phone": "9876543210"}
        ).json()
        assert started["action"] == "https://test.payu.in/_payment"
        assert SALT not in str(started)
        back = client.post(
            "/api/v1/payu/return",
            content=urlencode(result(started["fields"]["txnid"])),
            headers={"content-type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )
        assert back.status_code == 303
        assert back.headers["location"] == (
            f"http://127.0.0.1:3071/plan?payment={started['payment_id']}"
        )
        receipt = client.post("/api/v1/billing/receipt", json={"payment_id": started["payment_id"]})
        assert receipt.json()["status"] == "paid" and receipt.json()["covers_to"] is not None
        plan = client.get("/api/v1/auth/session").json()["plan"]
        assert plan["paid_through"] is not None and plan["premium"] is True
        assert plan["contact"] == {
            "email": "s•••@example.in",
            "phone": "•••• 3210",
            "phone_from_whatsapp": False,
        }
        history = client.get("/api/v1/billing/payments").json()["payments"]
        assert [(row["status"], row["amount_minor"]) for row in history] == [("paid", 29900)]
    app.state.engine.dispose()
