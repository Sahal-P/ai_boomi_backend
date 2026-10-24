"""Reusable bounded speech APIs. Provider failure never affects a separate text answer."""

import re
from typing import Literal

from openai import APIError, OpenAI

from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import Language
from finboy.services.assistant.language import normalize_speech
from finboy.services.speech import providers
from finboy.services.speech.media import InvalidAudio, decode_audio, pcm_to_wav, to_mp3
from finboy.services.speech.models import SynthesizedAudio, Transcript

SttProvider = Literal["groq", "openai"]
WHISPER_LANGUAGES: dict[str, Language] = {
    "en": "en",
    "english": "en",
    "hi": "hi",
    "hindi": "hi",
    "ml": "ml",
    "malayalam": "ml",
}
NATIVE_SCRIPTS = {"hi": (0x0900, 0x097F), "ml": (0x0D00, 0x0D7F)}


def script_language(reported: str | None, text: str) -> Language | Literal["unknown"]:
    """A model-reported language counts only when the transcript is written in its script."""
    language = WHISPER_LANGUAGES.get((reported or "").strip().lower())
    letters = [character for character in text if character.isalpha()]
    native = [character for character in letters if not character.isascii()]
    if language == "en":
        return "en" if letters and not native else "unknown"
    if language in NATIVE_SCRIPTS:
        low, high = NATIVE_SCRIPTS[language]
        if native and all(low <= ord(character) <= high for character in native):
            return language
    return "unknown"


def silent(result: providers.GroqTranscription) -> bool:
    # Whisper's standard no-speech thresholds. Hallucinated filler on silence must not
    # reach the assistant from WhatsApp, where no one reviews the transcript first.
    return not result.text.strip() or (
        bool(result.segments)
        and all(s.no_speech_prob > 0.6 and s.avg_logprob < -1.0 for s in result.segments)
    )


def transcribe_routed(
    *, audio: bytes, content_type: str, settings: Settings, language_hint: Language | None = None
) -> tuple[Transcript, SttProvider]:
    if language_hint not in {None, "en", "hi", "ml"}:
        raise InvalidAudio()
    pcm = decode_audio(
        audio=audio,
        content_type=content_type,
        settings=settings,
        max_bytes=settings.speech_max_audio_bytes,
        max_seconds=settings.speech_max_duration_seconds,
    )
    wav = pcm_to_wav(pcm)
    if settings.speech_transcribe_provider == "groq" and language_hint != "ml":
        try:
            result = providers.groq_transcribe(wav, language_hint, settings)
        except providers.PROVIDER_ERRORS:
            # A Groq outage is reported, never silently retried with another provider.
            raise ProviderUnavailable("speech_unavailable") from None
        if silent(result):
            return Transcript(transcript="", detected_language="unknown"), "groq"
        detected = script_language(result.language, result.text)
        if detected in {"en", "hi"}:
            return Transcript(transcript=result.text.strip(), detected_language=detected), "groq"
        # Malayalam, a misdetected language or a mismatched script: one OpenAI pass.
    return openai_transcribe(wav, language_hint, settings), "openai"


def transcribe_audio(
    *, audio: bytes, content_type: str, settings: Settings, language_hint: Language | None = None
) -> Transcript:
    return transcribe_routed(
        audio=audio, content_type=content_type, settings=settings, language_hint=language_hint
    )[0]


def openai_transcribe(wav: bytes, language_hint: Language | None, settings: Settings) -> Transcript:
    if not settings.openai_api_key or not settings.openai_transcribe_model:
        raise ProviderUnavailable("configuration_missing")
    # Verified model uses plural languages. Do not silently route to deprecated models.
    if settings.openai_transcribe_model != "gpt-transcribe":
        raise ProviderUnavailable("configuration_missing")
    try:
        with OpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.speech_timeout_seconds,
            max_retries=settings.provider_max_retries,
        ) as client:
            result = client.audio.transcriptions.create(
                model=settings.openai_transcribe_model,
                file=("question.wav", wav, "audio/wav"),
                prompt=(
                    "A bookkeeping question in English, Hindi, or Malayalam. Preserve the "
                    "original language."
                ),
                extra_body={
                    "languages": [language_hint] if language_hint else ["en", "hi", "ml"],
                    "keywords": ["SIP", "UPI", "EMI", "salary", "Swiggy", "Zomato", "Amazon"],
                },
            )
        data = result.model_dump()
        text = data.get("text")
        languages = data.get("languages", [])
        codes = {entry.get("code") for entry in languages if isinstance(entry, dict)}
        detected = (
            next(iter(codes)) if len(codes) == 1 and codes <= {"en", "hi", "ml"} else "unknown"
        )
        if not isinstance(text, str) or len(text) > 2000:
            raise ProviderUnavailable("speech_unavailable")
        # Unknown/mixed remains unknown even with a hint; UI keeps the transcript editable.
        return Transcript(transcript=text.strip(), detected_language=detected)
    except APIError, ValueError, TypeError, KeyError:
        raise ProviderUnavailable("speech_unavailable") from None


def synthesize_speech(*, text: str, language: Language, settings: Settings) -> SynthesizedAudio:
    if (
        language not in {"en", "hi", "ml"}
        or not text.strip()
        or len(text) > settings.speech_max_text_characters
    ):
        raise InvalidAudio()
    text = normalize_speech(text, language)
    # Do not turn romanized responses into unverified pronunciation through the wrong locale.
    if language == "hi" and not re.search(r"[\u0900-\u097f]", text):
        raise InvalidAudio()
    if language == "ml" and not re.search(r"[\u0d00-\u0d7f]", text):
        raise InvalidAudio()
    try:
        if language == "ml":
            audio, mime = providers.gemini_synthesize(text, settings)
            mp3 = to_mp3(audio, mime, settings)
        else:
            audio, mime = providers.resemble_synthesize(text, language, settings)
            mp3 = to_mp3(audio, mime, settings)
        return SynthesizedAudio(data=mp3)
    except (*providers.PROVIDER_ERRORS, InvalidAudio):
        raise ProviderUnavailable("speech_unavailable") from None
