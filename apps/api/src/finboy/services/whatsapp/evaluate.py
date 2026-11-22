"""The gate for the diary reader's dates and amounts (docs/whatsapp.md, "Dates and card replies").

Synthetic messages in English, Hindi, Malayalam, Hinglish and Manglish (fixtures/diary/cases.json)
go through `statement.read_statements`, the code the app uses, with the configured entry-parser
model, read as if today were 22 November 2026. A wrong date or amount fails the run outright, and
at least 95% of cases must be read exactly. `--check` needs no network: it checks the code's own
date reading and that no date is ever read as an amount. Output names cases by ID only.
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any, Literal

from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.services.ingestion import dates
from finboy.services.ingestion.hindi_numbers import parse_amount
from finboy.services.whatsapp import statement

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures" / "diary" / "cases.json"
TODAY = date(2026, 11, 22)
PASS_RATE = 0.95
Case = dict[str, Any]
Verdict = Literal["ok", "miss", "wrong"]


def cases() -> list[Case]:
    return json.loads(FIXTURES.read_text())


def _direction(case: Case) -> dates.Direction:
    return "future" if case["kind"] == "due" else "past"


def check(case: Case) -> str | None:
    """Offline: the code reads the case's date (or the reason to ask), and no amount comes from
    a date. The model's phrases are not involved."""
    said = dates.read_date(case["text"], TODAY, _direction(case))
    if "date" in case:
        expected = date.fromisoformat(case["date"])
        if said.day != expected and not (said.day is None and expected == TODAY):
            return "date"
    if "ask" in case and said.problem != case["ask"]:
        return "ask"
    amount = parse_amount(dates.strip(case["text"], said.spans))
    if amount is not None and amount != case.get("amount"):
        return "amount"
    return None


def judge(case: Case, read: list[statement.Statement]) -> tuple[Verdict, str]:
    """ok, a miss (asked or misread the kind: safe), or wrong (a wrong date or amount saved)."""
    first = read[0]
    kinds = case.get("kinds", [case["kind"]])
    if case["kind"] == "question":
        kinds = [*kinds, "unclear"]  # both go to the advisor
    if first.kind not in kinds:
        return "miss", f"kind {first.kind}"
    if first.kind in {"question", "unclear"}:
        return "ok", ""
    if first.amount_minor != case.get("amount"):
        return ("wrong" if first.amount_minor is not None else "miss"), "amount"
    got = first.due_date if first.kind == "due" else first.day
    if "date" in case and got != date.fromisoformat(case["date"]):
        return ("wrong" if got is not None else "miss"), "date"
    if "ask" in case and got is not None:
        return "wrong", "date"
    if "ask" in case and first.date_problem != case["ask"]:
        return "miss", "ask"
    return "ok", ""


def _read(case: Case, settings: Settings) -> tuple[Verdict, str]:
    try:
        return judge(case, statement.read_statements(case["text"], settings, TODAY))
    except ProviderUnavailable:
        return "miss", "unavailable"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="the code only, no network")
    options = parser.parse_args()
    found = cases()
    if options.check:
        failures = [(case["id"], reason) for case in found if (reason := check(case))]
        for case_id, reason in failures:
            print(f"FAIL {case_id}: {reason}")
        print(f"{len(found) - len(failures)}/{len(found)} cases read by code")
        return 1 if failures else 0
    settings = Settings()
    provider = settings.entry_parser_provider
    if not settings.ai_key(provider) or not settings.ai_model(
        provider, settings.openai_assistant_model
    ):
        print(f"no key or model for {provider}: the live gate needs the model, not the rules")
        return 2
    with ThreadPoolExecutor(max_workers=8) as pool:
        verdicts = list(pool.map(lambda case: _read(case, settings), found))
    for case, (verdict, reason) in zip(found, verdicts, strict=True):
        if verdict != "ok":
            print(f"{verdict.upper()} {case['id']}: {reason}")
    right = sum(verdict == "ok" for verdict, _ in verdicts)
    wrong = sum(verdict == "wrong" for verdict, _ in verdicts)
    rate = right / len(found)
    print(
        f"provider {settings.entry_parser_provider}: {right}/{len(found)} exact ({rate:.0%}), "
        f"{wrong} wrong"
    )
    return 0 if wrong == 0 and rate >= PASS_RATE else 1


if __name__ == "__main__":
    sys.exit(main())
