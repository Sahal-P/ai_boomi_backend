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
from finboy.services.advisor import (
    coach,
    grounding,
    knowledge,
    memory,
    service,
    snapshot,
    summaries,
    tools,
)
from finboy.services.advisor.synthetic import NUDGE_DAY, SyntheticHousehold, make_store, nudges
from finboy.services.assistant.intent import rule_intent

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures" / "advisor"
STYLES = ("en", "hi", "hinglish", "ml", "manglish")
POLICIES = ("answer", "clarify", "decline")
SCRIPTS = {"hi": "ऀ-ॿ", "ml": "ഀ-ൿ"}
GATES = {
    "figures": 0.95,
    "policy": 0.95,
    "refusals": 1.0,
    "memory": 0.9,
    "script": 0.95,
    "sources": 0.9,
}
PLAN_FIELDS = (
    "calculation",
    "amount_rupees",
    "by_month",
    "months",
    "monthly_rupees",
    "annual_interest_percent",
)
RUNS = 3
# Phase 3: coach nudges the advisor words itself (the rest go out as written by code).
COACH_LANGUAGES = ("en", "hi", "ml")
COACH_GATE = 0.9
COACH_MEMORY = "Saving ₹40,000 for a bike by March 2027"
Case = dict[str, Any]


def cases() -> list[Case]:
    return json.loads((FIXTURES / "cases.json").read_text())


def available() -> set:
    """Every figure FinBoy can give the synthetic household: the snapshot, each tool's answers
    and the money guides."""
    box, today = SyntheticHousehold(), today_ist()
    ctx = tools.Context(today=today)
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
            texts.append(tools.run(box, name, json.dumps(arguments), ctx).output)
    this, last = blank | {"kind": "this_month"}, blank | {"kind": "last_month"}
    for metric, category in (("money_out", None), ("category", "food_dining")):
        arguments = {"metric": metric, "category": category, "first": last, "second": this}
        texts.append(tools.run(box, "compare", json.dumps(arguments), ctx).output)
    texts.extend(guide.body for guide in knowledge.library())
    return grounding.allowed(texts)


def _planned(case: Case) -> str | None:
    """The plan_numbers output a planning case expects, worked out from its own words."""
    plan = case["expect"].get("plan")
    if plan is None:
        return None
    said = " ".join(case.get("turns", []))
    numbers = {value for value, _ in grounding.figures(said)}
    ctx = tools.Context(
        today=today_ist(), said={int(value * 100) for value in numbers}, stated=numbers
    )
    arguments = {name: plan.get(name) for name in PLAN_FIELDS}
    return tools.run(SyntheticHousehold(), "plan_numbers", json.dumps(arguments), ctx).output


def check(found: list[Case]) -> list[str]:
    """Problems with the cases themselves; an empty list means the set is usable."""
    problems: list[str] = []
    sources = available()
    guides = {guide.id for guide in knowledge.library()}
    ids = [case["id"] for case in found]
    if len(ids) != len(set(ids)):
        problems.append("duplicate case IDs")
    for case in found:
        expect = case.get("expect", {})
        if case.get("language") not in STYLES or not case.get("turns"):
            problems.append(f"{case['id']}: language or turns")
        if expect.get("policy") not in POLICIES:
            problems.append(f"{case['id']}: policy")
        unknown = set(expect.get("sources", [])) - guides
        if unknown:
            problems.append(f"{case['id']}: no guide {', '.join(sorted(unknown))}")
        planned = _planned(case)
        if planned is not None and "error" in json.loads(planned):
            problems.append(f"{case['id']}: plan_numbers refuses it")
        figures = [*expect.get("figures", []), *expect.get("figures_any", [])]
        said = " ".join(case.get("turns", []))
        given = grounding.allowed([said, planned or ""])
        missing = grounding.unchecked(figures, sources | given)
        if missing:
            problems.append(f"{case['id']}: FinBoy cannot give {', '.join(missing)}")
        if expect.get("rules_decline") and rule_intent(case["turns"][-1]).intent != (
            "regulated_advice"
        ):
            problems.append(f"{case['id']}: the rules do not decline it")
    return problems


def check_coach() -> list[str]:
    """Phase 3: every code-written nudge fits a template parameter and a WhatsApp message, and
    quotes only its own facts (or its copy's fixed example)."""
    problems: list[str] = []
    for nudge in nudges():
        for language in COACH_LANGUAGES:
            words = coach.WORDS[language]
            line, message = coach.line(nudge, language), coach.message(nudge, language)
            if not 1 <= len(line) <= 1024 or re.search(r"[\n\t]| {5}", line):
                problems.append(f"coach {nudge.kind} {language}: not a template parameter")
            copy = [*words.COACH.values(), words.COACH_MOST, words.COACH_AHEAD]
            known = grounding.allowed([json.dumps(coach.facts(nudge), ensure_ascii=False), *copy])
            if grounding.unchecked([line, message], known):
                problems.append(f"coach {nudge.kind} {language}: a figure not in its facts")
            if len(message) > coach.MAX_NUDGE:
                problems.append(f"coach {nudge.kind} {language}: too long for a nudge")
    return problems


def live_coach(settings: Settings, runs: int) -> bool:
    """Phase 3: the model words every kind of nudge in each language `runs` times, with one
    saved memory; only kinds and languages are printed, never the words."""
    worded: list[bool] = []
    latencies: list[float] = []
    missed: dict[str, int] = defaultdict(int)
    store = make_store()
    with store() as session:
        memory.remember(session, LOCAL_USER_ID, "goal", COACH_MEMORY, "web", 300)
        session.commit()
        for nudge in nudges():
            for language in COACH_LANGUAGES:
                for _ in range(runs):
                    started = perf_counter()
                    result = coach.compose(
                        session, settings, LOCAL_USER_ID, nudge, language, NUDGE_DAY
                    )
                    latencies.append(perf_counter() - started)
                    worded.append(result.by == "advisor")
                    if result.by != "advisor":
                        missed[f"{nudge.kind}/{language}"] += 1
    rate = sum(worded) / len(worded) if worded else 0.0
    print(
        f"coach nudges {len(nudges())} kinds x {len(COACH_LANGUAGES)} languages x runs {runs}; "
        f"worded {rate:.1%} (gate {COACH_GATE:.0%})"
    )
    if latencies:
        ordered = sorted(latencies)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
        print(f"coach latency p50 {statistics.median(ordered):.2f}s p95 {p95:.2f}s")
    for key, count in sorted(missed.items()):
        print(f"  {key}: {count} sent as written by code")
    passed = rate >= COACH_GATE
    print("coach PASSED" if passed else "coach FAILED")
    return passed


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
        "sources": set(expect.get("sources", [])) <= {source.id for source in answer.sources},
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
            for gate in ("figures", "policy", "memory", "script", "sources"):
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
    print("advisor PASSED" if passed else "advisor FAILED")
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="validate cases without the model")
    parser.add_argument("--runs", type=int, default=RUNS)
    args = parser.parse_args(argv)
    found = cases()
    problems = check(found) + check_coach()
    counts = defaultdict(int)
    for case in found:
        counts[case["language"]] += 1
    print("cases:", ", ".join(f"{style} {counts[style]}" for style in STYLES))
    print(f"coach nudges: {len(nudges())} kinds x {len(COACH_LANGUAGES)} languages")
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
    # The phase 2 and 3 releases.
    released = {"advisor_enabled": True, "knowledge_enabled": True, "coach_enabled": True}
    advisor = live(found, settings.model_copy(update=released), args.runs)
    coached = live_coach(settings.model_copy(update=released), args.runs)
    print("PASSED" if advisor == 0 and coached else "FAILED")
    return 0 if advisor == 0 and coached else 1


if __name__ == "__main__":
    sys.exit(main())
