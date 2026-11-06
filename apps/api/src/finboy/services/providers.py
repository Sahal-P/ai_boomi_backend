"""Which providers are configured, never their values: shared by readiness and the admin panel."""

from typing import Literal

from finboy.core.config import Settings
from finboy.services.triage.provider import MODELS as DECISION_MODELS
from finboy.services.whatsapp.config import ChannelUnavailable, channel_config


def transcription(settings: Settings) -> bool:
    """Settings for every language the chosen provider routing can reach."""
    if settings.speech_transcribe_provider == "sarvam":
        return bool(settings.sarvam_api_key and settings.sarvam_stt_model)
    # Groq covers English/Hindi only; Malayalam and misdetections still go to OpenAI.
    openai = bool(settings.openai_api_key and settings.openai_transcribe_model)
    if settings.speech_transcribe_provider == "groq":
        return openai and bool(settings.groq_api_key and settings.groq_transcribe_model)
    return openai


def malayalam_tts(settings: Settings) -> bool:
    if settings.malayalam_tts_provider == "sarvam":
        return bool(
            settings.sarvam_api_key and settings.sarvam_tts_model and settings.sarvam_tts_speaker_ml
        )
    return bool(settings.gemini_api_key and settings.gemini_tts_model and settings.gemini_tts_voice)


def english_hindi_tts(settings: Settings) -> bool:
    return bool(
        settings.resemble_api_key
        and settings.resemble_tts_model
        and settings.resemble_voice_uuid_en
        and settings.resemble_voice_uuid_hi
    )


def gmail(settings: Settings) -> bool:
    return bool(
        settings.google_oauth_client_id
        and settings.google_oauth_client_secret
        and settings.token_encryption_key
        and settings.google_oauth_redirect_uri
    )


def whatsapp(settings: Settings) -> Literal["disabled", "configured", "missing"]:
    if not settings.whatsapp_enabled:
        return "disabled"
    try:
        channel_config(settings)
    except ChannelUnavailable:
        return "missing"
    return "configured"


def triage(settings: Settings) -> Literal["off", "configured", "missing"]:
    if not settings.triage_enabled:
        return "off"
    if settings.liquid_api_key and settings.liquid_decision_model in DECISION_MODELS:
        return "configured"
    return "missing"


def advisor(settings: Settings) -> Literal["off", "configured", "missing"]:
    """The advisor round (docs/advisor-round/contract.md): its flag and model key."""
    if not settings.advisor_enabled:
        return "off"
    return "configured" if settings.openai_api_key and settings.advisor_model else "missing"
