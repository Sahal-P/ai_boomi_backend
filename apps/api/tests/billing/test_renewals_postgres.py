"""The billing timer against the disposable database, with PayU answering through a mock."""

import json
from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs
from uuid import UUID, uuid4

import httpx
import pytest
from finboy.core.clock import IST
from finboy.db.models.billing import BillingPayment, Subscription
from finboy.services.billing import plans, renewals
from finboy.services.billing.payu import PayUClient, new_txnid
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .database import household, local_settings

pytestmark = pytest.mark.integration

MANDATE = "403993715577000001"


class PayU:
    """Answers postservice commands from a script; records what FinBoy asked."""

    def __init__(self, **answers: list[dict]) -> None:
        self.answers = answers
        self.asked: list[tuple[str, dict]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        form = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        command, var1 = form["command"], form["var1"]
        self.asked.append((command, json.loads(var1) if var1.startswith("{") else {"txnids": var1}))
        queue = self.answers.get(command) or [{"status": 0}]
        body = queue.pop(0) if len(queue) > 1 else queue[0]
        if command == "si_transaction" and "details" in body:
            txnid = json.loads(var1)["txnid"]
            body = {"status": 1, "details": {txnid: body["details"]}}
        return httpx.Response(200, json=body)

    def commands(self) -> list[str]:
        return [command for command, _ in self.asked]


def client(payu: PayU) -> PayUClient:
    return PayUClient(local_settings(), transport=httpx.MockTransport(payu))


def autopay_household(pg: sessionmaker, paid_through: datetime) -> UUID:
    user_id = household(pg, joined_days_ago=60)
    with pg() as session:
        session.add(
            Subscription(
                user_id=user_id,
                paid_through=paid_through,
                renewal="autopay",
                mandate_payuid=MANDATE + str(uuid4().int % 1000).zfill(3),
                mandate_kind="upi",
                mandate_seq=1,
                next_charge_on=paid_through.astimezone(IST).date(),
            )
        )
        session.commit()
    return user_id


def ist(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST).astimezone(UTC)


def test_peak_hours_and_the_48_hour_notice() -> None:
    day = date(2027, 1, 10)
    assert renewals.in_peak(ist(day, 10, 0)) and renewals.in_peak(ist(day, 21, 29))
    assert not renewals.in_peak(ist(day, 9, 59)) and not renewals.in_peak(ist(day, 13, 0))
    # Notified at 08:00 on the 7th for the 10th: on time. At 20:00 on the 8th: a day later.
    assert renewals.debit_date(day, ist(date(2027, 1, 7), 8)) == day
    assert renewals.debit_date(day, ist(date(2027, 1, 8), 20)) == date(2027, 1, 11)


def test_an_autopay_month_renews_itself(world) -> None:
    settings, pg = world
    due = date.today() + timedelta(days=30)
    paid_through = ist(due, 9, 30)
    user_id = autopay_household(pg, paid_through)
    payu = PayU(
        upi_mandate_status=[{"status": "active"}],
        pre_debit_SI=[{"status": 1}],
        si_transaction=[{"details": {"status": "captured", "payuid": "88"}}],
    )
    notice_time = ist(due - timedelta(days=3), 8)
    with pg() as session:
        summary = renewals.notify(session, settings, client(payu), notice_time)
        assert summary.notified == 1
        renewal = session.scalar(
            select(BillingPayment).where(
                BillingPayment.user_id == user_id, BillingPayment.kind == "renewal"
            )
        )
        assert renewal.status == "scheduled" and renewal.debit_on == due and renewal.sequence == 2
        # A second run sends no second notice for the same month.
        assert renewals.notify(session, settings, client(payu), notice_time).notified == 0
    notice = dict(payu.asked)["pre_debit_SI"]
    assert notice["debitDate"] == due.isoformat() and notice["mandateSeqNo"] == 2
    assert notice["amount"] == "299.00" and notice["authpayuid"].startswith(MANDATE)
    with pg() as session:
        # Peak hours: nothing is charged; 07:00 on the renewal day: charged.
        assert renewals.charge(session, settings, client(payu), ist(due, 11)).charged == 0
        assert renewals.charge(session, settings, client(payu), ist(due, 7)).charged == 1
        subscription = session.get(Subscription, user_id)
        assert subscription.paid_through == plans.add_month(paid_through)
        assert subscription.next_charge_on == plans.add_month(paid_through).astimezone(IST).date()
        assert subscription.grace_until is None and subscription.renewal == "autopay"
    assert payu.commands() == ["upi_mandate_status", "pre_debit_SI", "si_transaction"]


def test_a_failing_renewal_is_retried_once_then_autopay_stops(world) -> None:
    settings, pg = world
    due = date.today() + timedelta(days=30)
    paid_through = ist(due, 9, 30)
    user_id = autopay_household(pg, paid_through)
    payu = PayU(
        upi_mandate_status=[{"status": "active"}],
        pre_debit_SI=[{"status": 1}],
        si_transaction=[{"details": {"status": "failed", "field9": "Insufficient funds"}}],
        upi_mandate_revoke=[{"status": 1}],
    )
    with pg() as session:
        renewals.notify(session, settings, client(payu), ist(due - timedelta(days=3), 8))
        assert renewals.charge(session, settings, client(payu), ist(due, 7)).failed == 1
        # Premium continues in grace while the retry is announced and charged.
        assert plans.plan_for(session, settings, user_id, ist(due, 12)).state == "grace"
        renewals.notify(session, settings, client(payu), ist(due, 8))
        retry = session.scalars(
            select(BillingPayment).where(
                BillingPayment.user_id == user_id, BillingPayment.status == "scheduled"
            )
        ).one()
        assert retry.attempts == 2 and retry.sequence == 3 and retry.debit_on > due
        later = ist(retry.debit_on, 7)
        assert plans.plan_for(session, settings, user_id, later).state == "grace"
        assert renewals.charge(session, settings, client(payu), later).failed == 1
        assert renewals.notify(session, settings, client(payu), later).ended == 1
        subscription = session.get(Subscription, user_id)
        assert subscription.renewal == "off" and subscription.mandate_payuid is None
        assert plans.plan_for(session, settings, user_id, later).state == "free"
    assert payu.commands()[-1] == "upi_mandate_revoke"


def test_a_mandate_cancelled_from_the_upi_app_stops_renewing(world) -> None:
    settings, pg = world
    due = date.today() + timedelta(days=30)
    user_id = autopay_household(pg, ist(due, 9, 30))
    payu = PayU(upi_mandate_status=[{"status": "revoked"}], upi_mandate_revoke=[{"status": 0}])
    with pg() as session:
        summary = renewals.notify(session, settings, client(payu), ist(due - timedelta(days=3), 8))
        assert summary.ended == 1 and summary.notified == 0
        subscription = session.get(Subscription, user_id)
        assert subscription.renewal == "off" and subscription.paid_through == ist(due, 9, 30)
    assert "pre_debit_SI" not in payu.commands()


def test_paying_by_hand_cancels_an_announced_debit(world) -> None:
    settings, pg = world
    due = date.today() + timedelta(days=30)
    paid_through = ist(due, 9, 30)
    user_id = autopay_household(pg, paid_through)
    payu = PayU(upi_mandate_status=[{"status": "active"}], pre_debit_SI=[{"status": 1}])
    with pg() as session:
        renewals.notify(session, settings, client(payu), ist(due - timedelta(days=3), 8))
        subscription = session.get(Subscription, user_id)
        subscription.paid_through = paid_through + timedelta(days=30)  # paid by hand meanwhile
        session.commit()
        renewals.charge(session, settings, client(payu), ist(due, 7))
        statuses = session.scalars(
            select(BillingPayment.status).where(BillingPayment.user_id == user_id)
        ).all()
    assert statuses == ["abandoned"] and "si_transaction" not in payu.commands()


def test_closed_tabs_still_count_and_stale_checkouts_are_abandoned(world) -> None:
    settings, pg = world
    user_id = household(pg, joined_days_ago=40)
    now = datetime.now(UTC)
    paid_txn, lost_txn = new_txnid(), new_txnid()
    with pg() as session:
        for txnid, age in ((paid_txn, timedelta(minutes=20)), (lost_txn, timedelta(hours=3))):
            session.add(
                BillingPayment(
                    id=uuid4(),
                    user_id=user_id,
                    txnid=txnid,
                    kind="checkout",
                    started_via="web",
                    status="started",
                    amount_minor=29900,
                    created_at=now - age,
                    updated_at=now - age,
                )
            )
        session.commit()
    payu = PayU(
        verify_payment=[
            {
                "status": 1,
                "transaction_details": {
                    paid_txn: {
                        "status": "success",
                        "amt": "299.00",
                        "mihpayid": "77",
                        "mode": "UPI",
                    },
                    lost_txn: {"status": "Not Found", "mihpayid": "Not Found"},
                },
            }
        ]
    )
    with pg() as session:
        summary = renewals.reconcile(session, settings, client(payu), now)
        assert summary.reconciled == 1 and summary.abandoned == 1
        statuses = dict(
            session.execute(
                select(BillingPayment.txnid, BillingPayment.status).where(
                    BillingPayment.user_id == user_id
                )
            ).all()
        )
        assert statuses == {paid_txn: "paid", lost_txn: "abandoned"}
        assert plans.plan_for(session, settings, user_id).state == "active"


def test_one_timer_run_at_a_time(world) -> None:
    settings, pg = world
    payu = PayU()
    with pg() as first, pg() as second:
        from sqlalchemy import text

        assert first.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": renewals.RUN_LOCK})
        assert renewals.run(second, settings, client(payu)) == renewals.Summary()
        first.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": renewals.RUN_LOCK})
        first.commit()
        assert renewals.run(second, settings, client(payu)) == renewals.Summary()
