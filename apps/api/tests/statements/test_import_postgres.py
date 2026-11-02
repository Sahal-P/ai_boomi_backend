"""Saving statements in PostgreSQL: every row once, linked not duplicated, removable, sortable."""

import time
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from finboy.core.clock import IST
from finboy.core.config import Settings
from finboy.db.models.core import User
from finboy.db.models.ledger import EmailSource, SourceEvent, Transaction
from finboy.db.models.mail import AuditEvent, ImportRun
from finboy.db.models.money import MerchantCategory
from finboy.db.models.statements import StatementImport
from finboy.db.session import build_engine
from finboy.services.accounts.households import remove_household_data
from finboy.services.ingestion.types import Event
from finboy.services.ledger.persist import persist_event
from finboy.services.money.engine import PeriodSpec
from finboy.services.money.insights import money_insights
from finboy.services.money.payees import PayeeChoice, sort_payee
from finboy.services.statements.gpay import Row, Statement
from finboy.services.statements.service import (
    removal_preview,
    remove_statement,
    run_statement_import,
    start_import,
)
from finboy.services.ux.records import PageQuery, transaction_page
from finboy.services.ux.state import data_version
from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration


@pytest.fixture
def world():
    settings = Settings()
    engine = build_engine(settings)
    assert engine.url.host in {"localhost", "127.0.0.1"} and settings.environment != "production"
    assert engine.url.database in {"finboy", "finboy_test", "finboy_signup", "finboy_billing"}, (
        "Use a local test database"
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    households = [uuid4(), uuid4()]
    with factory.begin() as session:
        for user_id in households:
            session.add(User(id=user_id, display_name="Synthetic statement household"))
    try:
        yield settings, engine, factory, households
    finally:
        with factory.begin() as session:
            for user_id in households:
                remove_household_data(session, user_id)
                session.execute(delete(AuditEvent).where(AuditEvent.user_id == user_id))
                session.execute(delete(User).where(User.id == user_id))
        engine.dispose()


def row(
    position: int,
    name: str,
    rupees: float,
    day: int,
    *,
    direction: str = "out",
    month: int = 4,
    minute: int = 0,
) -> Row:
    return Row(
        page=1,
        position=position,
        occurred_at=datetime(2026, month, day, 19, minute, tzinfo=IST),
        direction=direction,  # type: ignore[arg-type]
        name=name,
        detail=f"{'Received from' if direction == 'in' else 'Paid to'} {name}",
        upi_id=f"{month:02}{day:02}{position:08}",
        bank="Sample Bank",
        last4="1234",
        amount_minor=round(rupees * 100),
    )


def statement(
    rows: list[Row], *, start: date = date(2026, 4, 1), end: date = date(2026, 4, 30)
) -> Statement:
    return Statement(
        period_start=start,
        period_end=end,
        sent_minor=sum(item.amount_minor for item in rows if item.direction == "out"),
        received_minor=sum(item.amount_minor for item in rows if item.direction == "in"),
        pages=1,
        rows=tuple(rows),
        phone=None,
    )


def imported(world, user_id: UUID, value: Statement, digest: str | None = None) -> StatementImport:
    settings, engine, factory, _ = world
    with factory() as session:
        run, holder = start_import(
            session,
            settings=settings,
            user_id=user_id,
            statement=value,
            file_sha256=digest or uuid4().hex,
        )
        run_id = run.id
    run_statement_import(engine, run_id, value, file_sha256=digest or "x", holder=holder)
    with factory() as session:
        assert session.get(ImportRun, run_id).status == "completed"
        return session.get(StatementImport, run_id)


def records(factory, user_id: UUID) -> list[Transaction]:
    with factory() as session:
        return list(
            session.scalars(
                select(Transaction)
                .where(Transaction.user_id == user_id)
                .order_by(Transaction.occurred_at)
            )
        )


def existing(factory, user_id: UUID, source: str, event: Event) -> UUID:
    """A record the household already had, from a screenshot or its own words."""
    with factory.begin() as session:
        run = ImportRun(id=uuid4(), user_id=user_id, mode=source, status="completed")
        session.add(run)
        session.flush()
        email = EmailSource(
            id=uuid4(),
            user_id=user_id,
            import_run_id=run.id,
            source=source,
            provider_message_id=uuid4().hex,
            content_sha256="0" * 64,
            sender_domain="whatsapp.invalid",
            subject_sha256="0" * 64,
            received_at=event.occurred_at,
            classification="upi_alert",
            processing_status="extracted",
        )
        session.add(email)
        session.flush()
        persist_event(
            session, user_id=user_id, source=email, event=event, fallback_time=event.occurred_at
        )
        return session.scalar(
            select(SourceEvent.transaction_id).where(SourceEvent.email_source_id == email.id)
        )


def test_every_row_is_saved_once_as_a_confirmed_record_with_its_evidence(world) -> None:
    _, _, factory, (home, other) = world
    rows = [
        row(1, "Asha Stores", 315, 1),
        row(2, "Ravi Kumar", 12500, 6, direction="in"),
        row(3, "AWS India", 6318.27, 7),
    ]
    record = imported(world, home, statement(rows))
    assert (
        record.rows_new,
        record.rows_linked,
        record.rows_already_imported,
        record.reconciled,
    ) == (3, 0, 0, True)
    saved = records(factory, home)
    assert [
        (t.merchant, t.amount_minor, t.direction, t.status, t.payment_instrument, t.account_last4)
        for t in saved
    ] == [
        ("Asha Stores", 31500, "out", "confirmed", "UPI", "1234"),
        ("Ravi Kumar", 1250000, "in", "confirmed", "UPI", "1234"),
        ("AWS India", 631827, "out", "confirmed", "UPI", "1234"),
    ]
    assert saved[2].category == "subscriptions" and saved[0].category == "other"
    assert {t.reference_id for t in saved} == {item.upi_id for item in rows}
    with factory() as session:
        evidence = session.scalars(
            select(SourceEvent).where(SourceEvent.transaction_id == saved[0].id)
        ).one()
        assert (
            evidence.merchant_raw == "Asha Stores"
            and evidence.evidence["detail"] == "Paid to Asha Stores"
        )
        assert (evidence.evidence["bank"], evidence.evidence["page"], evidence.evidence["row"]) == (
            "Sample Bank",
            "1",
            "1",
        )
    assert records(factory, other) == []


def test_the_same_or_an_overlapping_statement_adds_only_what_is_new(world) -> None:
    _, _, factory, (home, _) = world
    april = [row(1, "Asha Stores", 315, 1), row(2, "Asha Stores", 315, 1, minute=2)]
    imported(world, home, statement(april))
    again = imported(world, home, statement(april))
    assert (again.rows_new, again.rows_already_imported) == (0, 2)
    longer = imported(
        world,
        home,
        statement([*april, row(3, "Corner Tea", 12, 2, month=5)], end=date(2026, 5, 31)),
    )
    assert (longer.rows_new, longer.rows_already_imported) == (1, 2)
    assert len(records(factory, home)) == 3


def test_a_payment_already_in_finboy_is_linked_and_a_spoken_one_waits_for_review(world) -> None:
    _, _, factory, (home, _) = world
    screenshot = existing(
        factory,
        home,
        "whatsapp_image",
        Event(
            event_type="debit",
            amount_minor=31500,
            merchant="Asha",
            occurred_at=datetime(2026, 4, 1, 19, 1, tzinfo=IST),
            reference_id="0401" + "00000001",
            payment_proof=True,
            rule_fields=["amount_minor", "occurred_at"],
        ),
    )
    spoken = existing(
        factory,
        home,
        "whatsapp_voice",
        Event(
            event_type="debit",
            amount_minor=50000,
            merchant="milk",
            occurred_at=datetime(2026, 4, 3, 8, tzinfo=IST),
        ),
    )
    record = imported(
        world, home, statement([row(1, "Asha Stores", 315, 1), row(2, "Sample Dairy", 500, 2)])
    )
    assert (record.rows_new, record.rows_linked, record.rows_possible_duplicate) == (0, 1, 1)
    saved = {t.id: t for t in records(factory, home)}
    assert len(saved) == 3
    with factory() as session:
        sources = session.scalar(
            select(func.count())
            .select_from(SourceEvent)
            .where(SourceEvent.transaction_id == screenshot)
        )
        assert sources == 2
    repeat = next(t for t in saved.values() if t.possible_duplicate_of_id == spoken)
    assert (repeat.status, repeat.review_reason, repeat.merchant) == (
        "needs_review",
        "possible_duplicate",
        "Sample Dairy",
    )


def test_removing_a_statement_keeps_records_that_have_other_evidence(world) -> None:
    _, _, factory, (home, _) = world
    screenshot = existing(
        factory,
        home,
        "whatsapp_image",
        Event(
            event_type="debit",
            amount_minor=31500,
            merchant="Asha",
            occurred_at=datetime(2026, 4, 1, 19, 1, tzinfo=IST),
            reference_id="0401" + "00000001",
            payment_proof=True,
        ),
    )
    record = imported(
        world, home, statement([row(1, "Asha Stores", 315, 1), row(2, "Corner Tea", 12, 2)])
    )
    with factory() as session:
        preview = removal_preview(session, user_id=home, run_id=record.import_run_id)
        assert (preview.records_removed, preview.records_kept) == (1, 1)
    with factory.begin() as session:
        remove_statement(session, user_id=home, run_id=record.import_run_id)
    left = records(factory, home)
    assert [t.id for t in left] == [screenshot]
    with factory() as session:
        assert session.get(StatementImport, record.import_run_id).removed_at is not None
        assert (
            session.scalar(
                select(func.count())
                .select_from(EmailSource)
                .where(EmailSource.source == "gpay_statement", EmailSource.user_id == home)
            )
            == 0
        )


def test_sorting_a_payee_sorts_its_past_payments_and_teaches_the_next_import(world) -> None:
    _, _, factory, (home, other) = world
    imported(
        world,
        home,
        statement(
            [
                row(1, "Lakshmi Tailors", 2000, 1),
                row(2, "LAKSHMI TAILORS", 2000, 15),
                row(3, "Corner Tea", 12, 2),
            ]
        ),
    )
    imported(world, other, statement([row(1, "Lakshmi Tailors", 999, 1)]))
    with factory.begin() as session:
        result = sort_payee(
            session,
            user_id=home,
            choice=PayeeChoice(
                name="Lakshmi Tailors",
                category="shopping",
                expected_version=data_version(session, home),
            ),
        )
    assert result.updated == 2
    sorted_rows = [t for t in records(factory, home) if t.merchant.casefold() == "lakshmi tailors"]
    assert {t.category for t in sorted_rows} == {"shopping"}
    assert all("category" in t.user_locked_fields for t in sorted_rows)
    assert {t.category for t in records(factory, other)} == {"other"}
    with factory() as session:
        assert session.get(MerchantCategory, (home, "lakshmi tailors")).category == "shopping"
    later = imported(
        world,
        home,
        statement(
            [row(4, "Lakshmi Tailors", 3000, 20, month=5)],
            start=date(2026, 5, 1),
            end=date(2026, 5, 31),
        ),
    )
    assert later.rows_new == 1
    assert records(factory, home)[-1].category == "shopping"


def test_a_person_printed_with_and_without_spaces_is_one_person(world) -> None:
    # Google Pay prints one person as "Ravi K M" when paid and "RaviKM" when received from.
    _, _, factory, (home, _) = world
    imported(
        world,
        home,
        statement([row(1, "Ravi K M", 500, 2), row(2, "RaviKM", 300, 9, direction="in")]),
    )
    april = PeriodSpec(kind="range", start_date=date(2026, 4, 1), end_date=date(2026, 4, 30))
    with factory() as session:
        people = money_insights(session, user_id=home, period=april).people
        found = transaction_page(session, user_id=home, query=PageQuery(scope="all", q="RaviKM"))
    assert [(p.sent_minor, p.received_minor, p.balance_minor) for p in people] == [
        (50000, 30000, -20000)
    ]
    assert sorted(item.merchant for item in found.items) == ["Ravi K M", "RaviKM"]


def test_two_thousand_rows_are_saved_within_budget(world) -> None:
    _, _, factory, (home, _) = world
    start = date(2026, 1, 1)
    rows = [
        row(index, f"Payee {index % 300}", 10 + index % 997, 1, month=1) for index in range(1, 2001)
    ]
    rows = [
        Row(
            **{
                **item.__dict__,
                "occurred_at": datetime.combine(
                    start + timedelta(days=index % 180), item.occurred_at.timetz()
                ),
                "upi_id": f"9{index:011}",
            }
        )
        for index, item in enumerate(rows)
    ]
    began = time.perf_counter()
    record = imported(world, home, statement(rows, start=start, end=start + timedelta(days=180)))
    assert record.rows_new == 2000
    assert time.perf_counter() - began < 10
