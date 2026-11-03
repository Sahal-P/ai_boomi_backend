"""Render research artifacts from captured observations and reviewed editorial angles."""

import csv
import html
from pathlib import Path
from urllib.parse import urlsplit

from scripts.seo.__main__ import csv_safe, read


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: csv_safe(v) for k, v in row.items()} for row in rows)


def render_bundle(directory: Path) -> None:
    path = directory / "opportunities.json"
    if not path.exists():
        return
    opportunities = read(path)["opportunities"]
    observations = read(directory / "serp.json")
    pages = read(directory / "page-evidence/index.json")
    google_path = directory / "google-observation.json"
    google = [read(google_path)] if google_path.exists() else []
    competitors = []
    for observation in observations + google:
        for result in observation["results"]:
            competitors.append(
                {
                    "query": observation["query"],
                    "domain": urlsplit(result["url"]).hostname,
                    "url": result["url"],
                    "title": result["title"],
                    "position": result["position"] if observation["ranking_verified"] else None,
                    "engine": observation["engine"],
                    "ranking_verified": observation["ranking_verified"],
                    "country_requested": observation.get("requested_country"),
                    "location_verified": observation.get("location_verified", False),
                    "observed_at": observation["observed_at"],
                    "evidence_file": observation.get("evidence_file"),
                    "evidence_url": observation.get("evidence_url"),
                }
            )
    write_csv(directory / "competitor-observations.csv", competitors)
    write_csv(directory / "opportunities.csv", opportunities)
    briefs = [
        "# FinBoy content briefs",
        "These are 20 editorial topic briefs. Several belong on the same page; consolidate "
        "them before publishing. Model scores are draft heuristics, with confidence retained. "
        "Additional guide URLs are a backlog, beyond the approved first four guides.",
    ]
    cards = []
    for index, row in enumerate(opportunities, 1):
        briefs.extend(
            [
                f"\n## {index}. {row['title']}",
                f"\nQuery: {row['query']}",
                f"\nRecommended URL: {row['target_url']}",
                f"\nAngle: {row['angle']}",
                f"\nDraft editorial score: {row['priority_score']}/100. "
                f"Model confidence: {row['model_confidence']}. "
                f"Needs review: {row['needs_review']}.",
                "\n### Suggested outline",
                *["- " + heading for heading in row["outline"]],
                "\n### Evidence",
                *["- " + url for url in row["references"]],
                "\nSearch evidence: " + str(row["search_evidence_file"]),
                "\nPage captures: " + ", ".join(row["evidence_files"]),
                "\n### Acceptance criteria",
                "- Use synthetic examples and the currently supported product workflow.",
                "- Link to the related feature page, pricing and privacy policy.",
                "- Make one supported action clear: sign in, add an entry or import a statement.",
                "- Verify instructions and feature availability against the current app.",
                "- Avoid unsupported bank sync, offline AI or guaranteed recognition/rankings.",
            ]
        )
        cards.append(
            "<article><h2>"
            + html.escape(row["title"])
            + "</h2><p>"
            + html.escape(row["angle"])
            + "</p><p>Target: "
            + html.escape(row["target_url"])
            + "</p><p>Draft score: "
            + str(row["priority_score"])
            + "/100; model confidence: "
            + str(round(row["model_confidence"] or 0, 3))
            + "; review required: "
            + str(row["needs_review"])
            + "</p></article>"
        )
    (directory / "content-briefs.md").write_text("\n".join(briefs), encoding="utf-8")
    summary = (
        f"# FinBoy research report\n\n{len(read(directory / 'analysis.json')['results'])} "
        f"candidate phrases classified; {len(observations)} queries sampled with Codex search; "
        f"{sum(len(o['results']) for o in observations)} result URLs captured.\n\n"
        f"{len(google)} Google desktop snapshot with {sum(len(o['results']) for o in google)} "
        f"observed organic positions. India requested; physical location not verified.\n\n"
        f"{len(pages)} reference pages; {sum(not p['available'] for p in pages)} unavailable. "
        f"{len(opportunities)} draft topic briefs scored using 40% fit, 30% sampled editorial gap, "
        "20% action intent and 10% publishing ease. All model uncertainty remains visible.\n\n"
        "Search-tool positions, volumes, traffic and authority metrics are unknown. Search results "
        "are not a complete competitor ranking database. Inspect raw captures before relying on "
        "individual recommendations. Competitors have substantive feature pages; this research "
        "does not demonstrate that generic category keywords are easy to win.\n\n"
        "## First release\n\nPublish the four supported feature pages and four practical guides. "
        "Explain actual correction/Undo workflows, supported statement formats, language support "
        "and coverage limits. Consolidate remaining briefs into an editorial backlog.\n"
    )
    (directory / "report.md").write_text(summary, encoding="utf-8")
    report_path = directory / "report.html"
    document = report_path.read_text(encoding="utf-8")
    document = document.replace(
        "</body>",
        "<section><h1>Draft content opportunities</h1><p>"
        "Scores are editorial heuristics. Low-confidence model assessments require review. "
        "They are not probabilities of ranking.</p>" + "".join(cards) + "</section></body>",
    )
    report_path.write_text(document, encoding="utf-8")
