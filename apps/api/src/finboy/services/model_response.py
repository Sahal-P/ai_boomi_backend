"""Structured Responses API calls shared by FinBoy's OpenAI and DeepSeek model paths."""

from types import SimpleNamespace
from typing import Any

from openai import OpenAI
from pydantic import BaseModel

from finboy.core.config import ModelProvider


def base_url(provider: ModelProvider) -> str | None:
    return "https://api.deepseek.com" if provider == "deepseek" else None


def parse(
    client: OpenAI, provider: ModelProvider, *, text_format: type[BaseModel], **options: Any
) -> Any:
    if provider == "openai":
        return client.responses.parse(text_format=text_format, **options)
    # The DeepSeek endpoint is stateless and manages its own cache. Tool calls can precede text.
    for field in ("store", "prompt_cache_key", "include", "parallel_tool_calls"):
        options.pop(field, None)
    options["reasoning"] = {"effort": "none"}
    response = client.responses.create(
        text={
            "format": {
                "type": "json_schema",
                "name": text_format.__name__,
                "schema": text_format.model_json_schema(),
            }
        },
        **options,
    )
    if response.status != "completed":
        return SimpleNamespace(output=[], output_parsed=None)
    content = response.output_text
    return SimpleNamespace(
        output=response.output,
        output_parsed=text_format.model_validate_json(content) if content.strip() else None,
    )
