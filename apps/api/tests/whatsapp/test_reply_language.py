"""WhatsApp replies: English for someone new, then the person's own language (docs/whatsapp.md)."""

from datetime import UTC, datetime
from types import ModuleType
from unittest.mock import MagicMock

import pytest
from finboy.core.config import Settings
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.services.accounts import login
from finboy.services.speech.models import Transcript
from finboy.services.whatsapp import english, hindi, malayalam, pilot, processor
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.language import written_language
from finboy.services.whatsapp.meta import DownloadedMedia

from .test_processor import harness, household


def question(text: str = "", kind: str = "text") -> InboundQuestion:
    return InboundQuestion("wamid.synthetic", "919000000001", datetime.now(UTC), kind, text=text)


@pytest.mark.parametrize(
    ("text", "kind", "language"),
    [
        ("Paid the milkman 500", "text", "en"),
        ("how much did I spend this month?", "text", "en"),
        ("Paid Roopa 500", "text", "en"),
        ("दूधवाले को 500 दिए", "text", "hi"),
        ("नमस्ते", "text", "hi"),
        ("बंद", "text", "hi"),
        ("doodhwale ko 500 diye", "text", "hi"),
        ("is mahine kitna kharcha hua", "text", "hi"),
        ("പാൽക്കാരന് 500 കൊടുത്തു", "text", "ml"),
        ("paalkaaranu 500 koduthu", "text", "ml"),
        # Nothing to go on: a greeting, a single word, digits, emoji, a tap, a photo, a voice note
        # before it is heard.
        ("Hi", "text", None),
        ("hi", "text", None),
        ("Hello FinBoy", "text", None),
        ("Hi FinBoy", "text", None),
        ("ok", "text", None),
        ("STOP", "text", None),
        ("hindi", "text", None),
        ("500", "text", None),
        ("👍", "text", None),
        ("", "audio", None),
        ("", "image", None),
        ("", "button", None),
    ],
)
def test_the_language_a_typed_message_shows(text: str, kind: str, language: str | None) -> None:
    assert written_language(question(text, kind)) == language


def test_the_prefilled_login_line_shows_no_language() -> None:
    assert written_language(question(f"FinBoy login code {login.new_code()}")) is None


def talk(binding: WhatsAppBinding, *, heard=None, kind="text", client=None) -> pilot.Conversation:
    return pilot.Conversation(
        MagicMock(),
        MagicMock(),
        MagicMock(),
        client or MagicMock(),
        MagicMock(),
        question(kind=kind),
        binding,
        MagicMock(return_value=True),
        heard=heard,
    )


@pytest.mark.parametrize(
    ("chosen", "heard", "last", "language"),
    [
        (None, None, None, "en"),  # someone new
        (None, None, "ml", "ml"),  # a tap or a login code: the language FinBoy last used
        (None, "hi", "ml", "hi"),  # this message's own language comes first
        ("hi", "en", "ml", "hi"),  # a chosen language sticks
    ],
)
def test_a_choice_then_this_message_then_the_last_reply_then_english(
    chosen: str | None, heard: str | None, last: str | None, language: str
) -> None:
    binding = WhatsAppBinding(language=chosen, last_language=last)
    assert talk(binding, heard=heard).language == language


def test_each_reply_remembers_its_language() -> None:
    binding = WhatsAppBinding(language=None, last_language="en")
    conversation = talk(binding, heard="hi")
    assert conversation.send("synthetic") is True
    assert binding.last_language == "hi"


@pytest.mark.parametrize(("chosen", "hint", "language"), [(None, None, "hi"), ("ml", "ml", "ml")])
def test_a_voice_note_gets_a_hint_only_for_a_chosen_language(
    monkeypatch: pytest.MonkeyPatch, chosen: str | None, hint: str | None, language: str
) -> None:
    transcribe = MagicMock(
        return_value=Transcript(transcript="दूधवाले को 500 दिए", detected_language="hi")
    )
    monkeypatch.setattr(pilot.speech, "transcribe_audio", transcribe)
    client = MagicMock()
    client.download_audio.return_value = DownloadedMedia(b"synthetic", "audio/ogg")
    conversation = talk(WhatsAppBinding(language=chosen), kind="audio", client=client)
    assert pilot._heard(conversation) == "दूधवाले को 500 दिए"
    assert transcribe.call_args.kwargs["language_hint"] == hint
    assert conversation.heard == "hi" and conversation.language == language


@pytest.mark.parametrize(
    "new_household",
    [{"joined_via": "whatsapp", "agreed": False}, {"pilot": True}],
    ids=["self-serve", "pilot"],
)
@pytest.mark.parametrize(
    ("words", "kind", "module"),
    [
        ("Hi", "text", english),
        ("नमस्ते", "text", hindi),
        ("നമസ്കാരം", "text", malayalam),
        ("", "audio", english),  # nothing is transcribed before agreeing
    ],
)
def test_the_consent_card_follows_the_first_message_and_otherwise_english(
    monkeypatch: pytest.MonkeyPatch,
    config: ChannelConfig,
    wa_settings: Settings,
    new_household: dict,
    words: str,
    kind: str,
    module: ModuleType,
) -> None:
    factory, receipt, _, _, _, _, transcribe, _, _ = harness(monkeypatch)
    session = factory.return_value.__enter__.return_value
    session.execute.return_value.one_or_none.return_value = household(**new_household)
    consent = MagicMock(return_value=None)
    monkeypatch.setattr(processor.pilot, "ask_consent", consent)
    processor.process_question(factory, wa_settings, config, receipt.id, question(words, kind))
    assert consent.call_args.args[0].words is module
    assert not transcribe.called


@pytest.mark.parametrize(("last", "module"), [(None, english), ("hi", hindi)])
def test_a_login_code_gets_the_language_last_used_or_english(
    monkeypatch: pytest.MonkeyPatch,
    config: ChannelConfig,
    wa_settings: Settings,
    last: str | None,
    module: ModuleType,
) -> None:
    factory, receipt, binding, _, _, _, _, _, _ = harness(monkeypatch)
    binding.last_language = last
    session = factory.return_value.__enter__.return_value
    session.execute.return_value.one_or_none.return_value = household(pilot=True)
    handle_code = MagicMock(return_value=None)
    monkeypatch.setattr(processor.signup, "handle_code", handle_code)
    code = question(f"FinBoy login code {login.new_code()}")
    processor.process_question(factory, wa_settings, config, receipt.id, code)
    assert handle_code.call_args.args[0].words is module


@pytest.mark.parametrize(
    ("chosen", "last", "words", "module"),
    [
        (None, None, "दूधवाले को 500 दिए", hindi),
        (None, "hi", "Paid the milkman 500", english),
        (None, None, "doodhwale ko 500 diye", hindi),
        (None, "en", "പാൽക്കാരന് 500 കൊടുത്തു", malayalam),
        (None, "ml", "500", malayalam),
        ("hi", "hi", "Paid the milkman 500", hindi),  # chosen: sticks through English
    ],
)
def test_a_diary_reply_follows_each_message_unless_a_language_was_chosen(
    monkeypatch: pytest.MonkeyPatch,
    config: ChannelConfig,
    wa_settings: Settings,
    chosen: str | None,
    last: str | None,
    words: str,
    module: ModuleType,
) -> None:
    factory, receipt, binding, _, _, _, _, _, _ = harness(monkeypatch, preferred=chosen)
    binding.consented_at = datetime.now(UTC)
    binding.last_language = last
    session = factory.return_value.__enter__.return_value
    session.execute.return_value.one_or_none.return_value = household(pilot=True)
    handle = MagicMock(return_value=None)
    monkeypatch.setattr(processor.pilot, "handle", handle)
    processor.process_question(factory, wa_settings, config, receipt.id, question(words))
    assert handle.call_args.args[0].words is module


def test_the_owners_answer_is_remembered_in_its_language(
    monkeypatch: pytest.MonkeyPatch, config: ChannelConfig, wa_settings: Settings
) -> None:
    factory, receipt, binding, _, send, ask, _, _, _ = harness(monkeypatch)
    processor.process_question(
        factory, wa_settings, config, receipt.id, question("how much did I spend this month?")
    )
    assert ask.call_args.kwargs["display_style"] == "auto"
    assert send.called and binding.last_language == "en"
