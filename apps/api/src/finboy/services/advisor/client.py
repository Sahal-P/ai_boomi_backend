"""One OpenAI client per key, reused across requests so each answer skips a new connection."""

from functools import lru_cache

from openai import OpenAI

from finboy.core.config import ModelProvider, Settings
from finboy.core.errors import ProviderUnavailable
from finboy.services import model_response


@lru_cache(maxsize=4)
def _client(key: str, retries: int, url: str | None = None) -> OpenAI:
    return OpenAI(api_key=key, max_retries=retries, base_url=url)


def client_for(settings: Settings, *, provider: ModelProvider | None = None) -> OpenAI:
    provider = provider or settings.assistant_provider
    key = settings.ai_key(provider)
    if key is None or not key.get_secret_value() or not settings.advisor_model_for(provider):
        raise ProviderUnavailable("configuration_missing")
    return _client(
        key.get_secret_value(), settings.provider_max_retries, model_response.base_url(provider)
    )
