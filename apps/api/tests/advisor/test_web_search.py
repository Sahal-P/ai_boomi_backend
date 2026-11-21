"""Web search: one OpenAI request carrying only the question; cited pages; links stripped."""

from types import SimpleNamespace

import httpx
import pytest
from finboy.core.errors import ProviderUnavailable
from finboy.services.advisor import web_search
from openai import APITimeoutError

from .support import make_settings


class FakeOpenAI:
    """Stands in for the OpenAI client; records each request."""

    def __init__(self) -> None:
        self.response: SimpleNamespace | None = None
        self.error: Exception | None = None
        self.options: dict = {}
        self.calls: list[dict] = []
        self.responses = SimpleNamespace(create=self.create)

    def with_options(self, **options) -> FakeOpenAI:
        self.options = options
        return self

    def create(self, **request) -> SimpleNamespace | None:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.response


def cite(url: str, title: str) -> SimpleNamespace:
    return SimpleNamespace(type="url_citation", url=url, title=title)


def answer(text: str, *citations: SimpleNamespace, status: str = "completed") -> SimpleNamespace:
    part = SimpleNamespace(type="output_text", text=text, annotations=list(citations))
    message = SimpleNamespace(type="message", content=[part])
    return SimpleNamespace(
        status=status, output=[SimpleNamespace(type="web_search_call"), message], output_text=text
    )


@pytest.fixture
def openai(monkeypatch) -> FakeOpenAI:
    fake = FakeOpenAI()
    monkeypatch.setattr(web_search, "client_for", lambda _settings, provider: fake)
    return fake


def test_only_the_question_goes_to_openai_web_search(openai) -> None:
    page = "https://www.bikes.example/gt-650?utm_source=openai"
    openai.response = answer(
        f"On-road price in Kochi about **₹3,65,000** ([bikes.example]({page})).\n"
        "Bike loans usually cost 10% to 14% a year. See [the rates](https://rates.example/two).",
        cite(page, "GT 650 price"),
        cite("https://rates.example/two", "Two-wheeler loan rates"),
        cite("http://plain.example/rates", "Not https"),
        cite(page, "The same page again"),
    )
    found = web_search.search("GT 650 on-road price in Kochi", make_settings())
    (request,) = openai.calls
    assert request["input"] == "GT 650 on-road price in Kochi"
    assert request["tools"] == [
        {
            "type": "web_search",
            "user_location": {"type": "approximate", "country": "IN"},
            "search_context_size": "low",
        }
    ]
    assert request["store"] is False and request["max_tool_calls"] == 2
    assert request["tool_choice"] == "required" and openai.options == {"max_retries": 0}
    assert found.summary == (
        "On-road price in Kochi about ₹3,65,000.\n"
        "Bike loans usually cost 10% to 14% a year. See the rates."
    )
    assert [(item.title, item.url) for item in found.pages] == [
        ("GT 650 price", page),
        ("Two-wheeler loan rates", "https://rates.example/two"),
    ]


def test_nothing_found_or_a_failure_is_plain(openai) -> None:
    settings = make_settings()
    openai.response = answer("NOT FOUND")
    assert web_search.search("price of a made-up bike", settings) == web_search.Found(None, [])
    openai.response = answer("Half an answer", status="incomplete")
    with pytest.raises(ProviderUnavailable):
        web_search.search("petrol price in Delhi", settings)
    openai.error = APITimeoutError(request=httpx.Request("POST", "https://api.openai.test"))
    with pytest.raises(ProviderUnavailable):
        web_search.search("petrol price in Delhi", settings)
