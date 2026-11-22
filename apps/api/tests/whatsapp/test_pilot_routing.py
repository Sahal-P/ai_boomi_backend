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
        ("malayalam", "ml", malayalam.LANGUAGE_CHOSEN),
        ("hindi", "hi", hindi.LANGUAGE_CHOSEN),
        ("हिंदी", "hi", hindi.LANGUAGE_CHOSEN),
        ("en", "en", english.LANGUAGE_CHOSEN),
        ("english", "en", english.LANGUAGE_CHOSEN),
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


def test_a_language_chosen_on_the_first_message_welcomes_in_it(
    monkeypatch: pytest.MonkeyPatch, config: ChannelConfig, wa_settings: Settings
) -> None:
    factory, receipt, binding, _, send, _, _, _, finish = harness(monkeypatch, preferred="ml")
    session = factory.return_value.__enter__.return_value
    session.execute.return_value.one_or_none.return_value = household(pilot=True, agreed=False)
    processor.process_question(factory, wa_settings, config, receipt.id, question("ml"))
    assert send.call_args_list[0].kwargs["text"] == malayalam.WELCOME
    assert binding.consented_at is not None and binding.language == "ml"
    assert finish.call_args.kwargs["error"] is None


def test_the_owners_language_commands_are_unchanged(
    monkeypatch: pytest.MonkeyPatch, config: ChannelConfig, wa_settings: Settings
) -> None:
    factory, receipt, _, _, send, _, _, _, _ = harness(monkeypatch, preferred="ml")
    processor.process_question(factory, wa_settings, config, receipt.id, question("ml"))
    assert send.call_args.kwargs["text"] == "മലയാളം തിരഞ്ഞെടുത്തു. FinBoy രേഖകളെക്കുറിച്ച് ചോദിക്കാം."


@pytest.mark.parametrize("purpose", [None, "web_login"])
def test_owner_button_shows_typing_only_if_it_has_a_reply(
    monkeypatch: pytest.MonkeyPatch,
    config: ChannelConfig,
    wa_settings: Settings,
    purpose: str | None,
) -> None:
    factory, receipt, _, meta, send, ask, _, _, finish = harness(monkeypatch)
    session = factory.return_value.__enter__.return_value
    session.scalar.return_value = purpose
    # An expired web login prompt still gets an explanation.
    monkeypatch.setattr(processor.prompts, "claim", lambda *_: None)
    tap = question(kind="button", button_id="fb1:" + "a" * 32 + ":yes")
    loop = MagicMock()
    processor.process_question(factory, wa_settings, config, receipt.id, tap, typing_loop=loop)
    if purpose:
        meta.start_typing.assert_called_once_with(loop, tap.message_id)
        send.assert_called_once()
    else:
        meta.start_typing.assert_not_called()
        send.assert_not_called()
    ask.assert_not_called()
    assert finish.call_args.kwargs["error"] == "prompt_expired"
