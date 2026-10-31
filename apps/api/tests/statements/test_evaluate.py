"""`pnpm eval:gpay` prints aggregates only, so its output can be shared."""

import json

from finboy.services.statements import evaluate

from .statement_pdf import Row, statement_pdf


def test_a_statement_is_judged_on_counts_and_totals_without_its_details(
    tmp_path, capsys, monkeypatch
) -> None:
    rows = [
        Row(details=["Paid to Asha Stores"], upi="100000000001"),
        Row(details=["Paid to AshaStores"], upi="100000000002", amount=["₹16"]),
        Row(
            details=["Received from Ravi Kumar"],
            upi="100000000003",
            account="Paid to Sample Bank 1234",
            amount=["₹12,50", "0"],
        ),
        # One person printed with spaces one way and without the other: not a reading problem.
        Row(details=["Paid to RaviKumar"], upi="100000000004", amount=["₹100"]),
    ]
    path = tmp_path / "statement.pdf"
    path.write_bytes(statement_pdf([rows], sent="₹431", received="₹12,500"))
    monkeypatch.setattr("sys.argv", ["eval:gpay", str(path)])

    assert evaluate.main() == 1
    printed = capsys.readouterr().out
    for detail in ("Asha", "Ravi", "100000000001", "1234", "9000000001", "12500", "₹"):
        assert detail not in printed
    result = json.loads(printed)
    assert (result["rows"], result["paid_rows"], result["received_rows"]) == (4, 3, 1)
    assert result["sent_matches"] and result["received_matches"]
    # "Asha Stores" and "AshaStores" are one payee split by a missing space, so the gate fails.
    assert result["payees_split_by_a_space"] == 1 and result["passed"] is False


def test_an_unreadable_file_reports_only_its_code() -> None:
    assert evaluate.evaluate(b"%PDF-1.4 not really") == {
        "error": "not_gpay_statement",
        "passed": False,
    }
