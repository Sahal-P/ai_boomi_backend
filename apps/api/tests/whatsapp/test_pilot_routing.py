from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from finboy.core.config import Settings
from finboy.services.whatsapp import processor
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion

from .test_processor import harness


def question(text: str = "", kind: str = "text", button_id: str | None = None) -> InboundQuestion:
    return InboundQuestion(
        "wamid.synthetic", "919000000001", datetime.now(UTC), kind, text=text, button_id=button_id
    )


def test_pilot_households_use_the_pilot_flow_and_owners_do_not(
    monkeypatch: pytest.MonkeyPatch, config: ChannelConfig, wa_settings: Settings
) -> None:
    factory, receipt, binding, _, _, ask, _, _, finish = harness(monkeypatch)
    session = factory.return_value.__enter__.return_value
    handle = MagicMock(return_value=None)
    monkeypatch.setattr(processor.pilot, "handle", handle)
    session.scalar.return_value = True  # users.pilot for this binding's household
    processor.process_question(factory, wa_settings, config, receipt.id, question("500 दिए"))
    assert handle.call_count == 1 and ask.call_count == 0
    assert handle.call_args.args[0].binding is binding
    assert handle.call_args.args[0].reply is processor.send_reply
    assert finish.call_args.kwargs["error"] is None


def test_pilot_stop_and_start_are_answered_in_hindi(
    monkeypatch: pytest.MonkeyPatch, config: ChannelConfig, wa_settings: Settings
) -> None:
    factory, receipt, _, _, send, _, _, _, _ = harness(monkeypatch)
    factory.return_value.__enter__.return_value.scalar.return_value = True
    processor.process_question(factory, wa_settings, config, receipt.id, question("बंद"))
    assert send.call_args.kwargs["text"] == processor.PILOT_COMMANDS["stop"]
    assert send.call_args.kwargs["allow_disabled"] is True


def test_a_button_from_a_non_pilot_household_does_nothing(
    monkeypatch: pytest.MonkeyPatch, config: ChannelConfig, wa_settings: Settings
) -> None:
    factory, receipt, _, _, send, ask, _, _, finish = harness(monkeypatch)
    tap = question(kind="button", button_id="fb1:" + "a" * 32 + ":yes")
    processor.process_question(factory, wa_settings, config, receipt.id, tap)
    assert send.call_count == ask.call_count == 0
    assert finish.call_args.kwargs["error"] == "prompt_expired"
