"""Apply and Undo on the real schema (migration 0024_record_changes): the correction the
Transactions page uses, payee memory, budgets, the goal and one Undo."""

from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from finboy.core.clock import IST, today_ist
from finboy.core.config import Settings
from finboy.db.models import User
from finboy.db.models.changes import RecordChangeSet
from finboy.db.models.ledger import Transaction, TransactionRevision
from finboy.db.models.mail import AuditEvent
from finboy.db.models.money import Budget, MerchantCategory
from finboy.db.session import build_engine
from finboy.services.accounts.households import remove_household_data
from finboy.services.advisor import changes as record_changes
from finboy.services.advisor.changes import Change
from finboy.services.ledger.reconcile import correct_transaction, set_review_status
from finboy.services.money import budgets, merchants
from finboy.services.money.engine import PeriodSpec, money_summary
from finboy.services.ux.state import TaskError, data_version
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


@pytest.fixture
def session() -> Iterator[Session]:
    settings = Settings()
    url = make_url(settings.database_url.get_secret_value())
    if settings.environment == "production" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Integration tests require a local disposable database")
    engine = build_engine(settings)
    with engine.connect() as connection, connection.begin() as transaction:
        with Session(bind=connection, join_transaction_mode="create_savepoint") as value:
            yield value
        transaction.rollback()
    engine.dispose()


def household(session: Session) -> User:
    user = User(id=uuid4(), display_name="Synthetic changes household")
    session.add(user)
    session.flush()
    return user


def record(
    session: Session,
    user: User,
    name: str,
    amount: int,
    *,
    category: str = "other",
    kind: str = "purchase",
    direction: str = "out",
    locked: list[str] | None = None,
) -> Transaction:
    row = Transaction(
        id=uuid4(),
        user_id=user.id,
        direction=direction,
        kind=kind,
        amount_minor=amount,
        merchant=name,
        category=category,
        occurred_at=datetime.combine(today_ist().replace(day=1), time(12), IST),
        confidence=Decimal("0.950"),
        confidence_factors={},
        status="confirmed",
        fingerprint=uuid4().hex,
        user_locked_fields=locked or [],
    )
    session.add(row)
    session.flush()
    return row


def proposal(session: Session, user: User, changes: list[Change], **values) -> RecordChangeSet:
    found = record_changes.plan(record_changes.load(session, user.id), changes)
    assert found.problems == []
    row = record_changes.propose(
        session,
        user_id=user.id,
        channel="web",
        message_id=None,
        proposal=record_changes.Proposal(changes, found),
    )
    for name, value in values.items():
        setattr(row, name, value)
    session.commit()
    return row


def spending(session: Session, user: User) -> dict[str, int]:
    summary = money_summary(session, user_id=user.id, period=PeriodSpec())
    session.rollback()
    return {item.category: item.amount_minor for item in summary.categories}


CHANGES = [
    Change(type="payee_category", payee="REDBUS", category="travel"),
    Change(type="payee_category", payee="Indian Railways", category="travel"),
    Change(type="own_transfer", payee="SBI self transfer"),
    Change(type="rename_payee", payee="PAYTM*KUMAR", new_name="Kumar Stores"),
    Change(type="budget", category="food_dining", amount_minor=500000),
    Change(type="savings_goal", amount_minor=300000),
]


def ledger(session: Session) -> tuple[User, dict[str, Transaction]]:
    user = household(session)
    rows = {
        "redbus": record(session, user, "REDBUS", 120000),
        "railways": record(session, user, "Indian Railways", 58220),
        "sbi": record(session, user, "SBI self transfer", 2000000, category="transfer"),
        "sbi2": record(session, user, "SBI self transfer", 2450000, category="transfer"),
        "kumar": record(session, user, "PAYTM*KUMAR", 4000, category="groceries"),
        "chosen": record(session, user, "REDBUS", 30000, category="friends", locked=["category"]),
    }
    budgets.set_budget(session, user.id, "food_dining", 400000)
    session.commit()
    return user, rows


def test_apply_sorts_other_leaves_own_transfers_out_of_spending_and_sets_the_month(
    session: Session,
) -> None:
    user, rows = ledger(session)
    before = spending(session, user)
    assert before["other"] == 178220 and before["transfer"] == 4450000
    version = data_version(session, user.id)
    row = proposal(session, user, CHANGES)
    assert row.state == "proposed" and row.summary["count"] == 7 and row.summary["kept"] == 1

    applied = record_changes.apply(session, user_id=user.id, change_set_id=row.id)
    assert (applied.state, applied.count, applied.skipped, applied.remembered) == (
        "applied",
        7,
        0,
        3,
    )
    after = spending(session, user)
    assert "other" not in after and "transfer" not in after  # own transfers are not spending
    assert after["travel"] == 178220 and after["friends"] == 30000  # the household's own choice
    assert applied.data_version != version
    for name in ("redbus", "railways", "sbi", "sbi2", "kumar", "chosen"):
        session.refresh(rows[name])
    assert (rows["redbus"].category, rows["redbus"].user_locked_fields) == ("travel", ["category"])
    assert (rows["sbi"].kind, rows["sbi"].category) == ("transfer", "transfer")
    assert rows["kumar"].merchant == "Kumar Stores" and rows["chosen"].category == "friends"
    reasons = session.scalars(
        select(TransactionRevision.reason).where(
            TransactionRevision.transaction_id == rows["redbus"].id
        )
    ).all()
    assert set(reasons) == {"advisor_change"}
    memory = {
        item.merchant_key: (item.category, item.display_name)
        for item in session.scalars(
            select(MerchantCategory).where(MerchantCategory.user_id == user.id)
        )
    }
    assert memory == {
        "redbus": ("travel", None),
        "indian railways": ("travel", None),
        "paytm*kumar": (None, "Kumar Stores"),
    }
    assert (
        session.scalar(
            select(Budget.limit_minor).where(
                Budget.user_id == user.id, Budget.category == "food_dining"
            )
        )
        == 500000
    )
    assert session.get(User, user.id).monthly_savings_goal_minor == 300000
    assert (
        session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.user_id == user.id, AuditEvent.event_type == "advisor.changes_applied"
            )
        )
        == 1
    )


def test_one_undo_puts_everything_back_including_what_was_remembered(session: Session) -> None:
    user, rows = ledger(session)
    before = spending(session, user)
    row = proposal(session, user, CHANGES)
    record_changes.apply(session, user_id=user.id, change_set_id=row.id)
    undone = record_changes.undo(session, user_id=user.id, change_set_id=row.id)
    assert (undone.state, undone.skipped) == ("undone", 0)
    assert spending(session, user) == before
    for name in ("redbus", "sbi", "kumar"):
        session.refresh(rows[name])
    assert (rows["redbus"].category, rows["redbus"].user_locked_fields) == ("other", [])
    assert (rows["sbi"].kind, rows["sbi"].category) == ("purchase", "transfer")
    assert rows["kumar"].merchant == "PAYTM*KUMAR"
    assert (
        session.scalar(
            select(func.count())
            .select_from(MerchantCategory)
            .where(MerchantCategory.user_id == user.id)
        )
        == 0
    )
    assert (
        session.scalar(
            select(Budget.limit_minor).where(
                Budget.user_id == user.id, Budget.category == "food_dining"
            )
        )
        == 400000
    )
    assert session.get(User, user.id).monthly_savings_goal_minor is None
    assert (
        "change_undone"
        in session.scalars(
            select(TransactionRevision.reason).where(
                TransactionRevision.transaction_id == rows["redbus"].id
            )
        ).all()
    )
    with pytest.raises(TaskError) as refused:
        record_changes.undo(session, user_id=user.id, change_set_id=row.id)
    assert refused.value.code == "changes_closed"  # Undo runs once


def test_undo_leaves_whatever_changed_since(session: Session) -> None:
    user, rows = ledger(session)
    row = proposal(session, user, CHANGES[:2])
    record_changes.apply(session, user_id=user.id, change_set_id=row.id)
    # The household then sets REDBUS itself on the Transactions page.
    correct_transaction(
        session, user_id=user.id, transaction_id=rows["redbus"].id, category="shopping"
    )
    session.commit()
    undone = record_changes.undo(session, user_id=user.id, change_set_id=row.id)
    assert undone.skipped == 1  # only the payment the household set itself since
    session.refresh(rows["redbus"])
    session.refresh(rows["railways"])
    assert (rows["redbus"].category, rows["redbus"].user_locked_fields) == (
        "shopping",
        ["category"],
    )
    assert (rows["railways"].category, rows["railways"].user_locked_fields) == ("other", [])


def test_a_proposal_applies_once_within_its_day_and_its_household(session: Session) -> None:
    user, rows = ledger(session)
    other = household(session)
    row = proposal(session, user, CHANGES[:1])
    with pytest.raises(TaskError) as refused:
        record_changes.undo(session, user_id=user.id, change_set_id=row.id)
    assert refused.value.code == "changes_closed"  # nothing applied yet
    with pytest.raises(TaskError) as refused:
        record_changes.apply(session, user_id=other.id, change_set_id=row.id)
    assert refused.value.code == "not_found"
    record_changes.apply(session, user_id=user.id, change_set_id=row.id)
    for action in (record_changes.apply, record_changes.decline):
        with pytest.raises(TaskError) as refused:
            action(session, user_id=user.id, change_set_id=row.id)
        assert refused.value.code == "changes_closed"
    late = proposal(
        session, user, CHANGES[1:2], expires_at=datetime.now(UTC) - timedelta(minutes=1)
    )
    with pytest.raises(TaskError) as refused:
        record_changes.apply(session, user_id=user.id, change_set_id=late.id)
    assert refused.value.code == "changes_expired"
    session.refresh(late)
    session.refresh(rows["railways"])
    assert late.state == "expired" and rows["railways"].category == "other"


def test_changes_that_no_longer_apply_are_skipped_and_counted(session: Session) -> None:
    user, rows = ledger(session)
    row = proposal(session, user, CHANGES[:2])
    set_review_status(
        session, user_id=user.id, transaction_id=rows["railways"].id, status="rejected"
    )
    session.commit()
    applied = record_changes.apply(session, user_id=user.id, change_set_id=row.id)
    assert (applied.count, applied.skipped) == (1, 1)
    session.refresh(rows["railways"])
    assert (rows["railways"].status, rows["railways"].category) == ("rejected", "other")


def test_the_next_entries_take_the_chosen_name_then_the_new_names_category(
    session: Session,
) -> None:
    user, _rows = ledger(session)
    row = proposal(
        session,
        user,
        [
            Change(type="rename_payee", payee="PAYTM*KUMAR", new_name="Kumar Stores"),
            Change(type="payee_category", payee="PAYTM*KUMAR", category="shopping"),
        ],
    )
    record_changes.apply(session, user_id=user.id, change_set_id=row.id)
    assert merchants.remembered_name(session, user.id, "paytm*kumar") == "Kumar Stores"
    assert merchants.remembered(session, user.id, "PAYTM*KUMAR") == "shopping"
    merchants.learn(session, user.id, "Kumar Stores", "groceries")  # sorted again by its new name
    session.commit()
    assert merchants.remembered(session, user.id, "PAYTM*KUMAR") == "groceries"
    memory = merchants.memory(session, user.id)
    assert (memory.name("PAYTM*KUMAR"), memory.category("PAYTM*KUMAR")) == (
        "Kumar Stores",
        "groceries",
    )
    assert merchants.remembered_name(session, user.id, "Unknown 93") is None


def test_erasure_removes_proposals_and_what_they_kept(session: Session) -> None:
    user, _rows = ledger(session)
    row = proposal(session, user, CHANGES)
    record_changes.apply(session, user_id=user.id, change_set_id=row.id)
    counts = remove_household_data(session, user.id)
    assert counts["record_change_sets"] == 1
    assert (
        session.scalar(
            select(func.count())
            .select_from(RecordChangeSet)
            .where(RecordChangeSet.user_id == user.id)
        )
        == 0
    )
