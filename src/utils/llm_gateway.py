"""
LLM Gateway configuration helpers.

This repo primarily uses OpenAI-compatible SDK clients (OpenAI/OpenRouter). To
support gateway products (e.g., Tetrate Agent Router) without rewriting code,
we resolve the base URL and API key from environment variables.

Priority:
- If LLM_GATEWAY_BASE_URL is set, it overrides the provider default base_url.
- If LLM_GATEWAY_API_KEY or TETRATE_API_KEY is set, it overrides the provider API key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    api_key: str
    base_url: str | None


def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def get_llm_gateway_base_url() -> str | None:
    """Optional override for OpenAI-compatible base URL (e.g., a gateway endpoint)."""
    value = _get_env("LLM_GATEWAY_BASE_URL")
    return value or None


def get_llm_gateway_api_key() -> str:
    """Optional override for OpenAI-compatible API key (gateway-managed key)."""
    return _get_env("LLM_GATEWAY_API_KEY") or _get_env("TETRATE_API_KEY")


def resolve_openai_compatible_config(
    *,
    default_api_key_env: str,
    default_base_url: str | None,
) -> OpenAICompatibleConfig:
    """
    Resolve (api_key, base_url) for an OpenAI-compatible SDK client.

    This keeps existing provider defaults, while allowing a gateway to override:
    - base_url via LLM_GATEWAY_BASE_URL
    - api_key via LLM_GATEWAY_API_KEY / TETRATE_API_KEY
    """
    base_url = get_llm_gateway_base_url() or default_base_url
    api_key = get_llm_gateway_api_key() or _get_env(default_api_key_env)
    return OpenAICompatibleConfig(api_key=api_key, base_url=base_url)
