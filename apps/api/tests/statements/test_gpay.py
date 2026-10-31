"""Reading Google Pay statements: every row exactly, or a fixed code and nothing else."""

from datetime import date, datetime

import pypdfium2 as pdfium
import pytest
from finboy.core.clock import IST
from finboy.services.statements import gpay
from finboy.services.statements.gpay import StatementError, parse_statement, read_statement

from .statement_pdf import Row, pdf_document, statement_pdf

RECEIVED = Row(
    date="02 Apr,",
    time="09:15 PM",
    details=["Received from Ravi Kumar"],
    upi="200000000002",
    account="Paid to Sample Bank 1234",
    amount=["₹12,50", "0"],
)


def problem(data: bytes) -> str:
    with pytest.raises(StatementError) as raised:
        parse_statement(data)
    return raised.value.code


def test_rows_keep_every_detail_and_add_up_to_the_statement_totals() -> None:
    paise = Row(date="03 Apr,", time="12:07 AM", upi="300000000003", amount=["₹6,318.", "27"])
    statement = parse_statement(
        statement_pdf(
            [[Row(), RECEIVED, paise]], sent="₹6,633.27", received="₹12,500", phone="9000000001"
        )
    )
    assert (statement.period_start, statement.period_end) == (date(2026, 4, 1), date(2026, 4, 30))
    assert (statement.sent_minor, statement.received_minor, statement.pages) == (663327, 1250000, 1)
    assert statement.reconciled and statement.phone == "9000000001"
    assert statement.accounts == ("Sample Bank ••1234",)
    first, second, third = statement.rows
    assert first.occurred_at == datetime(2026, 4, 1, 10, 42, tzinfo=IST)
    assert (first.direction, first.name, first.detail) == (
        "out",
        "Asha Stores",
        "Paid to Asha Stores",
    )
    assert (first.upi_id, first.bank, first.last4, first.amount_minor) == (
        "100000000001",
        "Sample Bank",
        "1234",
        31500,
    )
    # Amounts that wrap in the narrow column join exactly, paise included.
    assert (second.direction, second.name, second.amount_minor) == ("in", "Ravi Kumar", 1250000)
    assert (third.amount_minor, third.occurred_at.hour) == (631827, 0)
    assert [(row.page, row.position) for row in statement.rows] == [(1, 1), (1, 2), (1, 3)]


def test_a_long_name_that_wraps_is_one_name_and_pages_continue_in_order() -> None:
    long = Row(
        details=["Paid to Sample Agro Implements and Hardware Trading", "Company Private Limited"]
    )
    second_page = [Row(date="20 Apr,", upi="400000000004", amount=["₹1,00,000"])]
    statement = parse_statement(
        statement_pdf([[long], second_page], sent="₹1,00,315", received="₹0")
    )
    assert (
        statement.rows[0].name
        == "Sample Agro Implements and Hardware Trading Company Private Limited"
    )
    assert (statement.rows[1].page, statement.rows[1].amount_minor) == (2, 10_000_000)
    assert statement.reconciled and statement.pages == 2


def test_totals_that_do_not_match_are_reported_not_hidden() -> None:
    statement = parse_statement(statement_pdf([[Row(), RECEIVED]], sent="₹330", received="₹12,500"))
    assert not statement.reconciled
    assert (statement.paid_minor, statement.sent_minor) == (31500, 33000)


def test_a_row_that_is_neither_paid_nor_received_is_kept_apart_from_the_totals() -> None:
    transfer = Row(
        details=["Self transfer to Sample Bank 5678"], upi="500000000005", amount=["₹5,000"]
    )
    statement = parse_statement(statement_pdf([[Row(), transfer]], sent="₹315", received="₹0"))
    assert statement.reconciled
    assert statement.rows[1].direction == "other"
    assert statement.rows[1].name == "Self transfer to Sample Bank 5678"


def test_missing_pages_and_rows_outside_the_period_are_unreadable() -> None:
    pages = [[Row()], [Row(date="05 Apr,", upi="600000000006")]]
    assert problem(statement_pdf(pages, numbering=[(1, 3), (2, 3)], sent="₹568")) == (
        "statement_unreadable"
    )
    assert problem(statement_pdf([[Row(date="02 May,")]], sent="₹315")) == "statement_unreadable"


def test_other_files_are_refused_with_a_fixed_code() -> None:
    assert problem(b"") == "upload_limit"
    assert problem(b"%PDF-" + b"0" * gpay.MAX_BYTES) == "upload_limit"
    assert problem(b"not a pdf at all") == "not_gpay_statement"
    assert problem(b"%PDF-1.4 broken") == "not_gpay_statement"
    assert problem(pdf_document([[(72, 720, 12, "A letter, not a statement")]])) == (
        "not_gpay_statement"
    )
    assert problem(statement_pdf([[Row()]], note="Note: printed elsewhere", sent="₹315")) == (
        "not_gpay_statement"
    )


def test_password_protected_statements_ask_for_a_fresh_download(monkeypatch) -> None:
    import pypdfium2.raw as pdfium_c

    def locked(*args: object, **kwargs: object) -> None:
        raise pdfium.PdfiumError("Incorrect password error", err_code=pdfium_c.FPDF_ERR_PASSWORD)

    monkeypatch.setattr(gpay.pdfium, "PdfDocument", locked)
    assert problem(statement_pdf([[Row()]], sent="₹315")) == "statement_locked"


def test_page_and_row_limits_hold(monkeypatch) -> None:
    pages = [[Row()], [Row(date="05 Apr,", upi="600000000006")]]
    monkeypatch.setattr(gpay, "MAX_PAGES", 1)
    assert problem(statement_pdf(pages, sent="₹568")) == "upload_limit"
    monkeypatch.setattr(gpay, "MAX_PAGES", 600)
    monkeypatch.setattr(gpay, "MAX_ROWS", 1)
    assert problem(statement_pdf([[Row(), RECEIVED]], sent="₹315", received="₹12,500")) == (
        "upload_limit"
    )


def test_the_isolated_reader_returns_the_same_rows_and_only_fixed_codes() -> None:
    data = statement_pdf([[Row(), RECEIVED]], sent="₹315", received="₹12,500")
    assert read_statement(data) == parse_statement(data)
    with pytest.raises(StatementError) as raised:
        read_statement(b"not a pdf at all")
    assert raised.value.code == "not_gpay_statement"
    with pytest.raises(StatementError) as raised:
        read_statement(data, seconds=0.001)
    assert raised.value.code == "statement_unreadable"
