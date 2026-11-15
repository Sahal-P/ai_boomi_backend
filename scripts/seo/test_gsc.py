"""Focused tests for private Search Console imports and comparison reports."""

import csv
import json
from pathlib import Path

import pytest

from scripts.seo.__main__ import report, save
from scripts.seo.gsc import import_gsc


def export(path: Path, header: str, rows: list[list[str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([header, "Clicks", "Impressions", "CTR", "Position"])
        writer.writerows(rows)
    return path


def run_import(
    directory: Path,
    queries: Path,
    pages: Path | None,
    start: str,
    end: str,
    *,
    country: str = "IN",
    device: str = "all",
) -> None:
    import_gsc(queries, pages, directory, start, end, country, device, "web")


def test_import_and_comparison_preserve_missing_and_separate_dimensions(tmp_path):
    old = export(
        tmp_path / "old.csv",
        "Top queries",
        [["finboy", "1", "4", "25%", "2.1"], ["vanished", "0", "3", "0%", "0"]],
    )
    new = export(
        tmp_path / "new.csv",
        "Top queries",
        [["finboy", "2", "7", "28.6%", "1.8"], ["new query", "0", "6", "0%", "10"]],
    )
    pages = export(
        tmp_path / "pages.csv", "Top pages", [["https://finboy.io/", "2", "10", "20%", "3"]]
    )
    output = tmp_path / "private"
    run_import(output, old, None, "2026-01-01", "2026-01-07")
    run_import(output, new, pages, "2026-01-08", "2026-01-14")
    with (output / "gsc-report.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    lookup = {(row["dimension"], row["value"]): row for row in rows}
    assert lookup["query", "finboy"]["change_impressions"] == "3"
    assert lookup["query", "new query"]["previous_impressions"] == ""
    assert lookup["query", "vanished"]["current_impressions"] == ""
    assert lookup["page", "https://finboy.io/"]["previous_clicks"] == ""
    markdown = (output / "gsc-report.md").read_text()
    assert "Compared with 2026-01-01 to 2026-01-07" in markdown
    assert "Branded visible queries (rule-matched) | 2 | 7 | 1 | 4" in markdown
    assert lookup["group", "Branded visible queries (rule-matched)"]["change_clicks"] == "1"
    assert "## Pages" in markdown and "https://finboy.io/" in markdown
    snapshot = json.loads((output / "gsc" / "2026-01-01_2026-01-07_IN_all_web.json").read_text())
    assert snapshot["queries"][1]["average_position"] is None
    assert len(snapshot["sources"]["queries"]["sha256"]) == 64
    assert snapshot["source_kind"] == "gsc-export"


def test_only_same_filters_and_equal_nonoverlapping_periods_are_compared(tmp_path):
    q = export(tmp_path / "queries.csv", "Top queries", [["finboy", "1", "4", "25%", "2"]])
    run_import(tmp_path, q, None, "2026-01-01", "2026-01-07", device="desktop")
    run_import(tmp_path, q, None, "2026-01-08", "2026-01-14", device="mobile")
    assert "changes are unknown" in (tmp_path / "gsc-report.md").read_text()
    run_import(tmp_path, q, None, "2026-01-15", "2026-01-20", device="mobile")
    assert "changes are unknown" in (tmp_path / "gsc-report.md").read_text()
    run_import(tmp_path, q, None, "2026-01-15", "2026-01-21", device="mobile")
    assert "Compared with 2026-01-08 to 2026-01-14" in (tmp_path / "gsc-report.md").read_text()
    assert "mobile" in (tmp_path / "gsc-report.md").read_text()


def test_html_and_csv_escape_untrusted_query_text(tmp_path):
    q = export(
        tmp_path / "queries.csv",
        "Top queries",
        [
            ['=HYPERLINK("https://bad.example")', "0", "1", "0%", "8"],
            ["<script>alert(1)</script>", "0", "1", "0%", "2"],
        ],
    )
    run_import(tmp_path, q, None, "2026-01-01", "2026-01-07")
    html = (tmp_path / "gsc-report.html").read_text()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    with (tmp_path / "gsc-report.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert any(row["value"].startswith("'=HYPERLINK") for row in rows)
    assert "&lt;script&gt;" in (tmp_path / "gsc-report.md").read_text()


def test_validation_rejects_bad_context_foreign_pages_and_changed_snapshot(tmp_path):
    q = export(tmp_path / "queries.csv", "Top queries", [["finboy", "1", "2", "50%", "1"]])
    pages = export(
        tmp_path / "pages.csv", "Top pages", [["https://elsewhere.example/", "0", "1", "0%", "2"]]
    )
    with pytest.raises(ValueError, match="page_outside_property"):
        run_import(tmp_path, q, pages, "2026-01-01", "2026-01-07")
    with pytest.raises(ValueError, match="invalid_date"):
        run_import(tmp_path, q, None, "2026-01-07", "2026-01-01")
    with pytest.raises(ValueError, match="invalid_country"):
        run_import(tmp_path, q, None, "2026-01-01", "2026-01-07", country="India")
    run_import(tmp_path, q, None, "2026-01-01", "2026-01-07")
    q.write_text("Top queries,Clicks,Impressions\nfinboy,2,3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="period_already_imported"):
        run_import(tmp_path, q, None, "2026-01-01", "2026-01-07")
    import_gsc(q, None, tmp_path, "2026-01-01", "2026-01-07", "IN", "all", "web", replace=True)
    archived = list((tmp_path / "gsc-history").glob("*.json"))
    assert len(archived) == 1
    assert json.loads(archived[0].read_text())["queries"][0]["clicks"] == 1


def test_rejects_malformed_and_duplicate_queries(tmp_path):
    q = export(
        tmp_path / "queries.csv", "Top queries", [["finboy", "not-a-number", "1", "0%", "1"]]
    )
    with pytest.raises(ValueError, match="invalid_metric"):
        run_import(tmp_path, q, None, "2026-01-01", "2026-01-07")
    q = export(
        tmp_path / "queries.csv",
        "Top queries",
        [["FinBoy", "1", "1", "100%", "1"], ["finboy", "1", "1", "100%", "1"]],
    )
    with pytest.raises(ValueError, match="duplicate_csv_key"):
        run_import(tmp_path, q, None, "2026-01-01", "2026-01-07")
    q.write_text('Top queries,Clicks,Impressions\n"unclosed,0,2\n', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid_csv"):
        run_import(tmp_path, q, None, "2026-01-01", "2026-01-07")


def test_browser_transcription_requires_and_hashes_its_evidence(tmp_path):
    q = export(tmp_path / "queries.csv", "Top queries", [["finboy", "1", "1", "100%", "1"]])
    with pytest.raises(ValueError, match="missing_evidence"):
        import_gsc(
            q,
            None,
            tmp_path,
            "2026-01-01",
            "2026-01-07",
            "IN",
            "all",
            "web",
            "browser-transcription",
        )
    evidence = tmp_path / "capture.txt"
    evidence.write_text("Search Console screenshot transcription", encoding="utf-8")
    import_gsc(
        q,
        None,
        tmp_path,
        "2026-01-01",
        "2026-01-07",
        "IN",
        "all",
        "web",
        "browser-transcription",
        evidence,
    )
    snapshot = json.loads((tmp_path / "gsc" / "2026-01-01_2026-01-07_IN_all_web.json").read_text())
    assert snapshot["source_kind"] == "browser-transcription"
    assert len(snapshot["sources"]["queries"]["evidence"]["sha256"]) == 64


def test_main_report_links_to_search_console_report(tmp_path):
    q = export(tmp_path / "queries.csv", "Top queries", [["finboy", "1", "1", "100%", "1"]])
    run_import(tmp_path, q, None, "2026-01-01", "2026-01-07")
    save(
        tmp_path / "analysis.json",
        {
            "results": [
                {"keyword": "finboy", "fit": "direct", "intent": "navigational", "confidence": 0.9}
            ]
        },
    )
    report(tmp_path)
    assert 'href="gsc-report.html"' in (tmp_path / "report.html").read_text()
    assert "(gsc-report.md)" in (tmp_path / "report.md").read_text()
