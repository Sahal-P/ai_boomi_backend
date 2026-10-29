"""Budgets, the savings goal and merchant memory through the real API and PostgreSQL
(docs/money-manager-round/contract.md)."""

import pytest
from finboy.core.clock import today_ist
from finboy.db.models.core import User
from finboy.db.models.money import Budget, MerchantCategory
from sqlalchemy import select

from .test_entries_postgres import signed_in

pytestmark = pytest.mark.integration
ORIGIN: dict[str, str] = {}  # development TestClient: no Origin, like a same-origin call


def spend(browser, amount: int, category: str, counterparty: str = "Milkman") -> str:
    saved = browser.post(
        "/api/v1/entries",
        json={
            "kind": "spent",
            "amount_minor": amount,
            "counterparty": counterparty,
            "category": category,
            "day": today_ist().isoformat(),
        },
    )
    assert saved.status_code == 200
    return saved.json()["transaction_id"]


def test_budgets_and_the_goal_follow_confirmed_spending(world) -> None:
    browser, phone = signed_in(world)
    _, pg, _ = world
    try:
        empty = browser.get("/api/v1/money/budgets").json()
        assert empty["items"] == [] and empty["goal_minor"] is None
        assert "total" in empty["categories"] and "salary" not in empty["categories"]

        set_food = browser.patch(
            "/api/v1/money/budgets",
            json={"category": "food_dining", "limit_minor": 100000},
            headers=ORIGIN,
        )
        assert set_food.status_code == 200
        spend(browser, 85000, "food_dining")
        plan = browser.get("/api/v1/money/budgets").json()
        assert plan["items"] == [
            {
                "category": "food_dining",
                "limit_minor": 100000,
                "spent_minor": 85000,
                "level": "near",
            }
        ]
        spend(browser, 30000, "food_dining")
        (item,) = browser.get("/api/v1/money/budgets").json()["items"]
        assert (item["spent_minor"], item["level"]) == (115000, "over")

        goal = browser.patch("/api/v1/money/goal", json={"goal_minor": 500000}, headers=ORIGIN)
        assert goal.status_code == 200 and goal.json()["goal_minor"] == 500000
        assert goal.json()["saved_minor"] == -115000  # no income recorded yet

        for bad in (
            {"category": "salary", "limit_minor": 100},  # income has no budget
            {"category": "food_dining", "limit_minor": 0},
            {"category": "food_dining", "limit_minor": 10**9 + 1},
            {"category": "food_dining"},
        ):
            refused = browser.patch("/api/v1/money/budgets", json=bad, headers=ORIGIN)
            assert refused.status_code == 422, bad
        foreign = browser.patch(
            "/api/v1/money/goal", json={"goal_minor": 1}, headers={"Origin": "https://evil.test"}
        )
        assert foreign.status_code == 403

        removed = browser.patch(
            "/api/v1/money/budgets",
            json={"category": "food_dining", "limit_minor": None},
            headers=ORIGIN,
        )
        assert removed.json()["items"] == []
    finally:
        browser.__exit__(None, None, None)
    with pg() as session:
        user = session.get(User, phone.household())
        assert user.monthly_savings_goal_minor == 500000


def test_a_category_change_on_the_web_is_remembered_for_the_payee(world) -> None:
    browser, phone = signed_in(world)
    _, pg, _ = world
    try:
        record = spend(browser, 50000, "other", counterparty="Ravi Stores")
        version = browser.get("/api/v1/money/summary").json()["data_version"]
        changed = browser.post(
            f"/api/v1/transactions/{record}/decisions",
            json={
                "action": "correct",
                "correction": {"category": "groceries"},
                "expected_version": version,
            },
            headers=ORIGIN,
        )
        assert changed.status_code == 200
        preview = browser.post("/api/v1/entries/preview", json={"text": "Paid Ravi Stores 300"})
        assert preview.status_code == 200
    finally:
        browser.__exit__(None, None, None)
    with pg() as session:
        remembered = session.scalars(
            select(MerchantCategory).where(MerchantCategory.user_id == phone.household())
        ).one()
        assert (remembered.merchant_key, remembered.category) == ("ravi stores", "groceries")


def test_deleting_the_account_removes_budgets_goal_and_memory(world) -> None:
    browser, phone = signed_in(world)
    _, pg, _ = world
    household = phone.household()
    try:
        browser.patch(
            "/api/v1/money/budgets", json={"category": "total", "limit_minor": 100}, headers=ORIGIN
        )
        browser.patch("/api/v1/money/goal", json={"goal_minor": 100}, headers=ORIGIN)
        with pg() as session:
            session.add(MerchantCategory(user_id=household, merchant_key="x", category="rent"))
            session.commit()
        assert browser.post("/api/v1/account/delete", json={"confirm": "DELETE"}).status_code == 200
    finally:
        browser.__exit__(None, None, None)
    with pg() as session:
        assert not session.scalars(select(Budget).where(Budget.user_id == household)).all()
        assert not session.scalars(
            select(MerchantCategory).where(MerchantCategory.user_id == household)
        ).all()
        assert session.get(User, household).monthly_savings_goal_minor is None
