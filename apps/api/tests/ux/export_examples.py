"""Generate synthetic contract examples through real HTTP and disposable PostgreSQL.

Run explicitly; this is not a production seed, provider evaluation or normal test.
"""

import json
from pathlib import Path

from finboy.services.imports.files import DEMO_DIRECTORY
from pytest import MonkeyPatch
from test_trust_postgres import ux


def main() -> None:
    with MonkeyPatch.context() as monkeypatch:
        fixture = ux.__wrapped__(monkeypatch)
        client, _factory, _user_id = next(fixture)
        try:

            def get(path: str) -> dict:
                result = client.get("/api/v1" + path)
                result.raise_for_status()
                return result.json()

            def post(path: str, body: dict) -> dict:
                result = client.post("/api/v1" + path, json=body)
                result.raise_for_status()
                return result.json()

            def version() -> str:
                return get("/money/summary")["data_version"]

            paths = sorted(DEMO_DIRECTORY.glob("*.eml"))
            started = client.post(
                "/api/v1/imports/eml",
                files=[
                    ("files", (path.name, path.read_bytes(), "message/rfc822")) for path in paths
                ],
            )
            started.raise_for_status()
            run_id = started.json()["import_run_id"]
            page = get("/transactions/page?scope=unresolved&limit=3")
            selected = page["items"][0]["id"]
            obligation = get("/money/obligations")["items"][0]["id"]
            examples = {
                "_provenance": (
                    "All fields are synthetic. Captured from real HTTP, rules extraction "
                    "and guarded disposable PostgreSQL. No live provider success is claimed."
                ),
                "demo": get("/demo"),
                "summary": get("/money/summary"),
                "transaction_page": page,
                "filtered_empty": get("/transactions/page?scope=unresolved&q=does-not-match"),
                "transaction_detail": get("/transactions/" + selected),
                "merge_candidates": get("/transactions/" + selected + "/merge-candidates"),
                "obligations": get("/money/obligations"),
                "obligation_detail": get("/money/obligations/" + obligation),
                "import_started": started.json(),
                "import_status": get("/imports/" + run_id),
                "import_history": get("/imports?limit=3"),
                "import_issues": get("/imports/" + run_id + "/issues"),
                "isolation": get("/privacy/isolation"),
            }
            decision = {
                "expected_version": version(),
                "action": "confirm",
                "correction": {"merchant": "Sample reviewed merchant", "amount_minor": 50000},
            }
            examples["decision_request"] = decision
            examples["decision_preview"] = post(
                "/transactions/" + selected + "/decision-preview", decision
            )
            examples["decision_result"] = post("/transactions/" + selected + "/decisions", decision)
            result = examples["decision_result"]
            undo = {"expected_version": result["data_version"]}
            examples["undo_request"] = undo
            examples["undo_result"] = post(
                "/transactions/" + selected + "/decisions/" + result["decision_id"] + "/undo", undo
            )
            for style in ("en", "hi", "ml", "hinglish", "manglish"):
                examples["assistant_" + style] = post(
                    "/assistant/ask",
                    {"text": "How much did I spend on Amazon this month?", "display_style": style},
                )
            examples["assistant_period_clarification"] = post(
                "/assistant/ask", {"text": "How much did I spend last week?", "display_style": "en"}
            )
            examples["simulation"] = post(
                "/money/simulations",
                {"monthly_amount_minor": 500000, "label": "Sample monthly proposal"},
            )
            examples["deletion_preview"] = post("/privacy/deletion-preview", {})
            examples["structured_export"] = post("/privacy/export", {"expected_version": version()})
            examples["task_outcome"] = post(
                "/privacy/task-outcomes", {"task": "evidence_opened", "subject_id": selected}
            )
            target = (
                Path(__file__).resolve().parents[4] / "docs/ux-round/fixtures/actual-http-v1.json"
            )
            target.write_text(json.dumps(examples, indent=2, ensure_ascii=False) + "\n")
        finally:
            next(fixture, None)
    print("Published synthetic HTTP contract examples; temporary user cleaned up.")


if __name__ == "__main__":
    main()
