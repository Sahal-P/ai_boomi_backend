"""Reusable bounded speech APIs. Provider failure never affects a separate text answer."""

import re

from openai import APIError, OpenAI

from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import Language
from finboy.services.assistant.language import normalize_speech
from finboy.services.speech import providers
from finboy.services.speech.media import InvalidAudio, decode_audio, pcm_to_wav, to_mp3
from finboy.services.speech.models import SynthesizedAudio, Transcript


def transcribe_audio(
    *, audio: bytes, content_type: str, settings: Settings, language_hint: Language | None = None
) -> Transcript:
    if language_hint not in {None, "en", "hi", "ml"}:
        raise InvalidAudio()
    pcm = decode_audio(
        audio=audio,
        content_type=content_type,
        settings=settings,
        max_bytes=settings.speech_max_audio_bytes,
        max_seconds=settings.speech_max_duration_seconds,
    )
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
                file=("question.wav", pcm_to_wav(pcm), "audio/wav"),
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
