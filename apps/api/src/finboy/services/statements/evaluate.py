"""The gate for reading a real Google Pay statement (docs/statement-round/contract.md).

Reads one statement through the same isolated reader the app uses and prints aggregates only:
pages, rows by direction, whether the rows add up to Google's own totals to the paisa, payees paid
(or received from) under two spellings that differ only by a space (the sign of an extractor
joining words), and how long reading took. Google itself prints some people with spaces when paid
and without when received from, so only a split within one direction counts. It never prints a
name, amount, UPI ID, phone number or account digit. Keep the statement outside the repository.
"""

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from time import perf_counter

from finboy.services.statements.gpay import PARSE_SECONDS, Row, StatementError, read_statement


def split_spellings(rows: Iterable[Row]) -> int:
    """Payees printed with and without a space in one direction: each splits one payee in two."""
    spellings: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        spellings[row.direction, "".join(row.name.split())].add(row.name)
    return sum(1 for found in spellings.values() if len(found) > 1)


def evaluate(data: bytes) -> dict[str, object]:
    began = perf_counter()
    try:
        statement = read_statement(data)
    except StatementError as exc:
        return {"error": exc.code, "passed": False}
    seconds = round(perf_counter() - began, 2)
    rows = statement.rows
    result: dict[str, object] = {
        "pages": statement.pages,
        "rows": len(rows),
        "paid_rows": sum(row.direction == "out" for row in rows),
        "received_rows": sum(row.direction == "in" for row in rows),
        "self_transfer_rows": sum(row.direction == "other" for row in rows),
        "sent_matches": statement.paid_minor == statement.sent_minor,
        "received_matches": statement.got_minor == statement.received_minor,
        "repeated_upi_ids": len(rows) - len({row.upi_id for row in rows}),
        "counterparties": len({" ".join(row.name.split()).casefold() for row in rows}),
        "payees_split_by_a_space": split_spellings(rows),
        "accounts": len(statement.accounts),
        "seconds": seconds,
    }
    result["passed"] = (
        statement.reconciled and result["payees_split_by_a_space"] == 0 and seconds < PARSE_SECONDS
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="A Google Pay statement PDF outside the repository")
    args = parser.parse_args()
    result = evaluate(args.path.read_bytes())
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
