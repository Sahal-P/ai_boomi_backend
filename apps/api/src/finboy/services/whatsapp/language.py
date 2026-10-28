"""Which language FinBoy replies in on WhatsApp (docs/whatsapp.md, "Reply language").

A language the person chose with a command (`english`, `hindi`, `ml`, ...) sticks. Otherwise each
message decides: typed text by its script or its Hinglish/Manglish words (the web assistant's
detector), a voice note by what speech-to-text heard. A message that shows no language (a button
tap, a login code, a greeting, a photo, digits) gets the language FinBoy last used with that
person, and someone new gets English.
"""

import re

from finboy.core.languages import Language
from finboy.services.accounts import login
from finboy.services.assistant.language import resolve_style
from finboy.services.whatsapp.events import InboundQuestion

NATIVE_SCRIPT = re.compile(r"[ऀ-ॿഀ-ൿ]")
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
# FinBoy's own links prefill "Hi FinBoy", and a greeting says nothing about language.
GREETING = re.compile(
    r"^\s*(?:hi+|hello|hey|hai|namaste|namaskar)(?:\s+finboy)?\s*[.!,]*\s*$", re.IGNORECASE
)


def written_language(question: InboundQuestion) -> Language | None:
    """The language of a message the person typed, or None when it shows none."""
    text = question.text or ""
    # Latin commands (STOP, hindi) are single words and show nothing; बंद or നിർത്തുക shows a script.
    if question.kind != "text" or GREETING.match(text):
        return None
    if login.read_code(text) is not None:
        return None  # the English line FinBoy prefills for signing in
    if not NATIVE_SCRIPT.search(text) and len(LATIN_WORD.findall(text)) < 2:
        return None  # digits, emoji, or one word like "ok"
    return resolve_style(text, "auto")[1]
