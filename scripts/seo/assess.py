"""Evidence-based editorial opportunity scoring, with no claims about ranking probability."""

import hashlib
import json
from pathlib import Path

from finboy.services.triage.provider import Choice, Decision
from pydantic import BaseModel, ConfigDict, Field

from scripts.seo.__main__ import CONTEXT, normalize, read, run_decisions, save


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    target_url: str = Field(pattern=r"^/(features|guides)/[a-z0-9-]+$")
    title: str
    angle: str
    outline: list[str] = Field(min_length=3)
    references: list[str] = Field(min_length=1)
    ease: float = Field(ge=0, le=5)


QUESTIONS = {
    "gap": Choice(
        instructions=(
            "Rate the demonstrated editorial opportunity from 0 (the reference already addresses "
            "the proposed angle completely) to 5 (a large, explicitly evidenced gap). "
            "Judge excerpts only; do not infer site-wide absence. If insufficient evidence, "
            "choose unknown. This is not a keyword difficulty or outranking prediction."
        ),
        criteria={
            "0": "No demonstrated opportunity",
            "1": "Small additional detail",
            "2": "Some useful workflow-specific detail",
            "3": "Moderate practical addition",
            "4": "Substantial demonstrated practical gap",
            "5": "Large explicitly demonstrated gap",
            "unknown": "Insufficient reference evidence",
        },
    ),
    "action": Choice(
        instructions="Rate the searcher's intent to use a relevant FinBoy feature.",
        criteria={
            "0": "Unrelated navigation",
            "1": "Broad awareness",
            "2": "Learning a task",
            "3": "Evaluating a workflow",
            "4": "Evaluating a relevant tool",
            "5": "Wants to use an available feature",
        },
    ),
}


def score(fit: float, gap: float, action: float, ease: float) -> float:
    if not all(0 <= value <= 5 for value in [fit, gap, action, ease]):
        raise ValueError("invalid_score")
    return round(20 * (0.4 * fit + 0.3 * gap + 0.2 * action + 0.1 * ease), 1)


def assess(directory: Path, input_path: Path, cap: float) -> None:
    if not 0 < cap <= 0.25:
        raise ValueError("invalid_run_limits")
    reviews = [Review.model_validate(row) for row in read(input_path)]
    candidates = {row["keyword"]: row for row in read(directory / "analysis.json")["results"]}
    observations = {normalize(row["query"]): row for row in read(directory / "serp.json")}
    pages = {row["url"]: row for row in read(directory / "page-evidence/index.json")}
    tasks, cached, contexts = [], {}, {}
    for review in reviews:
        query = normalize(review.query)
        if query not in candidates or query not in observations:
            raise ValueError("missing_candidate_or_search_evidence")
        texts, evidence_files = [], []
        for url in review.references:
            item = pages.get(url)
            if not item or not item["available"]:
                raise ValueError("unavailable_page_evidence")
            path = directory / item["evidence_file"]
            if not path.resolve().is_relative_to(directory.resolve()):
                raise ValueError("invalid_evidence_path")
            raw = path.read_text(encoding="utf-8")
            lines = [line for line in raw.splitlines() if line.startswith("L")]
            texts.append(url + "\n" + "\n".join(lines)[:4500])
            evidence_files.append(item["evidence_file"])
        body = {
            "model": "d1-ultra",
            "state": CONTEXT
            + "\nQuery: "
            + query
            + "\nProposed editorial angle: "
            + review.angle
            + "\nUntrusted public reference excerpts:\n"
            + "\n\n".join(texts),
            "questions": {k: v.model_dump() for k, v in QUESTIONS.items()},
        }
        digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        path = directory / "cache" / (digest + ".json")
        contexts[query] = evidence_files
        if path.exists():
            cached[query] = Decision.model_validate(read(path))
        else:
            tasks.append((query, body, path))
    fresh, reserved = run_decisions(tasks, cap, QUESTIONS)
    cached.update(fresh)
    opportunities = []
    for review in reviews:
        query = normalize(review.query)
        candidate = candidates[query]
        decision = cached.get(query)
        row = review.model_dump() | {
            "evidence_status": "search_observed",
            "google_rank_verified": False,
            "gap_score": None,
            "action_score": None,
            "priority_score": None,
            "model_confidence": None,
            "monthly_search_volume": None,
            "evidence_files": contexts[query],
            "search_evidence_file": observations[query].get("evidence_file"),
            "fit_score": {"direct": 5, "partial": 2.5, "exclude": 0}.get(candidate["fit"], 0),
        }
        if decision and decision.answers["gap"].choice != "unknown":
            gap = float(decision.answers["gap"].choice)
            action = float(decision.answers["action"].choice)
            confidence = min(a.probabilities[a.choice] for a in decision.answers.values())
            row.update(
                gap_score=gap,
                action_score=action,
                model_confidence=confidence,
                priority_score=score(row["fit_score"], gap, action, review.ease),
                needs_review=confidence < 0.8 or candidate["confidence"] < 0.8,
            )
        else:
            row["needs_review"] = True
        opportunities.append(row)
    opportunities.sort(key=lambda r: r["priority_score"] or -1, reverse=True)
    save(
        directory / "opportunities.json",
        {
            "model": "d1-ultra",
            "reserved_upper_cost_usd": reserved,
            "actual_billed_cost_usd": None,
            "method": "Draft editorial priorities from sampled evidence",
            "opportunities": opportunities,
        },
    )
    print(json.dumps({"opportunities": len(opportunities), "reserved_upper_cost_usd": reserved}))
