"""Changes the advisor proposes and the household applies with one tap (docs/advisor-edits-round).

The model proposes; code checks each change against the household's records and works out what it
would do, and nothing changes until the household taps Apply. Applying works it out again against
the records as they are then, through the correction the Transactions page uses, and keeps each
touched field's value before and after. One Undo puts back every field still at its applied value
and leaves anything changed since as it is. `plan` is pure over a `Ledger` read once, so what the
household is shown and what Apply does follow the same rules.
"""

import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.clock import now_ist
from finboy.db.models.changes import RecordChangeSet
from finboy.db.models.core import User
from finboy.db.models.ledger import Transaction
from finboy.db.models.money import Budget, MerchantCategory
from finboy.services.assistant.language import money
from finboy.services.assistant.models import ChangeGroup, ChangeSetView
from finboy.services.ledger.persist import refresh_links
from finboy.services.ledger.reconcile import correct_transaction, revision
from finboy.services.money import budgets
from finboy.services.money.merchants import merchant_key
from finboy.services.money.payees import SpendingCategory
from finboy.services.privacy.audit import audit
from finboy.services.ux.state import TaskError, data_version

logger = logging.getLogger(__name__)
ChangeType = Literal[
    "payee_category", "record_category", "own_transfer", "rename_payee", "budget", "savings_goal"
]
LIFETIME = timedelta(hours=24)
MAX_CHANGES = 80
MAX_NAME = 60
NAMES_SHOWN = 3
OPEN = ("confirmed", "needs_review")
FIELDS = ("category", "kind", "merchant")
# Category "transfer" alone still counts as spending, so own-account moves use own_transfer.
SPENDING: frozenset[str] = frozenset(get_args(SpendingCategory)) - {"transfer"}
RECEIVED: frozenset[str] = frozenset(
    {"salary", "other_income", "wages", "farm_sales", "govt_benefit", "remittance", "friends"}
    | {"family_events", "work", "other"}
)
INCOME_KINDS = frozenset({"salary", "income_other", "refund", "reversal"})
SPENDING_KINDS = frozenset({"purchase", "fee", "bill_payment", "emi", "investment"})


class Change(BaseModel):
    """One checked change, as a change set stores it."""

    model_config = ConfigDict(extra="forbid")
    type: ChangeType
    payee: str | None = None  # every payment to a payee, by its name in the records
    record_id: UUID | None = None  # one payment
    category: str | None = None  # the new category; a budget's category, or "total"
    new_name: str | None = None
    amount_minor: int | None = None  # a budget or the goal, per month; None removes it


@dataclass(frozen=True)
class Row:
    """An open household record, as a plan reads it."""

    id: UUID
    direction: str
    kind: str
    merchant: str
    category: str
    amount_minor: int
    locked: frozenset[str] = frozenset()


@dataclass
class Ledger:
    """What a plan reads: open household records, budgets, the goal and payee memory."""

    rows: dict[UUID, Row]
    budgets: dict[str, int] = field(default_factory=dict)
    goal: int | None = None
    payees: dict[str, tuple[str | None, str | None]] = field(default_factory=dict)
    by_payee: dict[str, list[Row]] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        for row in self.rows.values():
            key = merchant_key(row.merchant)
            if key is not None:
                self.by_payee.setdefault(key, []).append(row)


@dataclass
class Plan:
    """What a list of changes would do to the records as they are now."""

    updates: dict[UUID, dict[str, str]]  # record → field → new value
    payees: dict[str, dict[str, str]]  # payee key → what to remember (category, display_name)
    budgets: dict[str, int | None]
    goal: list[int | None]  # empty when the goal stays; [None] clears it
    kept: int  # payments the household set itself, left as they are
    problems: list[str]
    groups: list[ChangeGroup]

    @property
    def count(self) -> int:
        return len(self.updates) + len(self.budgets) + len(self.goal)


@dataclass(frozen=True)
class Proposal:
    """A checked proposal from one answer, saved with that answer."""

    changes: list[Change]
    plan: Plan


def clean_name(value: str | None) -> str | None:
    """A payee name the household chose: 1 to 60 printable characters, never "Unknown"."""
    name = " ".join((value or "").split())
    if not 1 <= len(name) <= MAX_NAME or not name.isprintable() or merchant_key(name) is None:
        return None
    return name


def load(session: Session, user_id: UUID) -> Ledger:
    rows = session.execute(
        select(
            Transaction.id,
            Transaction.direction,
            Transaction.kind,
            Transaction.merchant,
            Transaction.category,
            Transaction.amount_minor,
            Transaction.user_locked_fields,
        ).where(
            Transaction.user_id == user_id,
            Transaction.dataset == "household",
            Transaction.status.in_(OPEN),
        )
    )
    return Ledger(
        rows={
            row.id: Row(
                row.id,
                row.direction,
                row.kind,
                row.merchant,
                row.category,
                row.amount_minor,
                frozenset(row.user_locked_fields or []),
            )
            for row in rows
        },
        budgets={
            category: limit
            for category, limit in session.execute(
                select(Budget.category, Budget.limit_minor).where(Budget.user_id == user_id)
            )
        },
        goal=session.scalar(select(User.monthly_savings_goal_minor).where(User.id == user_id)),
        payees={
            key: (category, name)
            for key, category, name in session.execute(
                select(
                    MerchantCategory.merchant_key,
                    MerchantCategory.category,
                    MerchantCategory.display_name,
                ).where(MerchantCategory.user_id == user_id)
            )
        },
    )


def _fits(kind: str, direction: str) -> bool:
    return not (
        (kind in INCOME_KINDS and direction != "in")
        or (kind in SPENDING_KINDS and direction != "out")
    )


def _one(row: Row, change: Change, problems: list[str]) -> dict[str, str]:
    """A change to one payment, which replaces any payee-wide change to it."""
    if change.type == "own_transfer":
        return {"kind": "transfer", "category": "transfer"}
    if change.type == "rename_payee":
        return {"merchant": change.new_name or ""}
    category = change.category or ""
    if category not in (SPENDING if row.direction == "out" else RECEIVED):
        problems.append(
            f'"{category}" does not fit money {"paid" if row.direction == "out" else "received"}'
        )
        return {}
    values = {"category": category}
    if row.kind == "transfer":  # not an own-account move after all: it counts again
        values["kind"] = (
            "purchase"
            if row.direction == "out"
            else "salary"
            if category == "salary"
            else "income_other"
        )
    return values


def _group(kind: str, rows: list[Row], **extra: Any) -> ChangeGroup:
    """Payees largest first, each in the spelling that carries most of its money."""
    spellings: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        spellings[merchant_key(row.merchant) or row.merchant][row.merchant] += row.amount_minor
    totals = {key: sum(found.values()) for key, found in spellings.items()}
    shown = {
        key: min(found, key=lambda name: (-found[name], name)) for key, found in spellings.items()
    }
    names = [shown[key] for key in sorted(totals, key=lambda key: (-totals[key], shown[key]))]
    return ChangeGroup(
        kind=kind,  # type: ignore[arg-type]
        names=names[:NAMES_SHOWN],
        more_names=max(len(names) - NAMES_SHOWN, 0),
        payments=len(rows),
        amount_minor=sum(row.amount_minor for row in rows),
        **extra,
    )


def _groups(
    ledger: Ledger,
    updates: dict[UUID, dict[str, str]],
    budget_changes: dict[str, int | None],
    goal: list[int | None],
) -> list[ChangeGroup]:
    moved: dict[str, list[Row]] = defaultdict(list)
    own: list[Row] = []
    renamed: dict[str, list[Row]] = defaultdict(list)
    for record_id, values in updates.items():
        row = ledger.rows[record_id]
        if values.get("kind") == "transfer":
            own.append(row)
        elif "category" in values:
            moved[values["category"]].append(row)
        if "merchant" in values:
            renamed[values["merchant"]].append(row)
    groups = sorted(
        (_group("category", rows, category=category) for category, rows in moved.items()),
        key=lambda group: (-group.amount_minor, group.category or ""),
    )
    if own:
        groups.append(_group("own_transfer", own))
    groups += [_group("rename", rows, new_name=name) for name, rows in sorted(renamed.items())]
    groups += [
        ChangeGroup(
            kind="budget",
            category=category,
            before_minor=ledger.budgets.get(category),
            after_minor=amount,
        )
        for category, amount in sorted(budget_changes.items())
    ]
    if goal:
        groups.append(
            ChangeGroup(kind="savings_goal", before_minor=ledger.goal, after_minor=goal[0])
        )
    return groups


def plan(ledger: Ledger, changes: Iterable[Change]) -> Plan:
    """What the changes would do. Payee-wide changes leave payments the household set itself
    as they are; a change to one payment is the household's own word and always applies."""
    problems: list[str] = []
    wide: dict[UUID, dict[str, str]] = {}
    single: dict[UUID, dict[str, str]] = {}
    memory: dict[str, dict[str, str]] = {}
    budget_changes: dict[str, int | None] = {}
    goal: list[int | None] = []
    kept: set[UUID] = set()

    def put(layer: dict[Any, dict[str, str]], key: Any, values: dict[str, str], what: str) -> None:
        current = layer.setdefault(key, {})
        if any(current.get(name, value) != value for name, value in values.items()):
            problems.append(f"two changes disagree about {what}; keep one")
            return
        current.update(values)

    for change in changes:
        if change.type in {"budget", "savings_goal"}:
            amount = change.amount_minor
            if amount is not None and not 0 < amount <= budgets.MAX_MINOR:
                problems.append("a budget or goal must be from ₹1 to ₹1 crore a month")
                continue
            if change.type == "savings_goal":
                if goal and goal[0] != amount:
                    problems.append("two changes disagree about the savings goal; keep one")
                elif ledger.goal != amount and not goal:
                    goal.append(amount)
                continue
            category = change.category or ""
            if category not in budgets.BUDGETED:
                problems.append(f'no budget can be set for "{category}"')
            elif budget_changes.get(category, amount) != amount:
                problems.append(f"two changes disagree about the {category} budget; keep one")
            elif ledger.budgets.get(category) != amount:
                budget_changes[category] = amount
            continue
        if change.record_id is not None:
            row = ledger.rows.get(change.record_id)
            if row is None:
                problems.append("a payment ref no longer matches an open record")
                continue
            values = _one(row, change, problems)
            if values:
                put(single, row.id, values, f"one payment to {row.merchant}")
            continue
        key = merchant_key(change.payee)
        if key is None:
            problems.append(
                f'"{change.payee}" is an unknown or hidden name, which may be several people: '
                "change its payments one by one, by ref"
            )
            continue
        rows = ledger.by_payee.get(key, [])
        if not rows:
            problems.append(
                f'no payments to "{change.payee}" in their records: use the name exactly as a '
                "tool listed it"
            )
            continue
        if change.type == "rename_payee":
            name = change.new_name or ""
            for row in rows:
                put(wide, row.id, {"merchant": name}, f'the name of "{change.payee}"')
            put(memory, key, {"display_name": name}, f'the name of "{change.payee}"')
            continue
        out = [row for row in rows if row.direction == "out"]
        if change.type == "payee_category":
            category = change.category or ""
            spending = [row for row in out if row.kind != "transfer"]
            if category not in SPENDING:
                problems.append(f'"{category}" is not a spending category')
                continue
            if not spending:
                problems.append(f'"{change.payee}" has no spending to sort')
                continue
            followed = 0
            for row in spending:
                if "category" in row.locked and row.category != category:
                    kept.add(row.id)
                    continue
                followed += 1
                put(wide, row.id, {"category": category}, f'"{change.payee}"')
            if followed:  # a payee whose every payment the household set keeps its memory too
                put(memory, key, {"category": category}, f'"{change.payee}"')
            continue
        if not out:  # own_transfer
            problems.append(f'nothing was paid to "{change.payee}"')
            continue
        for row in out:
            if ("kind" in row.locked and row.kind != "transfer") or (
                "category" in row.locked and row.category != "transfer"
            ):
                kept.add(row.id)
                continue
            put(wide, row.id, {"kind": "transfer", "category": "transfer"}, f'"{change.payee}"')

    updates: dict[UUID, dict[str, str]] = {}
    for record_id in dict.fromkeys([*wide, *single]):
        row = ledger.rows[record_id]
        final = dict(wide.get(record_id, {}))
        one = single.get(record_id, {})
        if {"category", "kind"} & one.keys():
            final.pop("category", None)
            final.pop("kind", None)
        final.update(one)
        changed = {name: value for name, value in final.items() if getattr(row, name) != value}
        if "kind" in changed and not _fits(changed["kind"], row.direction):
            problems.append(f"one payment to {row.merchant} cannot change that way")
            continue
        if changed:
            updates[record_id] = changed
    remembered: dict[str, dict[str, str]] = {}
    for key, values in memory.items():
        category, name = ledger.payees.get(key, (None, None))
        now = {"category": category, "display_name": name}
        changed = {item: value for item, value in values.items() if now[item] != value}
        if changed:
            remembered[key] = changed
    return Plan(
        updates=updates,
        payees=remembered,
        budgets=budget_changes,
        goal=goal,
        kept=len(kept - single.keys()),
        problems=problems,
        groups=_groups(ledger, updates, budget_changes, goal),
    )


def line(group: ChangeGroup, words: ModuleType) -> str:
    """One proposal line in a WhatsApp copy module's language (english, hindi or malayalam)."""
    one, many = words.CHANGE_PAYMENTS
    payments = f"{group.payments} {one if group.payments == 1 else many}"
    names = ", ".join(group.names) + (f" +{group.more_names}" if group.more_names else "")
    if group.kind == "category":
        return f"{words.label(group.category or 'other')} · {names} · {payments} · " + money(
            group.amount_minor
        )
    if group.kind == "own_transfer":
        return f"{words.CHANGE_OWN} · {names} · {payments} · {money(group.amount_minor)}"
    if group.kind == "rename":
        return f"{words.CHANGE_RENAME}: {group.new_name} · {names} · {payments}"
    title = (
        words.CHANGE_GOAL
        if group.kind == "savings_goal"
        else words.CHANGE_BUDGET.format(label=words.label(group.category or "total"))
    )
    after = (
        words.CHANGE_REMOVED
        if group.after_minor is None
        else words.CHANGE_MONTHLY.format(amount=money(group.after_minor))
    )
    if group.before_minor is None:
        return f"{title} · {after}"
    return f"{title} · {words.CHANGE_MONTHLY.format(amount=money(group.before_minor))} → {after}"


def _summary(found: Plan, skipped: int = 0) -> dict[str, Any]:
    return {
        "count": found.count,
        "groups": [group.model_dump(mode="json") for group in found.groups],
        "kept": found.kept,
        "remembered": len(found.payees),
        "skipped": skipped,
    }


def _log(outcome: str, channel: str, count: int, skipped: int = 0) -> None:
    """Counts only: never a payee, category or amount."""
    logger.info(
        "advisor.changes",
        extra={"outcome": outcome, "stage": channel, "record_changes": count, "count": skipped},
    )


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def view(
    row: RecordChangeSet, version: str | None = None, now: datetime | None = None
) -> ChangeSetView:
    now = now or datetime.now(UTC)
    expired = row.state == "proposed" and _aware(row.expires_at) <= now
    summary = row.summary or {}
    return ChangeSetView(
        id=row.id,
        state="expired" if expired else row.state,  # type: ignore[arg-type]
        count=summary.get("count", 0),
        groups=[ChangeGroup.model_validate(item) for item in summary.get("groups", [])],
        kept=summary.get("kept", 0),
        remembered=summary.get("remembered", 0),
        skipped=summary.get("skipped", 0),
        expires_at=_aware(row.expires_at),
        applied_at=_aware(row.applied_at) if row.applied_at else None,
        undone_at=_aware(row.undone_at) if row.undone_at else None,
        data_version=version,
    )


def propose(
    session: Session,
    *,
    user_id: UUID,
    channel: Literal["web", "whatsapp"],
    message_id: UUID | None,
    proposal: Proposal,
    now: datetime | None = None,
) -> RecordChangeSet:
    """Keep a checked proposal with the answer that offered it; the caller commits."""
    now = now or datetime.now(UTC)
    row = RecordChangeSet(
        user_id=user_id,
        message_id=message_id,
        channel=channel,
        state="proposed",
        changes=[item.model_dump(mode="json", exclude_none=True) for item in proposal.changes],
        summary=_summary(proposal.plan),
        created_at=now,
        expires_at=now + LIFETIME,
    )
    session.add(row)
    session.flush()
    return row


def for_messages(
    session: Session, user_id: UUID, message_ids: list[UUID]
) -> dict[UUID, ChangeSetView]:
    """The change set each advisor answer offered, for a reloaded chat."""
    if not message_ids:
        return {}
    rows = session.scalars(
        select(RecordChangeSet).where(
            RecordChangeSet.user_id == user_id, RecordChangeSet.message_id.in_(message_ids)
        )
    )
    return {row.message_id: view(row) for row in rows if row.message_id is not None}


def find(session: Session, user_id: UUID, change_set_id: UUID) -> ChangeSetView:
    row = session.scalar(
        select(RecordChangeSet).where(
            RecordChangeSet.id == change_set_id, RecordChangeSet.user_id == user_id
        )
    )
    if row is None:
        raise TaskError("not_found")
    return view(row)


def _locked(session: Session, user_id: UUID, change_set_id: UUID) -> RecordChangeSet:
    # The same household lock and order as ingestion and review, then the change set's row.
    from finboy.services.ingestion.pipeline import _user_lock

    _user_lock(session, user_id)
    session.scalar(select(User.id).where(User.id == user_id).with_for_update())
    row = session.scalar(
        select(RecordChangeSet)
        .where(RecordChangeSet.id == change_set_id, RecordChangeSet.user_id == user_id)
        .with_for_update()
    )
    if row is None:
        raise TaskError("not_found")
    return row


def _fields(item: Transaction) -> dict[str, Any]:
    return {
        "category": item.category,
        "kind": item.kind,
        "merchant": item.merchant,
        "user_locked_fields": sorted(item.user_locked_fields or []),
    }


def _payee(item: MerchantCategory | None) -> dict[str, str | None] | None:
    return None if item is None else {"category": item.category, "display_name": item.display_name}


def _limit(session: Session, user_id: UUID, category: str) -> int | None:
    return session.scalar(
        select(Budget.limit_minor).where(Budget.user_id == user_id, Budget.category == category)
    )


def _goal(session: Session, user_id: UUID) -> int | None:
    return session.scalar(select(User.monthly_savings_goal_minor).where(User.id == user_id))


def _write(session: Session, user_id: UUID, found: Plan) -> tuple[dict, dict]:
    before: dict[str, Any] = {"records": {}, "payees": {}, "budgets": {}}
    after: dict[str, Any] = {"records": {}, "payees": {}, "budgets": {}}
    for record_id, values in found.updates.items():
        item = session.get(Transaction, record_id)
        if item is None:
            continue
        before["records"][str(record_id)] = _fields(item)
        correct_transaction(
            session,
            user_id=user_id,
            transaction_id=record_id,
            category=values.get("category"),  # type: ignore[arg-type]
            kind=values.get("kind"),
            merchant=values.get("merchant"),
            reason="advisor_change",
        )
        after["records"][str(record_id)] = _fields(item)
    for key, values in found.payees.items():
        payee = session.get(MerchantCategory, (user_id, key))
        before["payees"][key] = _payee(payee)
        if payee is None:
            payee = MerchantCategory(user_id=user_id, merchant_key=key)
            session.add(payee)
        for name, value in values.items():
            setattr(payee, name, value)
        payee.updated_at = now_ist()
        after["payees"][key] = _payee(payee)
    for category, amount in found.budgets.items():
        before["budgets"][category] = _limit(session, user_id, category)
        budgets.set_budget(session, user_id, category, amount)
        after["budgets"][category] = amount
    if found.goal:
        before["goal"] = _goal(session, user_id)
        budgets.set_goal(session, user_id, found.goal[0])
        after["goal"] = found.goal[0]
    session.flush()
    return before, after


def apply(
    session: Session, *, user_id: UUID, change_set_id: UUID, now: datetime | None = None
) -> ChangeSetView:
    """Apply a proposal to the records as they are now; changes that no longer apply are
    skipped and counted. Commits."""
    now = now or datetime.now(UTC)
    try:
        row = _locked(session, user_id, change_set_id)
        if row.state == "proposed" and _aware(row.expires_at) <= now:
            row.state = "expired"
            session.commit()
            raise TaskError("changes_expired")
        if row.state != "proposed":
            raise TaskError("changes_closed")
        found = plan(load(session, user_id), [Change.model_validate(item) for item in row.changes])
        try:
            row.before_state, row.after_state = _write(session, user_id, found)
        except ValueError:
            raise TaskError("invalid_decision") from None
        refresh_links(session, user_id)
        row.summary = _summary(found, skipped=len(found.problems))
        row.state, row.applied_at = "applied", now
        audit(session, "advisor.changes_applied", "user", user_id, user_id=user_id)
        session.flush()
        result, channel = view(row, data_version(session, user_id), now), row.channel
        session.commit()
        _log("applied", channel, found.count)
        return result
    except Exception:
        session.rollback()
        raise


def _restore(item: Transaction, old: dict[str, Any], new: dict[str, Any], session: Session) -> bool:
    """Put back each field still at its applied value; False when any was changed since."""
    restored = {
        name for name in FIELDS if old[name] != new[name] and getattr(item, name) == new[name]
    }
    if "kind" in restored and not _fits(old["kind"], item.direction):
        restored.discard("kind")
    clean = restored == {name for name in FIELDS if old[name] != new[name]}
    for name in sorted(restored):
        revision(
            session,
            item,
            name,
            getattr(item, name),
            old[name],
            reason="change_undone",
            changed_by="user",
        )
        setattr(item, name, old[name])
    added = set(new["user_locked_fields"]) - set(old["user_locked_fields"])
    locks = sorted(set(item.user_locked_fields or []) - (added & restored))
    if locks != sorted(item.user_locked_fields or []):
        revision(
            session,
            item,
            "user_locked_fields",
            item.user_locked_fields,
            locks,
            reason="change_undone",
            changed_by="user",
        )
        item.user_locked_fields = locks
    if restored:
        item.updated_at = now_ist()
    return clean


def undo(
    session: Session, *, user_id: UUID, change_set_id: UUID, now: datetime | None = None
) -> ChangeSetView:
    """Put back what applying changed, wherever nothing changed it since. Runs once; commits."""
    now = now or datetime.now(UTC)
    try:
        row = _locked(session, user_id, change_set_id)
        if row.state != "applied":
            raise TaskError("changes_closed")
        before, after = row.before_state or {}, row.after_state or {}
        skipped = 0
        for key, old in before.get("records", {}).items():
            item = session.scalar(
                select(Transaction)
                .where(Transaction.id == UUID(key), Transaction.user_id == user_id)
                .with_for_update()
            )
            if item is None or item.status not in OPEN:
                skipped += 1
                continue
            skipped += not _restore(item, old, after["records"][key], session)
        for key, old in before.get("payees", {}).items():
            payee = session.get(MerchantCategory, (user_id, key))
            if payee is None or _payee(payee) != after["payees"][key]:
                skipped += 1
            elif old is None:
                session.delete(payee)
            else:
                payee.category, payee.display_name = old["category"], old["display_name"]
                payee.updated_at = now_ist()
        for category, old in before.get("budgets", {}).items():
            if _limit(session, user_id, category) != after["budgets"][category]:
                skipped += 1
            else:
                budgets.set_budget(session, user_id, category, old)
        if "goal" in before:
            if _goal(session, user_id) != after.get("goal"):
                skipped += 1
            else:
                budgets.set_goal(session, user_id, before["goal"])
        session.flush()
        refresh_links(session, user_id)
        row.summary = {**(row.summary or {}), "skipped": skipped}
        row.state, row.undone_at = "undone", now
        audit(session, "advisor.changes_undone", "user", user_id, user_id=user_id)
        session.flush()
        result, channel = view(row, data_version(session, user_id), now), row.channel
        session.commit()
        _log("undone", channel, result.count, skipped)
        return result
    except Exception:
        session.rollback()
        raise


def decline(
    session: Session, *, user_id: UUID, change_set_id: UUID, now: datetime | None = None
) -> ChangeSetView:
    """Not now: the proposal closes and nothing changes. Commits."""
    now = now or datetime.now(UTC)
    try:
        row = session.scalar(
            select(RecordChangeSet)
            .where(RecordChangeSet.id == change_set_id, RecordChangeSet.user_id == user_id)
            .with_for_update()
        )
        if row is None:
            raise TaskError("not_found")
        if row.state == "proposed":
            row.state = "declined"
        elif row.state != "declined":
            raise TaskError("changes_closed")
        session.flush()
        result = view(row, data_version(session, user_id), now)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
