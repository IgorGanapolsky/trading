"""
Tests for dynamic model pricing fetcher.

TDD approach: Tests written BEFORE implementation.
These tests define the contract that fetch_model_pricing.py must satisfy.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Import will fail initially - that's expected in TDD
try:
    from scripts.fetch_model_pricing import (
        ModelPricingFetcher,
        PricingCache,
        PricingSource,
        fetch_pricing_for_shell,
    )
except ImportError:
    pytest.skip("Implementation not yet created", allow_module_level=True)


class TestPricingCache:
    """Test the pricing cache mechanism."""

    def test_cache_stores_and_retrieves_pricing(self, tmp_path):
        """Cache should persist pricing data to disk."""
        cache = PricingCache(cache_dir=tmp_path)
        model = "gpt-4o-mini"
        pricing = {"input_cost_per_1m": 0.150, "output_cost_per_1m": 0.600}

        cache.set(model, pricing)
        retrieved = cache.get(model)

        assert retrieved == pricing

    def test_cache_expires_after_24_hours(self, tmp_path):
        """Cache should expire after 24 hours."""
        cache = PricingCache(cache_dir=tmp_path)
        model = "gpt-4o-mini"
        pricing = {"input_cost_per_1m": 0.150, "output_cost_per_1m": 0.600}

        # Set cache with old timestamp
        cache_file = tmp_path / f"{model}.json"
        old_data = {
            "model": model,
            "pricing": pricing,
            "cached_at": (datetime.now() - timedelta(hours=25)).isoformat(),
        }
        cache_file.write_text(json.dumps(old_data))

        # Should return None for expired cache
        assert cache.get(model) is None

    def test_cache_handles_missing_file(self, tmp_path):
        """Cache should gracefully handle missing cache files."""
        cache = PricingCache(cache_dir=tmp_path)
        assert cache.get("nonexistent-model") is None

    def test_cache_handles_corrupted_file(self, tmp_path):
        """Cache should gracefully handle corrupted cache files."""
        cache = PricingCache(cache_dir=tmp_path)
        cache_file = tmp_path / "gpt-4o-mini.json"
        cache_file.write_text("corrupted json {{{")

        assert cache.get("gpt-4o-mini") is None


class TestPricingSource:
    """Test pricing API sources."""

    @patch("scripts.fetch_model_pricing.requests")
    def test_openrouter_source_fetches_pricing(self, mock_requests):
        """OpenRouter source should fetch pricing via API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "openai/gpt-4o-mini",
                    "pricing": {"prompt": "0.00000015", "completion": "0.0000006"},
                }
            ]
        }
        mock_requests.get.return_value = mock_response

        source = PricingSource.openrouter()
        pricing = source.fetch("gpt-4o-mini")

        assert pricing["input_cost_per_1m"] == 0.150
        assert pricing["output_cost_per_1m"] == 0.600

    @patch("scripts.fetch_model_pricing.requests")
    def test_openrouter_handles_api_errors(self, mock_requests):
        """OpenRouter source should handle API errors gracefully."""
        mock_requests.get.side_effect = Exception("Network error")

        source = PricingSource.openrouter()
        pricing = source.fetch("gpt-4o-mini")

        assert pricing is None

    @patch("scripts.fetch_model_pricing.requests")
    def test_openrouter_handles_model_not_found(self, mock_requests):
        """OpenRouter source should return None for unknown models."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_requests.get.return_value = mock_response

        source = PricingSource.openrouter()
        pricing = source.fetch("unknown-model-xyz")

        assert pricing is None

    def test_fallback_source_provides_defaults(self):
        """Fallback source should provide reasonable defaults."""
        source = PricingSource.fallback()
        pricing = source.fetch("gpt-4o-mini")

        assert pricing is not None
        assert pricing["input_cost_per_1m"] > 0
        assert pricing["output_cost_per_1m"] > 0

    def test_fallback_handles_unknown_models(self):
        """Fallback should use gpt-4o-mini pricing for unknown models."""
        source = PricingSource.fallback()
        default_pricing = source.fetch("gpt-4o-mini")
        unknown_pricing = source.fetch("unknown-model-xyz")

        assert unknown_pricing == default_pricing


class TestModelPricingFetcher:
    """Test the main pricing fetcher."""

    def test_fetcher_tries_cache_first(self, tmp_path):
        """Fetcher should check cache before hitting API."""
        cache = PricingCache(cache_dir=tmp_path)
        model = "gpt-4o-mini"
        cached_pricing = {"input_cost_per_1m": 0.150, "output_cost_per_1m": 0.600}
        cache.set(model, cached_pricing)

        fetcher = ModelPricingFetcher(cache_dir=tmp_path)
        with patch.object(PricingSource, "openrouter") as mock_source:
            pricing = fetcher.fetch(model)
            # Should not call API if cache hit
            mock_source.assert_not_called()
            assert pricing == cached_pricing

    @patch("scripts.fetch_model_pricing.PricingSource.openrouter")
    def test_fetcher_falls_back_on_api_failure(self, mock_source, tmp_path):
        """Fetcher should use fallback if API fails."""
        mock_source.return_value.fetch.return_value = None

        fetcher = ModelPricingFetcher(cache_dir=tmp_path)
        pricing = fetcher.fetch("gpt-4o-mini")

        assert pricing is not None
        assert pricing["input_cost_per_1m"] > 0

    @patch("scripts.fetch_model_pricing.PricingSource.openrouter")
    def test_fetcher_caches_api_results(self, mock_source, tmp_path):
        """Fetcher should cache successful API results."""
        api_pricing = {"input_cost_per_1m": 0.150, "output_cost_per_1m": 0.600}
        mock_source.return_value.fetch.return_value = api_pricing

        fetcher = ModelPricingFetcher(cache_dir=tmp_path)
        pricing = fetcher.fetch("gpt-4o-mini")

        # Should cache the result
        cache = PricingCache(cache_dir=tmp_path)
        cached = cache.get("gpt-4o-mini")
        assert cached == api_pricing
        assert pricing == api_pricing


class TestShellIntegration:
    """Test shell script integration."""

    def test_fetch_pricing_for_shell_outputs_env_vars(self, tmp_path):
        """Shell integration should output env var format."""
        with patch("scripts.fetch_model_pricing.ModelPricingFetcher.fetch") as mock_fetch:
            mock_fetch.return_value = {
                "input_cost_per_1m": 0.150,
                "output_cost_per_1m": 0.600,
            }

            output = fetch_pricing_for_shell("gpt-4o-mini", cache_dir=tmp_path)

            assert "TARS_INPUT_COST_PER_1M=0.150" in output
            assert "TARS_OUTPUT_COST_PER_1M=0.600" in output

    def test_fetch_pricing_for_shell_handles_errors(self, tmp_path):
        """Shell integration should output reasonable defaults on error."""
        with patch("scripts.fetch_model_pricing.ModelPricingFetcher.fetch") as mock_fetch:
            mock_fetch.return_value = None

            output = fetch_pricing_for_shell("unknown-model", cache_dir=tmp_path)

            # Should still output valid env vars (fallback)
            assert "TARS_INPUT_COST_PER_1M=" in output
            assert "TARS_OUTPUT_COST_PER_1M=" in output


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_real_openrouter_api_call(self):
        """
        Real API test - only runs if OPENROUTER_API_KEY is set.

        This test actually calls OpenRouter API to verify integration.
        Skip if API key not available.
        """
        if not os.getenv("OPENROUTER_API_KEY"):
            pytest.skip("OPENROUTER_API_KEY not set - skipping live API test")

        source = PricingSource.openrouter()
        pricing = source.fetch("gpt-4o-mini")

        assert pricing is not None
        assert "input_cost_per_1m" in pricing
        assert "output_cost_per_1m" in pricing
        assert pricing["input_cost_per_1m"] > 0
        assert pricing["output_cost_per_1m"] > 0

    def test_cli_script_execution(self, tmp_path):
        """Test running the script from command line."""
        import subprocess

        result = subprocess.run(
            ["python3", "scripts/fetch_model_pricing.py", "gpt-4o-mini"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "TARS_INPUT_COST_PER_1M=" in result.stdout
        assert "TARS_OUTPUT_COST_PER_1M=" in result.stdout


# Validation tests
def test_pricing_values_are_reasonable():
    """Pricing values should be in expected ranges (sanity check)."""
    source = PricingSource.fallback()
    pricing = source.fetch("gpt-4o-mini")

    # GPT-4o-mini should cost less than $1 per 1M tokens
    assert 0 < pricing["input_cost_per_1m"] < 1.0
    assert 0 < pricing["output_cost_per_1m"] < 1.0

    # Output should cost more than input (typical pattern)
    assert pricing["output_cost_per_1m"] > pricing["input_cost_per_1m"]
