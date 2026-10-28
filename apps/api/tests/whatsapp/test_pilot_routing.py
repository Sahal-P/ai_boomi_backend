from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from finboy.core.config import Settings
from finboy.services.whatsapp import english, hindi, malayalam, processor
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion

from .test_processor import harness, household


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
    session.execute.return_value.one_or_none.return_value = household(pilot=True)
    processor.process_question(factory, wa_settings, config, receipt.id, question("500 दिए"))
    assert handle.call_count == 1 and ask.call_count == 0
    assert handle.call_args.args[0].binding is binding
    assert handle.call_args.args[0].reply is processor.send_reply
    assert finish.call_args.kwargs["error"] is None


def test_pilot_stop_and_start_are_answered_in_hindi(
    monkeypatch: pytest.MonkeyPatch, config: ChannelConfig, wa_settings: Settings
) -> None:
    factory, receipt, _, _, send, _, _, _, _ = harness(monkeypatch)
    session = factory.return_value.__enter__.return_value
    session.execute.return_value.one_or_none.return_value = household(pilot=True)
    processor.process_question(factory, wa_settings, config, receipt.id, question("बंद"))
    assert send.call_args.kwargs["text"] == hindi.STOP_REPLY
    assert send.call_args.kwargs["allow_disabled"] is True


@pytest.mark.parametrize(
    ("words", "language", "reply"),
    [
        ("ml", "ml", malayalam.LANGUAGE_CHOSEN),
        ("hi", "hi", hindi.LANGUAGE_CHOSEN),
        ("en", "en", english.LANGUAGE_CHOSEN),
        ("നിർത്തുക", "ml", malayalam.STOP_REPLY),
        ("തുടങ്ങുക", "ml", malayalam.START_REPLY),
    ],
)
def test_diary_households_hear_their_chosen_language(
    monkeypatch: pytest.MonkeyPatch,
    config: ChannelConfig,
    wa_settings: Settings,
    words: str,
    language: str,
    reply: str,
) -> None:
    # The receipt already stored the chosen language on the binding before processing.
    factory, receipt, binding, _, send, _, _, _, _ = harness(monkeypatch, preferred=language)
    binding.consented_at = datetime.now(UTC)
    session = factory.return_value.__enter__.return_value
    session.execute.return_value.one_or_none.return_value = household(joined_via="whatsapp")
    processor.process_question(factory, wa_settings, config, receipt.id, question(words))
    assert send.call_args.kwargs["text"] == reply


def test_a_language_chosen_before_agreeing_brings_the_consent_card_in_it(
    monkeypatch: pytest.MonkeyPatch, config: ChannelConfig, wa_settings: Settings
) -> None:
    factory, receipt, _, _, send, _, _, _, finish = harness(monkeypatch, preferred="ml")
    session = factory.return_value.__enter__.return_value
    session.execute.return_value.one_or_none.return_value = household(
        joined_via="whatsapp", agreed=False
    )
    consent = MagicMock(return_value=None)
    monkeypatch.setattr(processor.pilot, "ask_consent", consent)
    processor.process_question(factory, wa_settings, config, receipt.id, question("ml"))
    assert consent.call_args.args[0].words is malayalam
    assert send.call_count == 0 and finish.call_args.kwargs["error"] is None


def test_the_owners_language_commands_are_unchanged(
    monkeypatch: pytest.MonkeyPatch, config: ChannelConfig, wa_settings: Settings
) -> None:
    factory, receipt, _, _, send, _, _, _, _ = harness(monkeypatch, preferred="ml")
    processor.process_question(factory, wa_settings, config, receipt.id, question("ml"))
    assert send.call_args.kwargs["text"] == "മലയാളം തിരഞ്ഞെടുത്തു. FinBoy രേഖകളെക്കുറിച്ച് ചോദിക്കാം."


def test_a_button_from_a_non_pilot_household_does_nothing(
    monkeypatch: pytest.MonkeyPatch, config: ChannelConfig, wa_settings: Settings
) -> None:
    factory, receipt, _, _, send, ask, _, _, finish = harness(monkeypatch)
    tap = question(kind="button", button_id="fb1:" + "a" * 32 + ":yes")
    processor.process_question(factory, wa_settings, config, receipt.id, tap)
    assert send.call_count == ask.call_count == 0
    assert finish.call_args.kwargs["error"] == "prompt_expired"
