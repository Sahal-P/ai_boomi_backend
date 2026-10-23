"""Typed unavailable boundaries; Agent 3 supplies verified provider adapters."""

from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import Language
from finboy.services.speech.models import SynthesizedAudio, Transcript


def transcribe_audio(
    *, audio: bytes, content_type: str, settings: Settings, language_hint: Language | None = None
) -> Transcript:
    raise ProviderUnavailable("speech_unavailable")


def synthesize_speech(*, text: str, language: Language, settings: Settings) -> SynthesizedAudio:
    raise ProviderUnavailable("speech_unavailable")
