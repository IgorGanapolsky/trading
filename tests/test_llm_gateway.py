"""
Tests for LLM Gateway configuration and enforcement.

Validates:
- Gateway requirement enforcement (REQUIRE_LLM_GATEWAY)
- Strict mode suppresses direct-to-OpenRouter fallback (LLM_GATEWAY_STRICT)
- Normal config resolution with and without gateway overrides
"""

import os
from unittest.mock import patch

import pytest

from src.utils.llm_gateway import (
    OPENROUTER_BASE_URL,
    GatewayRequiredError,
    enforce_gateway_requirement,
    resolve_openai_compatible_config,
    resolve_openrouter_primary_and_fallback_configs,
)


class TestEnforceGatewayRequirement:
    """Test REQUIRE_LLM_GATEWAY enforcement."""

    @patch.dict(os.environ, {"REQUIRE_LLM_GATEWAY": "true"}, clear=False)
    def test_raises_when_required_but_missing(self):
        """Raises GatewayRequiredError when gateway is required but URL is not set."""
        os.environ.pop("LLM_GATEWAY_BASE_URL", None)
        with pytest.raises(GatewayRequiredError, match="LLM_GATEWAY_BASE_URL is not set"):
            enforce_gateway_requirement()

    @patch.dict(
        os.environ,
        {"REQUIRE_LLM_GATEWAY": "true", "LLM_GATEWAY_BASE_URL": "https://gw.example.com/v1"},
        clear=False,
    )
    def test_passes_when_required_and_configured(self):
        """No error when gateway is required and URL is set."""
        enforce_gateway_requirement()  # should not raise

    @patch.dict(os.environ, {}, clear=False)
    def test_noop_when_not_required(self):
        """No enforcement when REQUIRE_LLM_GATEWAY is not set."""
        os.environ.pop("REQUIRE_LLM_GATEWAY", None)
        os.environ.pop("LLM_GATEWAY_BASE_URL", None)
        enforce_gateway_requirement()  # should not raise

    @patch.dict(os.environ, {"REQUIRE_LLM_GATEWAY": "false"}, clear=False)
    def test_noop_when_explicitly_false(self):
        """No enforcement when REQUIRE_LLM_GATEWAY=false."""
        os.environ.pop("LLM_GATEWAY_BASE_URL", None)
        enforce_gateway_requirement()  # should not raise


class TestResolveConfig:
    """Test resolve_openai_compatible_config."""

    @patch.dict(os.environ, {"REQUIRE_LLM_GATEWAY": "true"}, clear=False)
    def test_resolve_raises_when_gateway_required_but_missing(self):
        """resolve_openai_compatible_config raises if gateway required but not set."""
        os.environ.pop("LLM_GATEWAY_BASE_URL", None)
        with pytest.raises(GatewayRequiredError):
            resolve_openai_compatible_config(
                default_api_key_env="OPENROUTER_API_KEY",
                default_base_url=OPENROUTER_BASE_URL,
            )

    @patch.dict(
        os.environ,
        {
            "LLM_GATEWAY_BASE_URL": "https://gw.example.com/v1",
            "LLM_GATEWAY_API_KEY": "gw-key-123",
        },
        clear=False,
    )
    def test_gateway_overrides_defaults(self):
        """Gateway env vars override default base_url and api_key."""
        os.environ.pop("REQUIRE_LLM_GATEWAY", None)
        config = resolve_openai_compatible_config(
            default_api_key_env="OPENROUTER_API_KEY",
            default_base_url=OPENROUTER_BASE_URL,
        )
        assert config.base_url == "https://gw.example.com/v1"
        assert config.api_key == "gw-key-123"

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-key-456"}, clear=False)
    def test_falls_back_to_default_without_gateway(self):
        """Uses default base_url and env key when no gateway is configured."""
        os.environ.pop("LLM_GATEWAY_BASE_URL", None)
        os.environ.pop("LLM_GATEWAY_API_KEY", None)
        os.environ.pop("TETRATE_API_KEY", None)
        os.environ.pop("REQUIRE_LLM_GATEWAY", None)
        config = resolve_openai_compatible_config(
            default_api_key_env="OPENROUTER_API_KEY",
            default_base_url=OPENROUTER_BASE_URL,
        )
        assert config.base_url == OPENROUTER_BASE_URL
        assert config.api_key == "or-key-456"


class TestStrictMode:
    """Test LLM_GATEWAY_STRICT suppresses fallback."""

    @patch.dict(
        os.environ,
        {
            "LLM_GATEWAY_BASE_URL": "https://gw.example.com/v1",
            "LLM_GATEWAY_API_KEY": "gw-key",
            "OPENROUTER_API_KEY": "or-key",
            "LLM_GATEWAY_STRICT": "true",
        },
        clear=False,
    )
    def test_strict_mode_no_fallback(self):
        """With strict mode, no fallback config is returned even if OpenRouter key exists."""
        os.environ.pop("REQUIRE_LLM_GATEWAY", None)
        primary, fallback = resolve_openrouter_primary_and_fallback_configs()
        assert primary.base_url == "https://gw.example.com/v1"
        assert fallback is None

    @patch.dict(
        os.environ,
        {
            "LLM_GATEWAY_BASE_URL": "https://gw.example.com/v1",
            "LLM_GATEWAY_API_KEY": "gw-key",
            "OPENROUTER_API_KEY": "or-key",
        },
        clear=False,
    )
    def test_normal_mode_returns_fallback(self):
        """Without strict mode, fallback to direct OpenRouter is available."""
        os.environ.pop("LLM_GATEWAY_STRICT", None)
        os.environ.pop("REQUIRE_LLM_GATEWAY", None)
        primary, fallback = resolve_openrouter_primary_and_fallback_configs()
        assert primary.base_url == "https://gw.example.com/v1"
        assert fallback is not None
        assert fallback.base_url == OPENROUTER_BASE_URL
        assert fallback.api_key == "or-key"

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-key"}, clear=False)
    def test_no_gateway_means_no_fallback(self):
        """Without a gateway, there's no fallback (primary IS OpenRouter)."""
        os.environ.pop("LLM_GATEWAY_BASE_URL", None)
        os.environ.pop("LLM_GATEWAY_STRICT", None)
        os.environ.pop("REQUIRE_LLM_GATEWAY", None)
        primary, fallback = resolve_openrouter_primary_and_fallback_configs()
        assert primary.base_url == OPENROUTER_BASE_URL
        assert fallback is None
