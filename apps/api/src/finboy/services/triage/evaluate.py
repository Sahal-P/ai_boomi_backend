"""The offline gate for d1-ultra (docs/triage-round/contract.md).

Synthetic diary messages, questions and pictures go through the same fast-path code the app uses.
`--check` needs no network: it answers every case the way a perfect d1-ultra would and confirms
the cases agree with the code. Without it, live d1-ultra answers each case `--runs` times (its
probabilities vary a little between calls), and every threshold is judged on all those answers.
Output names cases by ID only.
"""

import argparse
import json
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any

from finboy.core.clock import today_ist
from finboy.core.config import Settings
from finboy.core.languages import Language
from finboy.services.assistant.intent import _quick, rule_intent
from finboy.services.ingestion import screenshot
from finboy.services.triage import provider, service
from finboy.services.triage.service import Sorted
from finboy.services.whatsapp import cfo, statement

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures" / "triage"
# Hinglish and Manglish are switched on with Hindi and Malayalam.
GATE_LANGUAGE: dict[str, Language] = {
    "en": "en",
    "hi": "hi",
    "hinglish": "hi",
    "ml": "ml",
    "manglish": "ml",
}
THRESHOLDS = (0.8, 0.85, 0.9, 0.95)
IMAGE_THRESHOLDS = (0.9, 0.95, 0.98)
MAX_MISTAKE_RATE = 0.02
RUNS = 3
Case = dict[str, Any]


def cases() -> list[Case]:
    return json.loads((FIXTURES / "cases.json").read_text())


def may_be_fast(case: Case) -> bool:
    """Whether a sure d1-ultra may answer the case without the model."""
    return case["expect"] not in ("model", "money")


def ideal(case: Case) -> Sorted:
    """The answers a perfect d1-ultra would give."""

    def choice(option: str) -> provider.ChoiceAnswer:
        return provider.ChoiceAnswer(type="choice", choice=option, probabilities={option: 1.0})

    def yes(value: bool) -> provider.NoulAnswer:
        return provider.NoulAnswer(type="noul", noul=1.0 if value else 0.0)

    if case["route"] == "image":
        return Sorted({"image": choice(case["image"])})
    if case["route"] == "message":
        return Sorted(
            {
                "kind": choice(case["kind"]),
                "several": yes(case.get("why") == "several"),
                "payee": yes(case.get("why") == "payee"),
                "category": choice(case.get("category", "none")),
                "mode": choice(case.get("mode", "unknown")),
            }
        )
    return Sorted(
        {
            "intent": choice(case["intent"]),
            "topic": choice(case.get("topic", "none")),
            "category": choice(case.get("category", "none")),
            "merchant": yes(case.get("merchant", False)),
        }
    )


def judge(case: Case, sort: Sorted | None, today: date) -> tuple[str, str | None]:
    """How a case was answered ("fast", "model" or "unavailable") and the mistake, if any:
    "route" (answered fast when it must not be, or the wrong kind or intent), "amount" or
    "detail" (category, mode, day, check-up or topic)."""
    if sort is None:
        return "unavailable", None
    expect = case["expect"]
    if case["route"] == "image":
        if sort.pick("image", service.IMAGE_SURE) != "other":
            return "model", None
        return "fast", "route" if expect == "money" else None
    if case["route"] == "message":
        answer = statement._fast(sort, statement.mask(case["text"]), today)
        got: object = answer[0] if answer and len(answer) == 1 else answer
    else:
        got = _quick(sort, case["text"], rule_intent(case["text"]))
    if got is None:
        return "model", None
    if expect == "model" or isinstance(got, list):
        return "fast", "route"
    for field, wanted in expect.items():
        if field == "day_offset":
            if getattr(got, "day", None) != today + timedelta(days=wanted):
                return "fast", "detail"
        elif getattr(got, field) != wanted:
            mistake = {"kind": "route", "intent": "route", "amount_minor": "amount"}
            return "fast", mistake.get(field, "detail")
    return "fast", None


def check() -> list[str]:
    """Cases that disagree with the code even when d1-ultra answers perfectly, or that d1-ultra
    would never see because a rule answers them first."""
    problems: list[str] = []
    today = today_ist()
    for case in cases():
        if case["route"] == "image":
            if not (FIXTURES / "images" / case["file"]).is_file():
                problems.append(f"{case['id']}: missing image")
            continue
        text = case["text"]
        if case["route"] == "message" and (
            (statement.QUESTION.search(text) and not statement.BANK_SMS.search(text))
            or cfo.asked(text)
        ):
            problems.append(f"{case['id']}: answered by a rule before d1-ultra")
        if case["route"] == "question" and rule_intent(text).intent == "regulated_advice":
            problems.append(f"{case['id']}: declined by a rule before d1-ultra")
        how, mistake = judge(case, ideal(case), today)
        wanted = "model" if case["expect"] == "model" else "fast"
        if how != wanted or mistake:
            problems.append(f"{case['id']}: {how} {mistake or ''}".strip())
    return problems


def sort_case(case: Case, settings: Settings) -> tuple[Sorted | None, float]:
    if case["route"] == "image":
        data = (FIXTURES / "images" / case["file"]).read_bytes()
        jpeg = screenshot.preview(screenshot.sanitize(data, "image/png", settings), settings)
        started = perf_counter()
        sort = service.sort_image(jpeg, settings)
    elif case["route"] == "message":
        language = GATE_LANGUAGE[case["language"]]
        started = perf_counter()
        sort = service.sort_message(statement.mask(case["text"]), language, settings)
    else:
        language = GATE_LANGUAGE[case["language"]]
        started = perf_counter()
        sort = service.sort_question(case["text"], language, settings)
    return sort, (perf_counter() - started) * 1000


def report(
    results: list[tuple[Case, Sorted | None]], sure: float, clear_no: float, image_sure: float
) -> dict:
    """Per language (and for pictures): answers given fast, by the model or not at all, the fast
    share of answers that may be fast, mistakes by case ID, and whether the gate passes."""
    previous = service.SURE, service.CLEAR_NO, service.IMAGE_SURE
    service.SURE, service.CLEAR_NO, service.IMAGE_SURE = sure, clear_no, image_sure
    today = today_ist()
    groups: dict[str, dict[str, Any]] = {}
    try:
        for case, sort in results:
            name = "images" if case["route"] == "image" else GATE_LANGUAGE[case["language"]]
            group = groups.setdefault(
                name,
                {
                    "answers": 0,
                    "may_be_fast": 0,
                    "fast": 0,
                    "model": 0,
                    "unavailable": 0,
                    "mistakes": [],
                },
            )
            how, mistake = judge(case, sort, today)
            group["answers"] += 1
            group["may_be_fast"] += may_be_fast(case)
            group[how] += 1
            if mistake:
                blocking = not may_be_fast(case) or case.get("strict", False) or mistake == "amount"
                group["mistakes"].append(
                    {"id": case["id"], "mistake": mistake, "blocking": blocking}
                )
    finally:
        service.SURE, service.CLEAR_NO, service.IMAGE_SURE = previous
    for group in groups.values():
        group["fast_share"] = (
            round(group["fast"] / group["may_be_fast"], 2) if group["may_be_fast"] else None
        )
        group["mistake_rate"] = round(len(group["mistakes"]) / group["answers"], 3)
        group["passed"] = not any(m["blocking"] for m in group["mistakes"]) and (
            group["mistake_rate"] <= MAX_MISTAKE_RATE
        )
    return groups


def evaluate(settings: Settings, runs: int = RUNS) -> dict:
    settings = settings.model_copy(
        update={"triage_enabled": True, "triage_languages": ["en", "hi", "ml"]}
    )
    all_cases = cases()
    jobs = all_cases * runs
    with ThreadPoolExecutor(max_workers=4) as pool:
        sorted_ = list(pool.map(lambda case: sort_case(case, settings), jobs))
    latencies = sorted(ms for sort, ms in sorted_ if sort is not None)
    results = [(case, sort) for case, (sort, _) in zip(jobs, sorted_, strict=True)]
    return {
        "model": settings.liquid_decision_model,
        "cases": len(all_cases),
        "runs": runs,
        "latency_ms": {
            "p50": round(statistics.median(latencies)) if latencies else None,
            "p95": round(latencies[int(0.95 * (len(latencies) - 1))]) if latencies else None,
        },
        # The yes/no threshold stays at the app's value; it guards payees and several items.
        "by_threshold": {
            f"sure={sure} image_sure={image_sure}": report(
                results, sure, service.CLEAR_NO, image_sure
            )
            for sure in THRESHOLDS
            for image_sure in IMAGE_THRESHOLDS
        },
        "gate": report(results, service.SURE, service.CLEAR_NO, service.IMAGE_SURE),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Check the cases against the code; no network"
    )
    parser.add_argument("--runs", type=int, default=RUNS, help="Live answers per case")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    if args.check:
        problems = check()
        print(json.dumps({"cases": len(cases()), "problems": problems}, indent=2))
        return 1 if problems else 0
    settings = Settings()
    if settings.liquid_api_key is None or settings.liquid_decision_model not in provider.MODELS:
        print(json.dumps({"error": "Set LIQUID_API_KEY and LIQUID_DECISION_MODEL=d1-ultra"}))
        return 2
    result = evaluate(settings, args.runs)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    gate = result["gate"]
    enabled = {*settings.triage_languages, "images"}
    return 0 if all(group["passed"] for name, group in gate.items() if name in enabled) else 1


if __name__ == "__main__":
    sys.exit(main())
