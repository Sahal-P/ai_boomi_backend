"""A synthetic household for advisor tests and the offline eval (docs/advisor-round).

Fixed, made-up figures behind the same Toolbox the real engine implements, and an in-memory
SQLite store for chats and memories. SQLite is a test and eval double only; PostgreSQL remains
the sole runtime store. Nothing here is a real household's data.
"""

from datetime import date, datetime, time, timedelta
from uuid import UUID, uuid4

from sqlalchemy import JSON, MetaData, create_engine, event
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from finboy.core.clock import IST, today_ist
from finboy.core.config import LOCAL_USER_ID
from finboy.db.base import Base
from finboy.db.models import User
from finboy.services.advisor import changes, coach, history, knowledge, web_search
from finboy.services.money import budgets, engine, insights, merchants, payees
from finboy.services.money.engine import (
    CategoryTotal,
    CommitmentView,
    MoneySummary,
    PeriodSpec,
    TransactionView,
)

OTHER_USER = UUID("00000000-0000-0000-0000-0000000000aa")
# Made-up public facts behind search_web, for the eval's price and EMI questions.
SEARCH_FOUND = web_search.Found(
    summary=(
        "Example Roadster 350: on-road price in Kochi about ₹2,40,000.\n"
        "Two-wheeler loans in India usually cost 10% to 14% a year."
    ),
    pages=[web_search.Page(title="Example bike prices", url="https://example.com/bike-prices")],
)


def make_store() -> sessionmaker[Session]:
    engine_ = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine_, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if (
                isinstance(column.type, ARRAY | JSONB)
                and "sqlite" not in column.type._variant_mapping
            ):
                column.type = column.type.with_variant(JSON(), "sqlite")
        copy = table.to_metadata(metadata)
        for column in copy.columns:
            if column.server_default and "::" in str(column.server_default.arg):
                column.server_default = None
    metadata.create_all(engine_)
    make = sessionmaker(engine_, expire_on_commit=False)
    with make.begin() as session:
        session.add(User(id=LOCAL_USER_ID, display_name="Synthetic owner"))
        session.add(User(id=OTHER_USER, display_name="Another synthetic household"))
    return make


def _summary(period: PeriodSpec, *, last_month: bool = False) -> MoneySummary:
    start, end = engine.period_dates(period, today_ist())
    food, groceries = (300000, 280000) if last_month else (420000, 310000)
    return MoneySummary(
        period_start=start,
        period_end=end,
        as_of=today_ist(),
        data_version="7:synthetic",
        tracked_income_minor=3000000,
        confirmed_outflows_minor=1500000 if last_month else 1842050,
        upcoming_commitments_minor=150000,
        unresolved_commitments_minor=150000,
        estimated_unallocated_minor=1350000 if last_month else 1007950,
        pending_review_count=0 if last_month else 1,
        pending_review_minor=0,
        income_transaction_count=1,
        outflow_transaction_count=12,
        commitment_count=1,
        categories=[
            CategoryTotal(category="food_dining", amount_minor=food, transaction_count=6),
            CategoryTotal(category="groceries", amount_minor=groceries, transaction_count=4),
        ]
        + (
            []
            if last_month
            else [
                # Categorised "transfer" but still counted as spending, and payments in "Other".
                CategoryTotal(category="transfer", amount_minor=445000, transaction_count=2),
                CategoryTotal(category="other", amount_minor=262220, transaction_count=4),
            ]
        ),
        evidence_transaction_ids=[],
    )


def payment(name: str, amount: int, *, out: bool = True, category: str = "food_dining"):
    return TransactionView(
        id=uuid4(),
        direction="out" if out else "in",
        kind="purchase" if out else "salary",
        amount_minor=amount,
        merchant=name,
        category=category,
        occurred_at=datetime.combine(today_ist(), time(12), IST),
        status="confirmed",
        confidence=0.9,
    )


class SyntheticHousehold:
    """Fixed figures; records each read so tests can see what the model asked for."""

    def __init__(self) -> None:
        self.reads: list[str] = []
        self.chats: list[history.ChatHit] = []
        self.payments = [
            payment("Swiggy", 45000),
            payment("Swiggy", 32050),
            payment("Ramesh milkman", 6000, category="groceries"),
            payment("Acme Pvt Ltd", 3000000, out=False, category="salary"),
        ]
        # Payments still to sort (docs/advisor-edits-round): listed when asked for by category or
        # name, so the other lists and their totals stay as they were.
        self.others = [
            payment("REDBUS", 120000, category="other"),
            payment("Indian Railways", 58220, category="other"),
            payment("Apollo Pharmacy", 34000, category="other"),
            payment("Unknown 93", 50000, category="other"),
            payment("SBI self transfer", 200000, category="transfer"),
            payment("SBI self transfer", 245000, category="transfer"),
        ]
        self.ledger = changes.Ledger(
            rows={
                row.id: changes.Row(
                    row.id, row.direction, row.kind, row.merchant, row.category, row.amount_minor
                )
                for row in [*self.payments, *self.others]
            },
            budgets={"food_dining": 500000},
            goal=500000,
        )

    def money_summary(self, period: PeriodSpec) -> MoneySummary:
        self.reads.append("money_summary")
        return _summary(period, last_month=period.kind == "month")

    def category_breakdown(self, period: PeriodSpec, category: str | None) -> list[CategoryTotal]:
        self.reads.append("category_breakdown")
        rows = _summary(period, last_month=period.kind == "month").categories
        return [row for row in rows if category is None or row.category == category]

    def find_transactions(
        self, period: PeriodSpec, category: str | None, merchant: str | None
    ) -> list[TransactionView]:
        self.reads.append("find_transactions")
        rows = self.payments
        if category in {"other", "transfer"} or merchant is not None:
            rows = [*self.payments, *self.others]
        return [
            row
            for row in rows
            if (category is None or row.category == category)
            and (merchant is None or merchant.casefold() in row.merchant.casefold())
        ]

    def insights(self, period: PeriodSpec) -> insights.Insights:
        self.reads.append("insights")
        start, end = engine.period_dates(period, today_ist())
        return insights.Insights(
            period_start=start,
            period_end=end,
            months=3,
            money_out_minor=4500000,
            money_in_minor=9000000,
            payment_count=40,
            top_payees=[
                insights.PayeeTotal(
                    name="Swiggy", amount_minor=77050, count=2, share=0.2, category="food_dining"
                )
            ],
            top_senders=[],
            biggest=[],
            regular=[
                insights.RegularPayment(
                    name="Jio",
                    usual_minor=29900,
                    months=3,
                    last_paid=date(2026, 10, 5),
                    next_expected=date(2026, 11, 5),
                    category="phone_recharge",
                )
            ],
            regular_monthly_minor=29900,
            people=[],
            small=insights.SmallPayments(
                threshold_minor=20000,
                count=10,
                amount_minor=90000,
                per_month_minor=30000,
                count_share=0.25,
                amount_share=0.02,
                places=[],
            ),
        )

    def dues(self, period: PeriodSpec) -> list[CommitmentView]:
        self.reads.append("dues")
        return [
            CommitmentView(
                id=uuid4(),
                kind="bill",
                label="Electricity bill",
                amount_minor=150000,
                due_date=period.end_date or today_ist(),
                status="upcoming",
                confidence=0.9,
            )
        ]

    def month_plan(self, period: PeriodSpec) -> budgets.MonthPlan:
        self.reads.append("month_plan")
        start, end = engine.period_dates(period, today_ist())
        return budgets.MonthPlan(
            start=start,
            end=end,
            as_of=today_ist(),
            income_minor=3000000,
            spent_minor=1842050,
            saved_minor=1157950,
            goal_minor=500000,
            budgets=[
                budgets.BudgetStatus(category="food_dining", limit_minor=500000, spent_minor=420000)
            ],
            top=[("food_dining", 420000)],
            waiting=1,
        )

    def simulate(self, monthly_minor: int) -> engine.CashFlowSimulation:
        self.reads.append("simulate")
        return engine.calculate_simulation(_summary(PeriodSpec()), monthly_minor)

    def knowledge(self, query: str) -> list[knowledge.Hit]:
        self.reads.append("knowledge")
        return knowledge.search(query)  # keywords only: no network in tests or offline checks

    def past_chats(self, query: str) -> list[history.ChatHit]:
        self.reads.append("past_chats")
        return list(self.chats)

    def search_web(self, question: str) -> web_search.Found:
        self.reads.append("search_web")
        return SEARCH_FOUND

    def other_payees(self, period: PeriodSpec) -> payees.OtherPayees:
        self.reads.append("other_payees")
        other = [row for row in self.others if row.category == "other"]
        named = [row for row in other if merchants.merchant_key(row.merchant)]
        moved = [row for row in self.others if row.category == "transfer"]
        return payees.OtherPayees(
            items=[
                payees.OtherPayee(
                    name=row.merchant, count=1, amount_minor=row.amount_minor, latest=today_ist()
                )
                for row in sorted(named, key=lambda row: -row.amount_minor)
            ],
            payees=len(named),
            spent_minor=1842050,
            other_minor=sum(row.amount_minor for row in other),
            other_count=len(other),
            unnamed_count=len(other) - len(named),
            unnamed_minor=sum(row.amount_minor for row in other if row not in named),
            transfer_count=len(moved),
            transfer_minor=sum(row.amount_minor for row in moved),
        )

    def own_transfers(self, period: PeriodSpec) -> engine.TransferTotal:
        self.reads.append("own_transfers")
        return engine.TransferTotal(count=1, amount_minor=1500000)

    def plan_changes(self, proposed: list[changes.Change]) -> changes.Plan:
        self.reads.append("plan_changes")
        return changes.plan(self.ledger, proposed)


# Phase 3: a Sunday after the 20th, when every kind of coach nudge can come up.
NUDGE_DAY = date(2026, 11, 22)


def nudges() -> list[coach.Nudge]:
    """One coach nudge of every kind with made-up figures, most important first: the offline
    check's lines and the live gate's wording (evaluate.py)."""

    def record(name: str, amount: int, *, out: bool = True, category: str) -> TransactionView:
        return TransactionView(
            id=UUID(int=amount),
            direction="out" if out else "in",
            kind="purchase" if out else "salary",
            amount_minor=amount,
            merchant=name,
            category=category,
            occurred_at=datetime.combine(NUDGE_DAY, time(12), IST),
            status="confirmed",
            confidence=0.9,
        )

    def due(label: str, amount: int, days: int) -> CommitmentView:
        return CommitmentView(
            id=UUID(int=amount),
            kind="bill",
            label=label,
            amount_minor=amount,
            due_date=NUDGE_DAY + timedelta(days=days),
            status="upcoming",
            confidence=0.9,
        )

    bill = due("Electricity bill", 150000, 1)
    netflix = insights.RegularPayment(
        name="Netflix",
        usual_minor=64900,
        months=3,
        last_paid=NUDGE_DAY - timedelta(days=2),
        next_expected=date(2026, 12, 20),
        category="subscriptions",
    )
    return [
        coach.Nudge(
            "weekly_recap",
            "2026-W47",
            "info",
            coach.RecapDetail(
                start=NUDGE_DAY - timedelta(days=6),
                end=NUDGE_DAY,
                income_minor=3000000,
                outflow_minor=842050,
                top=(("food_dining", 420000), ("groceries", 310000)),
                ahead=(due("Rent", 1200000, 3),),
                overdue_minor=0,
                waiting=1,
            ),
        ),
        coach.Nudge("due_soon", str(bill.id), "warning", coach.DueDetail(bill, 1)),
        coach.Nudge(
            "budget_over",
            "2026-11:total",
            "warning",
            coach.BudgetDetail(budgets.BudgetStatus("total", 2000000, 2100000), 9),
        ),
        coach.Nudge(
            "unusual_payment",
            "unusual",
            "warning",
            coach.UnusualDetail(record("Swiggy", 250000, category="food_dining"), 40000, "payee"),
        ),
        coach.Nudge(
            "income_in",
            "2026-11",
            "good",
            coach.IncomeDetail(
                record("Acme Pvt Ltd", 3000000, out=False, category="salary"), 500000
            ),
        ),
        coach.Nudge(
            "budget_near",
            "2026-11:food_dining",
            "warning",
            coach.BudgetDetail(budgets.BudgetStatus("food_dining", 500000, 420000), 9),
        ),
        coach.Nudge("goal_progress", "2026-11", "warning", coach.GoalDetail(500000, 200000, 9)),
        coach.Nudge("new_regular", "netflix", "info", coach.RegularDetail(netflix, 94800)),
    ]
