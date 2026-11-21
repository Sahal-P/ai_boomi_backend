"""Public facts from the web for the advisor (docs/names-search-round/contract.md).

Only the search question leaves FinBoy, never the household's records, memories or chat. OpenAI's
web search reads the pages; the advisor gets a short summary and the pages it cites, and may quote
a figure only from that summary. Nothing here is stored or logged.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from openai import OpenAIError

from finboy.core.clock import today_ist
from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.services.advisor.client import client_for

MAX_SUMMARY = 1200
MAX_PAGES = 4
INSTRUCTIONS = """Find current public facts for a person in India. Today is {today}.
- Answer in plain English in at most 6 short lines, and say what each figure is (for example the
  ex-showroom or on-road price and for which city, or interest a year).
- Write every amount in full rupees with its own ₹, like ₹4,56,000 to ₹4,93,000 (never
  ₹4.56–4.93 lakh), and every rate with its own %, like 9% to 14% a year.
- For loans give the usual range across lenders, from a comparison or official page rather than
  one lender's own; never name or rank a lender or a loan product. Give no advice.
- If the pages don't answer the question, reply only: NOT FOUND"""
CITATION = re.compile(r"\s*\(\[[^\]]*\]\([^)]*\)\)")  # an inline "([site](https://…))"
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")  # "[words](https://…)" keeps its words
URL = re.compile(r"https?://\S+")


@dataclass(frozen=True)
class Page:
    title: str
    url: str


@dataclass(frozen=True)
class Found:
    summary: str | None  # None when the pages did not answer
    pages: list[Page]


def _summary(text: str) -> str:
    text = URL.sub("", LINK.sub(r"\1", CITATION.sub("", text))).replace("**", "")
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)[:MAX_SUMMARY]


def _pages(output: list) -> list[Page]:
    """The pages the answer cites, in order, once each."""
    pages: dict[str, Page] = {}
    for item in output:
        if item.type != "message":
            continue
        for part in item.content:
            for note in getattr(part, "annotations", None) or []:
                address = urlsplit(note.url) if note.type == "url_citation" else None
                if address is None or address.scheme != "https" or not address.hostname:
                    continue
                title = " ".join((note.title or "").split())[:120] or address.hostname
                pages.setdefault(note.url, Page(title=title, url=note.url))
    return list(pages.values())[:MAX_PAGES]


def search(question: str, settings: Settings) -> Found:
    """One web search; ProviderUnavailable when it can't answer now, so the advisor goes on
    without it. No retries: the answer is already waiting on this call."""
    try:
        client = client_for(settings, provider="openai").with_options(max_retries=0)
        response = client.responses.create(
            model=settings.advisor_model_for("openai"),  # type: ignore[arg-type]
            instructions=INSTRUCTIONS.format(today=today_ist().isoformat()),
            input=question,
            tools=[
                {
                    "type": "web_search",
                    "user_location": {"type": "approximate", "country": "IN"},
                    "search_context_size": "low",
                }
            ],
            tool_choice="required",
            max_tool_calls=2,
            reasoning={"effort": settings.advisor_reasoning_effort},
            store=False,
            max_output_tokens=1500,
            timeout=settings.advisor_timeout_seconds,
        )
    except OpenAIError:
        raise ProviderUnavailable from None
    if response.status != "completed":
        raise ProviderUnavailable
    summary = _summary(response.output_text)
    if not summary or summary.upper().startswith("NOT FOUND"):
        return Found(summary=None, pages=[])
    return Found(summary=summary, pages=_pages(response.output))
