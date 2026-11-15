"""Render private, provenance-aware Search Console reports."""

import csv
import html
import re
from datetime import date
from pathlib import Path

from scripts.seo.__main__ import csv_safe, read

LIMITS = (
    "Query rows may omit anonymized or truncated searches. Counts below sum only provided "
    "visible rows, not all searches. Google may export unavailable values as zero. Query and page "
    "tables have different aggregation and cannot be joined into query-page pairs. "
    "Average position is a Search Console aggregate, not a verified search-result rank."
)


def _brand(query: str) -> bool:
    return re.search(r"(?<![a-z0-9])fin\s*boy(?![a-z0-9])", query.casefold()) is not None


def _sum(rows: list[dict], field: str) -> int | None:
    values = [row[field] for row in rows]
    return sum(values) if all(value is not None for value in values) else None


def _same_context(a: dict, b: dict) -> bool:
    fields = ("property", "country", "device", "search_type")
    return all(a[field] == b[field] for field in fields)


def _duration(context: dict) -> int:
    return (
        date.fromisoformat(context["end_date"]) - date.fromisoformat(context["start_date"])
    ).days + 1


def _md(value: object) -> str:
    text = "unknown" if value is None else str(value)
    return html.escape(text).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _index(items: list[dict] | None, dimension: str) -> dict:
    return {
        (item["key"].casefold() if dimension == "query" else item["key"]): item
        for item in items or []
    }


def render_gsc(directory: Path) -> bool:
    folder = directory / "gsc"
    snapshots = [read(path) for path in folder.glob("*.json")] if folder.exists() else []
    if not snapshots:
        return False
    selected_path = directory / "gsc-context.json"
    if selected_path.exists():
        selected = read(selected_path)
        snapshots = [item for item in snapshots if _same_context(selected, item["context"])]
    if not snapshots:
        raise ValueError("missing_selected_context")
    snapshots.sort(key=lambda item: (item["context"]["end_date"], item["context"]["start_date"]))
    current = snapshots[-1]
    context = current["context"]
    earlier = [
        item
        for item in snapshots[:-1]
        if _same_context(context, item["context"])
        and item["context"]["end_date"] < context["start_date"]
        and _duration(item["context"]) == _duration(context)
    ]
    previous = earlier[-1] if earlier else None
    rows = []
    for dimension, field in (("query", "queries"), ("page", "pages")):
        current_data = current[field]
        previous_data = previous[field] if previous else None
        if current_data is None and previous_data is None:
            continue

        now, before = _index(current_data, dimension), _index(previous_data, dimension)
        for key in sorted(set(now) | set(before)):
            c, p = now.get(key), before.get(key)
            display = (c or p)["key"]
            line = {
                "dimension": dimension,
                "value": display,
                "query_group": ("brand match" if _brand(display) else "unmatched")
                if dimension == "query"
                else "",
            }
            for metric in ("clicks", "impressions", "average_position"):
                line[f"current_{metric}"] = c[metric] if c else None
                line[f"previous_{metric}"] = p[metric] if p else None
                if metric != "average_position":
                    line[f"change_{metric}"] = (
                        c[metric] - p[metric]
                        if c and p and c[metric] is not None and p[metric] is not None
                        else None
                    )
            rows.append(line)
    grouped = []
    for title, matched in (
        ("Branded visible queries (rule-matched)", True),
        ("Non-branded visible queries (unmatched)", False),
    ):
        current_group = [r for r in current["queries"] if _brand(r["key"]) == matched]
        previous_group = (
            [r for r in previous["queries"] if _brand(r["key"]) == matched] if previous else None
        )
        row = {"dimension": "group", "value": title, "query_group": ""}
        for metric in ("clicks", "impressions"):
            now = _sum(current_group, metric)
            before = _sum(previous_group, metric) if previous_group is not None else None
            row[f"current_{metric}"] = now
            row[f"previous_{metric}"] = before
            row[f"change_{metric}"] = (
                now - before if now is not None and before is not None else None
            )
        row["current_average_position"] = None
        row["previous_average_position"] = None
        grouped.append(row)
        rows.append(row)
    csv_path = directory / "gsc-report.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "dimension",
            "value",
            "query_group",
            "current_clicks",
            "previous_clicks",
            "change_clicks",
            "current_impressions",
            "previous_impressions",
            "change_impressions",
            "current_average_position",
            "previous_average_position",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: csv_safe(value) for key, value in row.items()} for row in rows)
    period = (
        f"{context['start_date']} to {context['end_date']} · {context['country']} · "
        f"{context['device']} · {context['search_type']}"
    )
    comparison = (
        f"Compared with {previous['context']['start_date']} to {previous['context']['end_date']} "
        f"({previous['source_kind']})."
        if previous
        else "No equal-length, non-overlapping earlier period with the same filters was "
        "available; changes are unknown."
    )
    summary = [
        "# Search Console performance",
        "",
        _md(period),
        "",
        "Source: " + _md(current["source_kind"]) + ".",
        "",
        comparison,
        "",
        LIMITS,
        "",
        "The brand rule only matches 'finboy' and 'fin boy'; other spellings can appear "
        "among unmatched queries. Context is operator-supplied and must match the export filters.",
        "",
        "| Visible query group | Clicks | Impressions | Previous clicks | Previous impressions |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    fields = (
        "value",
        "current_clicks",
        "current_impressions",
        "previous_clicks",
        "previous_impressions",
    )
    summary.extend("| " + " | ".join(_md(row[key]) for key in fields) + " |" for row in grouped)
    parts = [
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width">'
        "<title>FinBoy Search Console performance</title><style>"
        "body{font:16px system-ui;margin:2rem auto;padding:0 1rem;max-width:1100px;color:#18202b}"
        "table{width:100%;border-collapse:collapse}"
        "td,th{padding:.6rem;text-align:left;border-bottom:1px solid #ddd}"
        "</style><body>",
        f"<h1>Search Console performance</h1><p>{html.escape(period)}</p>"
        f"<p>Source: {html.escape(current['source_kind'])}.</p>"
        f"<p>{html.escape(comparison)}</p><p>{html.escape(LIMITS)}</p>"
        "<p>Brand match means finboy or fin boy. Other spellings can be in unmatched queries. "
        "Context is operator-supplied.</p>",
        "<table><thead><tr><th>Visible query group</th><th>Clicks</th>"
        "<th>Impressions</th><th>Previous clicks</th><th>Previous impressions</th>"
        "</tr></thead><tbody>",
    ]
    for row in grouped:
        parts.append(
            "<tr>"
            + "".join(
                "<td>" + html.escape(str(value) if value is not None else "unknown") + "</td>"
                for value in (row[key] for key in fields)
            )
            + "</tr>"
        )
    parts.append("</tbody></table>")
    for dimension, label in (("query", "Queries"), ("page", "Pages")):
        selected_rows = [row for row in rows if row["dimension"] == dimension]
        selected_rows.sort(key=lambda row: -(row["current_impressions"] or 0))
        summary.extend(
            [
                "",
                f"## {label}",
                "",
                "| Item | Clicks | Impressions | Previous clicks | Previous impressions |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        parts.append(
            f"<h2>{label}</h2><table><thead><tr><th>Item</th><th>Clicks</th>"
            "<th>Impressions</th><th>Previous clicks</th><th>Previous impressions</th>"
            "</tr></thead><tbody>"
        )
        for row in selected_rows:
            values = (
                row["value"],
                row["current_clicks"],
                row["current_impressions"],
                row["previous_clicks"],
                row["previous_impressions"],
            )
            summary.append("| " + " | ".join(_md(value) for value in values) + " |")
            parts.append(
                "<tr>"
                + "".join(
                    "<td>" + html.escape(str(value) if value is not None else "unknown") + "</td>"
                    for value in values
                )
                + "</tr>"
            )
        if not selected_rows:
            summary.append("No rows supplied for this dimension.")
        parts.append("</tbody></table>")
    summary.extend(
        [
            "",
            "Full query and page rows are in gsc-report.csv. A missing row is unknown, not zero. "
            "Sources and SHA-256 hashes are retained in the private gsc snapshots.",
        ]
    )
    (directory / "gsc-report.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    parts.append(
        '<p>Full query and page rows: <a href="gsc-report.csv">CSV</a>. '
        "Missing rows are unknown.</p></body></html>"
    )
    (directory / "gsc-report.html").write_text("".join(parts), encoding="utf-8")
    return True
