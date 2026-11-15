"""Import private Search Console CSV exports without inventing missing observations."""

import csv
import hashlib
import io
import json
import math
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from scripts.seo.__main__ import read, save

PROPERTY = "https://finboy.io/"


def _number(value: str | None, *, position: bool = False) -> int | float | None:
    text = (value or "").strip()
    if text in {"", "-", "~"}:
        return None
    # English Search Console CSVs sometimes format large counts with commas.
    if not position and re.fullmatch(r"\d{1,3}(?:,\d{3})+", text):
        text = text.replace(",", "")
    try:
        number = float(text) if position else int(text)
    except ValueError as exc:
        raise ValueError("invalid_metric") from exc
    if not math.isfinite(number) or number < 0 or number > 10**12:
        raise ValueError("invalid_metric")
    # A zero position cannot describe a rank; Google may have exported an unavailable value as 0.
    return None if position and number == 0 else number


def _read_rows(path: Path, dimension: str) -> tuple[list[dict], str]:
    raw = path.read_bytes()
    if len(raw) > 5_000_000:
        raise ValueError("export_too_large")
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    label = "Top queries" if dimension == "query" else "Top pages"
    try:
        fields = reader.fieldnames or []
        source_rows = list(reader)
    except csv.Error as exc:
        raise ValueError("invalid_csv") from exc
    if len(fields) != len(set(fields)) or not {label, "Clicks", "Impressions"}.issubset(fields):
        raise ValueError("invalid_csv_headers")
    rows = []
    seen = set()
    for row in source_rows:
        if None in row:
            raise ValueError("invalid_csv_row")
        key = (row.get(label) or "").strip()
        if not key or len(key) > 2048:
            raise ValueError("invalid_csv_key")
        identity = key.casefold() if dimension == "query" else key
        if identity in seen:
            raise ValueError("duplicate_csv_key")
        seen.add(identity)
        if dimension == "page":
            parsed = urlsplit(key)
            if parsed.scheme != "https" or parsed.netloc != "finboy.io" or parsed.fragment:
                raise ValueError("page_outside_property")
        rows.append(
            {
                "key": key,
                "clicks": _number(row.get("Clicks")),
                "impressions": _number(row.get("Impressions")),
                "average_position": _number(row.get("Position"), position=True),
            }
        )
        if len(rows) > 10_000:
            raise ValueError("too_many_rows")
    return rows, hashlib.sha256(raw).hexdigest()


def _evidence(path: Path | None) -> dict | None:
    if path is None:
        return None
    content = path.read_bytes()
    if not content or len(content) > 5_000_000:
        raise ValueError("invalid_evidence")
    return {"name": path.name, "sha256": hashlib.sha256(content).hexdigest()}


def _context(
    start: str | None, end: str | None, country: str | None, device: str | None, search_type: str
) -> dict:
    if not all((start, end, country, device)):
        raise ValueError("missing_context")
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_date") from exc
    if last < first or last > date.today():
        raise ValueError("invalid_date")
    region = country.upper()
    if region != "ALL" and not re.fullmatch(r"[A-Z]{2}", region):
        raise ValueError("invalid_country")
    if device not in {"all", "desktop", "mobile", "tablet"} or search_type not in {
        "web",
        "image",
        "video",
        "news",
    }:
        raise ValueError("invalid_context")
    return {
        "property": PROPERTY,
        "start_date": first.isoformat(),
        "end_date": last.isoformat(),
        "country": region,
        "device": device,
        "search_type": search_type,
    }


def import_gsc(
    queries: Path,
    pages: Path | None,
    directory: Path,
    start: str | None,
    end: str | None,
    country: str | None,
    device: str | None,
    search_type: str,
    source_kind: str = "gsc-export",
    query_evidence: Path | None = None,
    page_evidence: Path | None = None,
    replace: bool = False,
) -> None:
    context = _context(start, end, country, device, search_type)
    if source_kind not in {"gsc-export", "browser-transcription"}:
        raise ValueError("invalid_source_kind")
    if source_kind == "browser-transcription" and (
        query_evidence is None or (pages is not None and page_evidence is None)
    ):
        raise ValueError("missing_evidence")
    query_rows, query_hash = _read_rows(queries, "query")
    page_rows, page_hash = _read_rows(pages, "page") if pages else (None, None)
    data = {
        "context": context,
        "context_source": "operator supplied; verify against the export filters",
        "source_kind": source_kind,
        "queries": query_rows,
        "pages": page_rows,
        "sources": {
            "queries": {
                "name": queries.name,
                "sha256": query_hash,
                "evidence": _evidence(query_evidence),
            },
            "pages": {"name": pages.name, "sha256": page_hash, "evidence": _evidence(page_evidence)}
            if pages
            else None,
        },
    }
    name = "_".join(
        (
            context["start_date"],
            context["end_date"],
            context["country"],
            context["device"],
            context["search_type"],
        )
    )
    output = directory / "gsc" / f"{name}.json"
    if output.exists() and read(output) != data:
        if not replace:
            raise ValueError("period_already_imported")
        previous_bytes = output.read_bytes()
        digest = hashlib.sha256(previous_bytes).hexdigest()[:16]
        archive = directory / "gsc-history" / f"{name}_{digest}.json"
        save(archive, json.loads(previous_bytes))
    save(output, data)
    save(
        directory / "gsc-context.json",
        {key: context[key] for key in ("property", "country", "device", "search_type")},
    )
    from scripts.seo.gsc_report import render_gsc

    render_gsc(directory)
    print(
        json.dumps(
            {
                "query_rows": len(query_rows),
                "page_rows": len(page_rows) if page_rows is not None else None,
                "period": name,
            }
        )
    )
