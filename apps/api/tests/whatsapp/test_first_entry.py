"""The first WhatsApp message from a page visit, and a household's first entry.

docs/ad-journey-round/contract.md. Synthetic numbers, refs and households only.
"""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from finboy.services.whatsapp import english, hindi, malayalam, pilot
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion, parse_events
from finboy.services.whatsapp.language import written_language

from .conftest import payload


def test_the_parser_hands_on_the_greeting_without_its_ref(config: ChannelConfig) -> None:
    raw = json.dumps(payload(text="നമസ്കാരം FinBoy (ref K7Q2MX)")).encode()
    (question,), _statuses = parse_events(raw, config)
    assert question.text == "നമസ്കാരം FinBoy" and question.ref == "K7Q2MX"
    (plain,), _statuses = parse_events(json.dumps(payload(text="chai 20")).encode(), config)
    assert plain.text == "chai 20" and plain.ref is None


def message(body: str) -> InboundQuestion:
    return InboundQuestion(
        "wamid.synthetic", "919000000071", datetime(2026, 11, 23, tzinfo=UTC), "text", body
    )


def test_the_malayalam_greeting_gets_the_malayalam_welcome() -> None:
    for greeting in ("നമസ്കാരം FinBoy", "നമസ്കാരം ഫിൻബോയ്", "Namaskaram FinBoy", "Hi FinBoy"):
        assert pilot._greeting(message(greeting)), greeting
    assert written_language(message("നമസ്കാരം FinBoy")) == "ml"
    assert written_language(message("Hi FinBoy")) is None  # English for someone new


@pytest.mark.parametrize("words", [english, hindi, malayalam])
def test_the_welcome_asks_for_one_entry_first(words) -> None:
    first, task = words.WELCOME.splitlines()[:2]
    assert first.startswith(("Thank you", "धन्यवाद", "നന്ദി")) and task.startswith("👉")
    assert "*" in task and "20*" in task
    assert "20*" in words.LANGUAGE_CHOSEN
    assert words.FIRST_SAVED.startswith("🎉")


def conversation(shown: int, confirmed: int) -> SimpleNamespace:
    session = MagicMock()
    session.scalar.side_effect = [shown, confirmed]
    return SimpleNamespace(
        session=session, binding=SimpleNamespace(user_id=uuid4()), words=malayalam
    )


def test_the_first_saved_entry_gets_its_line_once() -> None:
    line = "\n\n" + malayalam.FIRST_SAVED
    assert pilot._first_saved(conversation(1, 1), cards=1, saved=1, length=100) == line
    # Several items at once, one of them unsure.
    assert pilot._first_saved(conversation(3, 2), cards=3, saved=2, length=300) == line
    # An earlier saved card (an amount was changed), records from before (the web, the owner),
    # nothing saved, or no room left on the card: no line.
    assert pilot._first_saved(conversation(2, 1), cards=1, saved=1, length=100) == ""
    assert pilot._first_saved(conversation(1, 900), cards=1, saved=1, length=100) == ""
    assert pilot._first_saved(conversation(1, 0), cards=1, saved=0, length=100) == ""
    assert pilot._first_saved(conversation(1, 1), cards=1, saved=1, length=1000) == ""
