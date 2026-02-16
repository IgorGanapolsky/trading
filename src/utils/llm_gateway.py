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

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class GatewayRequiredError(RuntimeError):
    """Raised when REQUIRE_LLM_GATEWAY=true but no gateway URL is configured."""


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    api_key: str
    base_url: str | None


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def enforce_gateway_requirement() -> None:
    """Raise if REQUIRE_LLM_GATEWAY is set but no gateway URL is configured."""
    if not _is_truthy(os.getenv("REQUIRE_LLM_GATEWAY")):
        return
    if not get_llm_gateway_base_url():
        raise GatewayRequiredError(
            "REQUIRE_LLM_GATEWAY=true but LLM_GATEWAY_BASE_URL is not set. "
            "All LLM calls must route through the gateway."
        )


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

    Raises GatewayRequiredError if REQUIRE_LLM_GATEWAY=true and no gateway URL is set.
    """
    enforce_gateway_requirement()
    base_url = get_llm_gateway_base_url() or default_base_url
    api_key = get_llm_gateway_api_key() or _get_env(default_api_key_env)
    return OpenAICompatibleConfig(api_key=api_key, base_url=base_url)


def resolve_openrouter_primary_and_fallback_configs(
    *,
    openrouter_base_url: str = OPENROUTER_BASE_URL,
) -> tuple[OpenAICompatibleConfig, OpenAICompatibleConfig | None]:
    """
    Resolve OpenRouter config for OpenAI-compatible clients with an optional fallback.

    Primary:
    - Uses gateway overrides if present (LLM_GATEWAY_BASE_URL + LLM_GATEWAY_API_KEY/TETRATE_API_KEY),
      otherwise uses direct OpenRouter config.

    Fallback:
    - If a gateway base_url is configured AND OPENROUTER_API_KEY is set, returns a direct OpenRouter
      config so callers can retry when the gateway is unavailable.
    """
    primary = resolve_openai_compatible_config(
        default_api_key_env="OPENROUTER_API_KEY",
        default_base_url=openrouter_base_url,
    )

    gateway_base_url = get_llm_gateway_base_url()
    openrouter_api_key = _get_env("OPENROUTER_API_KEY")
    using_gateway = bool(gateway_base_url) and (gateway_base_url != openrouter_base_url)
    strict = _is_truthy(os.getenv("LLM_GATEWAY_STRICT"))

    if strict and using_gateway:
        logger.info("LLM_GATEWAY_STRICT=true — no direct-to-OpenRouter fallback")
        return primary, None

    fallback = (
        OpenAICompatibleConfig(api_key=openrouter_api_key, base_url=openrouter_base_url)
        if using_gateway and openrouter_api_key
        else None
    )
    return primary, fallback
