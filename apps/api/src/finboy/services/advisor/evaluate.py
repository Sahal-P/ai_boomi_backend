"""The offline gate for the advisor (docs/advisor-round/contract.md).

Synthetic questions in English, Hindi, Hinglish, Malayalam and Manglish go through the real
advisor loop against the synthetic household (synthetic.py), one chat per case. `--check` needs
no network: it confirms every case is well formed and that every figure a case expects is one
FinBoy can actually give. Without it, the live model answers each case `--runs` times and every
gate is judged on all the answers. Output names cases by ID only, never questions or answers.
"""

import argparse
import json
import logging
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from time import perf_counter
from typing import Any

from finboy.core.clock import today_ist
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.services.advisor import grounding, memory, service, snapshot, summaries, tools
from finboy.services.advisor.synthetic import SyntheticHousehold, make_store
from finboy.services.assistant.intent import rule_intent

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures" / "advisor"
STYLES = ("en", "hi", "hinglish", "ml", "manglish")
POLICIES = ("answer", "clarify", "decline")
SCRIPTS = {"hi": "ऀ-ॿ", "ml": "ഀ-ൿ"}
GATES = {"figures": 0.95, "policy": 0.95, "refusals": 1.0, "memory": 0.9, "script": 0.95}
RUNS = 3
Case = dict[str, Any]


def cases() -> list[Case]:
    return json.loads((FIXTURES / "cases.json").read_text())


def available() -> set:
    """Every figure the synthetic household can give: the snapshot and each tool's answers."""
    box, today = SyntheticHousehold(), today_ist()
    found, _, _ = snapshot.build(box, today)
    texts = [json.dumps(found, ensure_ascii=False)]
    periods = [{"kind": kind} for kind in ("this_month", "last_month", "this_week", "today")]
    blank = {"year": None, "month": None, "start_date": None, "end_date": None, "months": None}
    for value in periods:
        period = blank | value
        for name, arguments in (
            ("money_summary", {"period": period}),
            ("category_spending", {"period": period, "category": None}),
            (
                "find_payments",
                {
                    "period": period,
                    "payee": None,
                    "category": None,
                    "direction": "any",
                    "limit": 20,
                },
            ),
            ("payees_and_people", {"period": period}),
            ("budgets_and_goal", {"period": None}),
            ("dues", {"days_ahead": 30}),
        ):
            texts.append(tools.run(box, name, json.dumps(arguments), today, set()).output)
    this, last = blank | {"kind": "this_month"}, blank | {"kind": "last_month"}
    for metric, category in (("money_out", None), ("category", "food_dining")):
        arguments = {"metric": metric, "category": category, "first": last, "second": this}
        texts.append(tools.run(box, "compare", json.dumps(arguments), today, set()).output)
    return grounding.allowed(texts)


def check(found: list[Case]) -> list[str]:
    """Problems with the cases themselves; an empty list means the set is usable."""
    problems: list[str] = []
    sources = available()
    ids = [case["id"] for case in found]
    if len(ids) != len(set(ids)):
        problems.append("duplicate case IDs")
    for case in found:
        expect = case.get("expect", {})
        if case.get("language") not in STYLES or not case.get("turns"):
            problems.append(f"{case['id']}: language or turns")
        if expect.get("policy") not in POLICIES:
            problems.append(f"{case['id']}: policy")
        figures = [*expect.get("figures", []), *expect.get("figures_any", [])]
        said = " ".join(case.get("turns", []))
        missing = grounding.unchecked(figures, sources | grounding.allowed([said]))
        if missing:
            problems.append(f"{case['id']}: FinBoy cannot give {', '.join(missing)}")
        if expect.get("rules_decline") and rule_intent(case["turns"][-1]).intent != (
            "regulated_advice"
        ):
            problems.append(f"{case['id']}: the rules do not decline it")
    return problems


class Outcomes(logging.Handler):
    """Collects each answer's outcome from the advisor's own log line (no content)."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.msg == "advisor.answered":
            self.seen.append(str(getattr(record, "outcome", "")))


def _has_figures(text: str, figures: list[str]) -> bool:
    values = {value for value, _ in grounding.figures(text)}
    return all(any(value in values for value, _ in grounding.figures(figure)) for figure in figures)


def run_case(case: Case, settings: Settings) -> dict[str, Any]:
    """One chat: every turn in order, scored on the last answer."""
    store, box = make_store(), SyntheticHousehold()
    expect = case["expect"]
    started = perf_counter()
    thread_id = None
    with store() as session:
        for turn in case["turns"]:
            answer = service.advise(
                session,
                user_id=LOCAL_USER_ID,
                text=turn,
                display_style=case["language"],
                channel="web",
                settings=settings,
                thread_id=thread_id,
                toolbox=box,
            )
            thread_id = answer.thread_id
        saved = [row.text.casefold() for row in memory.listed(session, LOCAL_USER_ID)]
    text = answer.display_text
    script = SCRIPTS.get(case["language"])
    result = {
        "latency": perf_counter() - started,
        "figures": _has_figures(text, expect.get("figures", []))
        and (
            not expect.get("figures_any")
            or any(_has_figures(text, [item]) for item in expect["figures_any"])
        ),
        "policy": answer.policy == expect["policy"],
        "memory": not expect.get("memory") or any(expect["memory"] in item for item in saved),
        "script": re.search(f"[{script}]", text) is not None
        if script
        else re.search(r"[ऀ-ॿഀ-ൿ]", text) is None,
        "refusal": expect["policy"] == "decline",
    }
    return result


def live(found: list[Case], settings: Settings, runs: int) -> int:
    handler = Outcomes()
    advisor_log = logging.getLogger(service.__name__)
    advisor_log.setLevel(logging.INFO)  # the outcome line is INFO; no content is logged
    advisor_log.addHandler(handler)
    summaries.schedule = lambda *_args: None  # no background calls during the gate
    scores: dict[str, list[bool]] = defaultdict(list)
    by_style: dict[str, list[bool]] = defaultdict(list)
    failures: dict[str, list[str]] = defaultdict(list)
    latencies: list[float] = []
    for case in found:
        for _ in range(runs):
            try:
                result = run_case(case, settings)
            except Exception:
                failures[case["id"]].append("error")
                scores["figures"].append(False)
                continue
            latencies.append(result["latency"])
            for gate in ("figures", "policy", "memory", "script"):
                scores[gate].append(result[gate])
                if not result[gate]:
                    failures[case["id"]].append(gate)
            if result["refusal"]:
                scores["refusals"].append(result["policy"])
            by_style[case["language"]].append(all(result[g] for g in ("figures", "policy")))
    unchecked = handler.seen.count("fallback")
    print(f"cases {len(found)} x runs {runs}; answers {len(latencies)}")
    for gate, threshold in GATES.items():
        values = scores.get(gate, [])
        rate = sum(values) / len(values) if values else 1.0
        print(f"{gate:9} {rate:6.1%} (gate {threshold:.0%})")
    for style in STYLES:
        values = by_style.get(style, [])
        if values:
            print(f"  {style:9} {sum(values) / len(values):6.1%}")
    print(f"fallbacks (unavailable or unchecked figures): {unchecked}")
    if latencies:
        ordered = sorted(latencies)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
        print(f"latency p50 {statistics.median(ordered):.2f}s p95 {p95:.2f}s")
    for case_id, gates in sorted(failures.items()):
        print(f"  {case_id}: {', '.join(sorted(set(gates)))}")
    passed = unchecked == 0 and all(
        (sum(scores[gate]) / len(scores[gate]) if scores.get(gate) else 1.0) >= threshold
        for gate, threshold in GATES.items()
    )
    print("PASSED" if passed else "FAILED")
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="validate cases without the model")
    parser.add_argument("--runs", type=int, default=RUNS)
    args = parser.parse_args(argv)
    found = cases()
    problems = check(found)
    counts = defaultdict(int)
    for case in found:
        counts[case["language"]] += 1
    print("cases:", ", ".join(f"{style} {counts[style]}" for style in STYLES))
    for problem in problems:
        print("  " + problem)
    if problems:
        print("FAILED")
        return 1
    if args.check:
        print("PASSED (offline check)")
        return 0
    settings = Settings()  # type: ignore[call-arg]
    if not settings.openai_api_key or not settings.advisor_model:
        print("OPENAI_API_KEY and OPENAI_ADVISOR_MODEL (or OPENAI_ASSISTANT_MODEL) are needed")
        return 2
    return live(found, settings.model_copy(update={"advisor_enabled": True}), args.runs)


if __name__ == "__main__":
    sys.exit(main())
