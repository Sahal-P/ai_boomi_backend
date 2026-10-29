"""The WhatsApp money diary in Malayalam (docs/malayalam-round/contract.md)."""

import inspect
from datetime import UTC, datetime
from types import ModuleType

import pytest
from finboy.core.clock import today_ist
from finboy.db.models.ledger import Transaction
from finboy.services.speech.models import SynthesizedAudio, Transcript
from finboy.services.whatsapp import english, hindi, malayalam, pilot
from finboy.services.whatsapp.capture import Capture
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.language import written_language
from finboy.services.whatsapp.statement import Statement

from .conftest import Household

MODULES = [english, hindi, malayalam]
BUTTONS = [
    "YES",
    "CHANGE",
    "NO",
    "UNDO",
    "AGREE",
    "DECLINE",
    "PAID",
    "LATER",
    "REMIND",
    "AGAIN",
    "SIGN_IN_YES",
    "CREATE_YES",
    "LINK_YES",
]


def public(module: ModuleType) -> dict[str, object]:
    return {
        name: value
        for name, value in vars(module).items()
        if not name.startswith("_")
        and not isinstance(value, ModuleType)
        and name not in {"date", "money", "spoken_money"}
    }


def test_every_language_defines_the_same_copy_name_for_name() -> None:
    names = [set(public(module)) for module in MODULES]
    assert names[0] == names[1] == names[2]
    for name, value in public(english).items():
        if callable(value):
            signatures = {str(inspect.signature(getattr(module, name))) for module in MODULES}
            assert len(signatures) == 1, name
    assert set(malayalam.CATEGORY) == set(english.CATEGORY) and len(malayalam.MONTHS) == 12


@pytest.mark.parametrize("module", MODULES, ids=lambda module: module.__name__.split(".")[-1])
def test_buttons_fit_whatsapp_in_every_language(module: ModuleType) -> None:
    for name in BUTTONS:
        title = getattr(module, name)
        # Meta allows 20 characters; stay within it however they are counted.
        assert len(title) <= 20 and len(title.encode("utf-16-le")) // 2 <= 20, (name, title)


def ask(text: str, kind: str = "text") -> InboundQuestion:
    return InboundQuestion("wamid.synthetic", "919000000002", datetime.now(UTC), kind, text=text)


@pytest.mark.parametrize(
    "text",
    ["നമസ്കാരം", "Hi FinBoy നമസ്കാരം", "നിർത്തുക", "paalkaaranu 500 koduthu", "ethra chelavayi?"],
)
def test_malayalam_script_and_manglish_are_answered_in_malayalam(text: str) -> None:
    assert written_language(ask(text)) == "ml"


@pytest.mark.parametrize(
    ("text", "command"),
    [("നിർത്തുക", "stop"), ("നിർത്തൂ", "stop"), (" തുടങ്ങുക ", "start"), ("ML", "ml")],
)
def test_malayalam_stop_and_start_words(text: str, command: str) -> None:
    assert ask(text).command == command


@pytest.fixture
def kerala(pilot_factory, settings, channel, monkeypatch) -> Household:
    home = Household(pilot_factory, settings, channel, monkeypatch)
    home.binding.language = "ml"
    home.session.commit()
    home.spoken = []
    monkeypatch.setattr(
        pilot.speech,
        "synthesize_speech",
        lambda **kwargs: home.spoken.append(kwargs["language"]) or SynthesizedAudio(b"mp3"),
    )
    return home


def test_consent_and_welcome_are_in_malayalam(pilot_factory, settings, channel, monkeypatch):
    home = Household(pilot_factory, settings, channel, monkeypatch, consented=False)
    home.binding.language = "ml"
    home.session.commit()
    assert home.say("പാൽക്കാരന് 500 കൊടുത്തു") is None
    assert home.texts() == [malayalam.CONSENT] and home.spoke() == 1
    assert [title for _, title in home.buttons()] == [malayalam.AGREE, malayalam.DECLINE]
    assert home.tap("decline") is None and home.texts()[-1] == malayalam.DECLINED
    home.say("നമസ്കാരം")
    assert home.tap("agree") is None
    assert home.binding.consented_at is not None and home.texts()[-1] == malayalam.WELCOME


def test_a_record_card_yes_and_undo_in_malayalam(kerala: Household) -> None:
    record = kerala.record()
    assert kerala.card(record) is None
    text = kerala.texts()[-1]
    assert "₹500 കൊടുത്തു" in text and "📅 ഇന്ന്" in text and "പലചരക്ക്" in text
    assert [title for _, title in kerala.buttons()] == [
        malayalam.YES,
        malayalam.CHANGE,
        malayalam.NO,
    ]
    assert kerala.spoken == ["ml"]
    assert kerala.tap("yes") is None
    assert kerala.session.get(Transaction, record).status == "confirmed"
    assert kerala.texts()[-1].startswith("✅ ചേർത്തു: ₹500 കൊടുത്തു")
    assert kerala.tap("undo") is None
    assert kerala.session.get(Transaction, record).status == "rejected"
    assert kerala.texts()[-1].startswith("↩️ മാറ്റി: ₹500 കൊടുത്തു")
    assert [title for _, title in kerala.buttons()] == [malayalam.PUT_BACK]
    assert kerala.tap("putback") is None
    assert kerala.session.get(Transaction, record).status == "confirmed"
    assert kerala.texts()[-1].startswith(malayalam.PUT_BACK_DONE)


def test_a_malayalam_voice_note_is_heard_in_malayalam_and_read_back(kerala, monkeypatch) -> None:
    hints: list[str | None] = []

    def transcribe(**kwargs):
        hints.append(kwargs["language_hint"])
        return Transcript(transcript="പാൽക്കാരന് ₹500 കാശായി കൊടുത്തു.", detected_language="ml")

    def record_voice(_engine, _settings, **kwargs):
        assert kwargs["line"].startswith("Rs. 500.00 paid to പാൽക്കാരന് via cash on ")
        return Capture("saved", 50000, "പാൽക്കാരന്", kerala.record())

    spoken = Statement("spent", 50000, "പാൽക്കാരന്", "cash", today_ist(), "groceries")
    monkeypatch.setattr(pilot.speech, "transcribe_audio", transcribe)
    monkeypatch.setattr(pilot.statement, "read_statements", lambda *_args: [spoken])
    monkeypatch.setattr(pilot.capture, "record_voice", record_voice)
    assert kerala.say("", kind="audio") is None
    assert hints == ["ml"] and kerala.texts()[-1].startswith("✅ ചേർത്തു: ₹500 കൊടുത്തു")


def test_unclear_and_missing_amounts_are_explained_in_malayalam(kerala) -> None:
    # The rules reader: no model is configured in tests.
    assert kerala.say("നമസ്കാരം") is None and kerala.texts()[-1] == malayalam.UNCLEAR
    assert kerala.say("പാൽക്കാരന് അഞ്ഞൂറ് രൂപ കൊടുത്തു") == "amount_unclear"
    assert kerala.texts()[-1] == malayalam.AMOUNT_MISSING and kerala.spoken[-1] == "ml"


@pytest.mark.parametrize("words", ["കണക്ക്", "എന്റെ കണക്ക്", "കണക്ക് പറയൂ.", "കണക്ക് കാണിക്കൂ"])
def test_kanakku_shows_the_week_in_malayalam(kerala, words) -> None:
    assert kerala.say(words) is None
    assert kerala.texts()[-1] == malayalam.WEEK_EMPTY
    row = kerala.session.get(Transaction, kerala.record())
    row.status = "confirmed"
    kerala.session.commit()
    kerala.say(words)
    text = kerala.texts()[-1]
    assert text.startswith("📒 ഈ ആഴ്ചത്തെ കണക്ക്") and "💸 പോയത്: ₹500" in text
    assert "🏷️ കൂടുതൽ ചെലവായത്: പലചരക്ക് ₹500" in text
