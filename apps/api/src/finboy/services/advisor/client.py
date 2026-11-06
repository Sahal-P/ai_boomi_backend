"""One OpenAI client per key, reused across requests so each answer skips a new connection."""

from functools import lru_cache

from openai import OpenAI

from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable


@lru_cache(maxsize=4)
def _client(key: str, retries: int) -> OpenAI:
    return OpenAI(api_key=key, max_retries=retries)


def client_for(settings: Settings) -> OpenAI:
    key = settings.openai_api_key
    if key is None or not key.get_secret_value() or not settings.advisor_model:
        raise ProviderUnavailable("configuration_missing")
    return _client(key.get_secret_value(), settings.provider_max_retries)
