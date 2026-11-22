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


def malayalam_tts(settings: Settings) -> Literal["off", "configured", "missing"]:
    """Spoken Malayalam replies come only from Sarvam; off means they are written only."""
    if settings.malayalam_tts_provider == "off":
        return "off"
    if settings.sarvam_api_key and settings.sarvam_tts_model and settings.sarvam_tts_speaker_ml:
        return "configured"
    return "missing"


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


def knowledge(settings: Settings) -> Literal["off", "configured", "missing"]:
    """FinBoy's money guides (advisor phase 2): missing when switched on with nothing to serve,
    as in production before any guide is reviewed."""
    if not settings.advisor_enabled or not settings.knowledge_enabled:
        return "off"
    from finboy.services.advisor.knowledge import serving

    return "configured" if serving(settings) else "missing"


def advisor(settings: Settings) -> Literal["off", "configured", "missing"]:
    """The advisor round (docs/advisor-round/contract.md): its flag and model key."""
    if not settings.advisor_enabled:
        return "off"
    provider = settings.advisor_answer_provider
    return (
        "configured"
        if settings.ai_key(provider) and settings.advisor_model_for(provider)
        else "missing"
    )


def web_search(settings: Settings) -> Literal["off", "configured", "missing"]:
    """Public prices and rates for the advisor (docs/names-search-round/contract.md). The search
    always runs on OpenAI, even when another provider writes the answer."""
    if not settings.advisor_enabled or not settings.advisor_web_search_enabled:
        return "off"
    ready = settings.ai_key("openai") and settings.advisor_model_for("openai")
    return "configured" if ready else "missing"


def media_store(settings: Settings) -> Literal["off", "configured", "missing"]:
    """Cloudflare R2 for kept voice notes and photos (docs/conversation-round/contract.md)."""
    if not settings.conversation_log_enabled:
        return "off"
    ready = (
        settings.r2_account_id
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
        and settings.r2_bucket
    )
    return "configured" if ready else "missing"


def coach(settings: Settings) -> Literal["off", "window_only", "configured"]:
    """The coach (advisor phase 3): `window_only` until Meta approves its template, when nudges
    reach only households that wrote to FinBoy in the last day."""
    if not settings.coach_active:
        return "off"
    return "configured" if settings.whatsapp_coach_template else "window_only"
