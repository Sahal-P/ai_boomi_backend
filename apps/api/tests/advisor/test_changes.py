"""Changes Ask proposes (docs/advisor-edits-round/contract.md): checked by code, shown as lines,
applied only on a tap. These tests need no database: plans are pure over a ledger."""

import json
import logging
from datetime import date
from uuid import UUID, uuid4

import pytest
from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.advisor import AdvisorMessage
from finboy.db.models.changes import RecordChangeSet
from finboy.services.advisor import changes, tools
from finboy.services.advisor.changes import Change, Ledger, Row
from finboy.services.assistant.models import ChangeGroup, ChangeSetView
from finboy.services.whatsapp import english, hindi, malayalam
from finboy.services.whatsapp.pilot import changes_text
from sqlalchemy import select

from .support import FixtureToolbox, ask, call, make_settings, reply

TODAY = date(2026, 11, 23)


def row(name: str, amount: int, *, category: str = "other", **values) -> Row:
    fields = {"direction": "out", "kind": "purchase", "locked": frozenset()} | values
    return Row(uuid4(), merchant=name, category=category, amount_minor=amount, **fields)


def ledger(*rows: Row, **values) -> Ledger:
    return Ledger(rows={item.id: item for item in rows}, **values)


def test_a_payee_moves_together_and_payments_the_household_set_stay() -> None:
    first, second = row("REDBUS", 120000), row("redbus ", 30000)
    mine = row("REDBUS", 5000, category="friends", locked=frozenset({"category"}))
    moved = row("Self", 9000, kind="transfer", category="transfer")  # never re-sorted as spending
    found = changes.plan(
        ledger(first, second, mine, moved),
        [Change(type="payee_category", payee="RedBus", category="travel")],
    )
    assert found.problems == [] and set(found.updates) == {first.id, second.id}
    assert found.updates[first.id] == {"category": "travel"} and found.kept == 1
    assert found.payees == {"redbus": {"category": "travel"}} and found.count == 2
    [group] = found.groups
    assert (group.kind, group.category, group.payments, group.amount_minor) == (
        "category",
        "travel",
        2,
        150000,
    )
    assert group.names == ["REDBUS"]  # one payee, in its first spelling


def test_own_transfers_leave_spending_unless_the_household_chose_otherwise() -> None:
    sent = row("SBI self transfer", 2000000, category="transfer")
    again = row("SBI self transfer", 2450000, category="transfer")
    rent = row("SBI self transfer", 900000, category="rent", locked=frozenset({"category"}))
    back = row("SBI self transfer", 100000, direction="in", kind="income_other", category="other")
    found = changes.plan(
        ledger(sent, again, rent, back), [Change(type="own_transfer", payee="SBI self transfer")]
    )
    assert found.updates == {
        sent.id: {"kind": "transfer"},
        again.id: {"kind": "transfer"},
    }  # money received stays; the rent the household chose stays
    assert found.kept == 1 and found.payees == {}
    [group] = found.groups
    assert (group.kind, group.payments, group.amount_minor) == ("own_transfer", 2, 4450000)


def test_a_change_to_one_payment_replaces_its_payees_change() -> None:
    gift, order = row("Amazon", 250000), row("Amazon", 80000)
    found = changes.plan(
        ledger(gift, order),
        [
            Change(type="payee_category", payee="Amazon", category="shopping"),
            Change(type="record_category", record_id=gift.id, category="family_events"),
        ],
    )
    assert found.updates == {
        gift.id: {"category": "family_events"},
        order.id: {"category": "shopping"},
    }
    assert [group.category for group in found.groups] == ["family_events", "shopping"]


def test_a_payment_marked_as_an_own_transfer_by_mistake_counts_again() -> None:
    wrong = row("Ravi", 500000, kind="transfer", category="transfer")
    found = changes.plan(
        ledger(wrong), [Change(type="record_category", record_id=wrong.id, category="rent")]
    )
    assert found.updates == {wrong.id: {"category": "rent", "kind": "purchase"}}
    received = row("Acme", 3000000, direction="in", kind="transfer", category="transfer")
    found = changes.plan(
        ledger(received),
        [Change(type="record_category", record_id=received.id, category="salary")],
    )
    assert found.updates == {received.id: {"category": "salary", "kind": "salary"}}
    found = changes.plan(
        ledger(received),
        [Change(type="record_category", record_id=received.id, category="groceries")],
    )
    assert found.updates == {} and "does not fit money received" in found.problems[0]


def test_renames_cover_both_directions_and_are_remembered() -> None:
    paid = row("PAYTM*KUMAR", 4000, category="groceries")
    back = row("paytm*kumar", 1000, direction="in", kind="refund", category="groceries")
    found = changes.plan(
        ledger(paid, back),
        [
            Change(type="rename_payee", payee="PAYTM*KUMAR", new_name="Kumar Stores"),
            Change(type="payee_category", payee="PAYTM*KUMAR", category="groceries"),
        ],
    )
    assert found.updates == {
        paid.id: {"merchant": "Kumar Stores"},
        back.id: {"merchant": "Kumar Stores"},
    }
    assert found.payees == {
        "paytm*kumar": {"display_name": "Kumar Stores", "category": "groceries"}
    }
    [group] = found.groups
    assert (group.kind, group.new_name, group.names, group.payments) == (
        "rename",
        "Kumar Stores",
        ["PAYTM*KUMAR"],
        2,
    )


@pytest.mark.parametrize("payee", ["Unknown 93", "Paid to [phone]"])
def test_unknown_and_hidden_names_change_only_one_payment_at_a_time(payee: str) -> None:
    item = row(payee, 50000)
    found = changes.plan(ledger(item), [Change(type="rename_payee", payee=payee, new_name="Milk")])
    assert found.updates == {} and "one by one" in found.problems[0]
    found = changes.plan(
        ledger(item), [Change(type="rename_payee", record_id=item.id, new_name="Milkman")]
    )
    assert found.updates == {item.id: {"merchant": "Milkman"}} and found.payees == {}


def test_problems_come_back_for_the_model_to_fix() -> None:
    item = row("Swiggy", 45000, category="food_dining")
    found = changes.plan(
        ledger(item, budgets={"food_dining": 500000}, goal=300000),
        [
            Change(type="payee_category", payee="Zomato", category="food_dining"),
            Change(type="payee_category", payee="Swiggy", category="salary"),
            Change(type="record_category", record_id=uuid4(), category="travel"),
            Change(type="budget", category="food_dining", amount_minor=500000),  # already so
            Change(type="budget", category="salary", amount_minor=100000),
            Change(type="savings_goal", amount_minor=300000),  # already so
            Change(type="savings_goal", amount_minor=10**10),
        ],
    )
    assert found.count == 0 and len(found.problems) == 5
    assert 'no payments to "Zomato"' in found.problems[0]
    assert "not a spending category" in found.problems[1]
    found = changes.plan(
        ledger(item),
        [
            Change(type="payee_category", payee="Swiggy", category="groceries"),
            Change(type="payee_category", payee="swiggy", category="shopping"),
        ],
    )
    assert any("disagree" in problem for problem in found.problems)


def test_budgets_and_the_goal_show_before_and_after() -> None:
    found = changes.plan(
        ledger(budgets={"food_dining": 400000}, goal=None),
        [
            Change(type="budget", category="food_dining", amount_minor=500000),
            Change(type="budget", category="total", amount_minor=2000000),
            Change(type="savings_goal", amount_minor=300000),
        ],
    )
    assert found.budgets == {"food_dining": 500000, "total": 2000000} and found.goal == [300000]
    lines = [changes.line(group, english) for group in found.groups]
    assert lines == [
        "Food & dining budget · ₹4,000 a month → ₹5,000 a month",
        "All spending budget · ₹20,000 a month",
        "Savings goal · ₹3,000 a month",
    ]
    removed = changes.plan(
        ledger(budgets={"food_dining": 400000}),
        [Change(type="budget", category="food_dining", amount_minor=None)],
    )
    assert (
        changes.line(removed.groups[0], english)
        == "Food & dining budget · ₹4,000 a month → removed"
    )


def test_lines_read_in_each_language() -> None:
    group = ChangeGroup(
        kind="category",
        category="travel",
        names=["REDBUS", "Indian Railways"],
        payments=2,
        amount_minor=178220,
    )
    assert (
        changes.line(group, english) == "Travel · REDBUS, Indian Railways · 2 payments · ₹1,782.20"
    )
    assert changes.line(group, hindi).endswith("· 2 भुगतान · ₹1,782.20")
    assert changes.line(group, malayalam).endswith("· 2 പേയ്മെന്റുകൾ · ₹1,782.20")
    own = ChangeGroup(
        kind="own_transfer", names=["SBI"], more_names=2, payments=1, amount_minor=500
    )
    assert changes.line(own, english) == "Own account, not spending · SBI +2 · 1 payment · ₹5"


@pytest.mark.parametrize("words", [english, hindi, malayalam])
def test_the_whatsapp_card_fits_and_points_to_the_web_for_the_rest(words) -> None:
    groups = [
        ChangeGroup(
            kind="category",
            category="shopping",
            names=[f"A very long payee name number {index}" for index in range(3)],
            more_names=4,
            payments=12,
            amount_minor=12345678,
        )
        for _ in range(80)
    ]
    view = ChangeSetView(
        id=uuid4(),
        state="proposed",
        count=80,
        groups=groups,
        kept=3,
        expires_at="2026-11-24T00:00:00Z",
    )
    text = changes_text(view, words)
    assert len(text) <= 1024
    more = words.CHANGES_MORE.split("{count}")[1]
    assert more in text and text.endswith(words.CHANGES_ASK)
    small = view.model_copy(update={"groups": groups[:2], "kept": 0})
    assert more not in changes_text(small, words)
    for title in (words.APPLY.format(count=80), words.NOT_NOW, words.UNDO):
        assert len(title) <= 20


# The tool: what code checks before the records, and what the model is told.


def period(kind: str) -> dict:
    return {
        "kind": kind,
        "year": None,
        "month": None,
        "start_date": None,
        "end_date": None,
        "months": None,
    }


def change(**values) -> dict:
    fields = {
        "type": "payee_category",
        "payee": None,
        "ref": None,
        "category": None,
        "new_name": None,
        "monthly_rupees": None,
        "remove": None,
    }
    return fields | values


def propose(box: FixtureToolbox, ctx: tools.Context, *items: dict) -> dict:
    result = tools.run(box, "propose_changes", json.dumps({"changes": list(items)}), ctx)
    return json.loads(result.output)


def test_the_tool_checks_types_refs_categories_and_amounts() -> None:
    box, ctx = FixtureToolbox(), tools.Context(today=TODAY, said={500000})
    refused = propose(
        box,
        ctx,
        change(type="record_category", payee="REDBUS", category="travel"),
        change(type="payee_category", ref="p9", category="travel"),
        change(payee="SBI self transfer", category="transfer"),
        change(type="budget", category="food_dining", monthly_rupees=4000),
        change(type="rename_payee", payee="REDBUS", new_name="Unknown"),
    )
    error = refused["error"]
    assert error.startswith("Nothing was proposed") and ctx.proposal is None
    for part in ("change 1", "change 2", "own_transfer", "amount the person said", "change 5"):
        assert part in error
    ok = propose(
        box,
        ctx,
        change(payee="REDBUS", category="travel"),
        change(payee="Indian Railways", category="travel"),
        change(type="own_transfer", payee="SBI self transfer"),
        change(type="budget", category="food_dining", monthly_rupees=5000),
    )
    assert ok["proposed"] == 4 and ctx.proposal is not None
    assert ok["shown_to_them"] == [
        "Travel · REDBUS, Indian Railways · 2 payments · ₹1,782.20",
        "Own account, not spending · SBI self transfer · 2 payments · ₹4,450",
    ]
    assert "never say it is done" in ok["note"] and box.reads[-1] == "plan_changes"


def test_refs_come_from_find_payments_in_this_answer_and_page_on() -> None:
    box, ctx = FixtureToolbox(), tools.Context(today=TODAY)
    arguments = {
        "period": period("this_month"),
        "payee": None,
        "category": "other",
        "direction": "out",
        "limit": 2,
        "offset": 0,
    }
    first = json.loads(tools.run(box, "find_payments", json.dumps(arguments), ctx).output)
    assert [item["ref"] for item in first["listed"]] == ["p1", "p2"] and first["remaining"] == 2
    second = json.loads(
        tools.run(box, "find_payments", json.dumps(arguments | {"offset": 2}), ctx).output
    )
    assert [item["ref"] for item in second["listed"]] == ["p3", "p4"] and second["remaining"] == 0
    again = json.loads(tools.run(box, "find_payments", json.dumps(arguments), ctx).output)
    assert [item["ref"] for item in again["listed"]] == ["p1", "p2"]  # stable within the answer
    unknown = next(item["ref"] for item in second["listed"] if item["payee"] == "Unknown 93")
    ok = propose(box, ctx, change(type="rename_payee", ref=unknown, new_name="Milkman"))
    assert ok["shown_to_them"] == ["New name: Milkman · Unknown 93 · 1 payment"]
    assert isinstance(ctx.refs["p1"], UUID)


def test_other_payees_and_the_spending_review_come_from_code() -> None:
    box, ctx = FixtureToolbox(), tools.Context(today=TODAY)
    other = json.loads(
        tools.run(box, "other_payees", json.dumps({"period": period("this_month")}), ctx).output
    )
    assert [item["payee"] for item in other["payees"]] == [
        "REDBUS",
        "Indian Railways",
        "Apollo Pharmacy",
    ]
    assert other["unknown_or_hidden_names"]["payments"] == 1
    assert other["categorised_transfer_still_counted_as_spending"]["total"] == "₹4,450"
    review = json.loads(tools.run(box, "spending_review", json.dumps({"period": None}), ctx).output)
    assert review["own_account_moves_not_spending"] == {"amount": "₹15,000", "payments": 1}
    assert review["categorised_transfer_still_counted"]["amount"] == "₹4,450"
    assert review["other_not_sorted"]["payments"] == 4 and review["months_averaged"] == 3
    flexible = {item["category"]: item for item in review["flexible_spending"]}
    assert set(flexible) == {"food_dining", "groceries"}
    assert flexible["food_dining"]["usual_per_month"] == "₹3,000"
    assert (
        flexible["food_dining"]["change"] == "up ₹1,200" and box.reads.count("money_summary") == 4
    )
    refused = json.loads(
        tools.run(box, "spending_review", json.dumps({"period": period("this_week")}), ctx).output
    )
    assert "one month" in refused["error"]


def test_proposals_are_offered_only_while_edits_are_released() -> None:
    off = make_settings()
    assert "propose_changes" not in [tool.name for tool in tools.offered(off)]
    on = off.model_copy(update={"advisor_edits_enabled": True})
    assert "propose_changes" in [tool.name for tool in tools.offered(on)]
    box, ctx = FixtureToolbox(), tools.Context(today=TODAY)
    result = tools.run(box, "propose_changes", json.dumps({"changes": []}), ctx, off)
    assert json.loads(result.output) == {"error": "unknown tool"}


# The advisor keeps a proposal with the answer that offered it.


def test_an_answer_keeps_its_proposal_for_the_tap(session, settings, toolbox, scripted, caplog):
    settings = settings.model_copy(update={"advisor_edits_enabled": True})
    scripted(
        [call("other_payees", {"period": period("this_month")})],
        [
            call(
                "propose_changes",
                {
                    "changes": [
                        change(payee="REDBUS", category="travel"),
                        change(payee="Indian Railways", category="travel"),
                    ]
                },
                "call_2",
            )
        ],
        reply(
            "I can move REDBUS and Indian Railways to travel: 2 payments, ₹1,782.20. "
            "Nothing changes until you tap Apply.",
        ),
    )
    with caplog.at_level(logging.INFO):
        answer = ask(session, settings, toolbox, "Categorise my Other payments")
    proposed = answer.change_set
    assert proposed is not None and proposed.state == "proposed" and proposed.count == 2
    assert proposed.groups[0].names == ["REDBUS", "Indian Railways"]
    row = session.scalar(select(RecordChangeSet))
    assert row is not None and row.id == proposed.id and row.channel == "web"
    message = session.get(AdvisorMessage, row.message_id)
    assert message is not None and message.role == "assistant" and row.user_id == LOCAL_USER_ID
    logged = " ".join(record.getMessage() + str(record.__dict__) for record in caplog.records)
    assert "REDBUS" not in logged and "Railways" not in logged
    assert any(getattr(record, "record_changes", None) == 2 for record in caplog.records)


def test_a_clarifying_answer_proposes_nothing(session, settings, toolbox, scripted):
    settings = settings.model_copy(update={"advisor_edits_enabled": True})
    scripted(
        [call("propose_changes", {"changes": [change(payee="REDBUS", category="travel")]})],
        reply("Which payments do you mean?", policy="clarify"),
    )
    answer = ask(session, settings, toolbox, "Fix it")
    assert answer.change_set is None and session.scalar(select(RecordChangeSet)) is None
