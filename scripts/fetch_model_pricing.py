#!/usr/bin/env python3
"""
Dynamic Model Pricing Fetcher

Fetches real-time pricing for LLM models from OpenRouter API.
Caches results for 24 hours to minimize API calls.
Falls back to reasonable defaults if API unavailable.

Usage:
    python3 scripts/fetch_model_pricing.py gpt-4o-mini
    # Outputs: TARS_INPUT_COST_PER_1M=0.150 TARS_OUTPUT_COST_PER_1M=0.600

Integration with tars_autopilot.sh:
    eval "$(python3 scripts/fetch_model_pricing.py "$OPENAI_MODEL")"
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None  # type: ignore

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


@dataclass
class ModelPricing:
    """Model pricing data."""

    input_cost_per_1m: float
    output_cost_per_1m: float


class PricingCache:
    """24-hour cache for pricing data."""

    CACHE_TTL_HOURS = 24

    def __init__(self, cache_dir: Path | str | None = None):
        """
        Initialize cache.

        Args:
            cache_dir: Directory for cache files (default: .cache/pricing)
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "trading_pricing"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, model: str) -> dict[str, float] | None:
        """
        Get cached pricing if still valid.

        Args:
            model: Model name

        Returns:
            Cached pricing or None if expired/missing
        """
        cache_file = self._cache_path(model)
        if not cache_file.exists():
            return None

        try:
            data = json.loads(cache_file.read_text())
            cached_at = datetime.fromisoformat(data["cached_at"])
            age = datetime.now() - cached_at

            if age > timedelta(hours=self.CACHE_TTL_HOURS):
                logger.debug(f"Cache expired for {model} (age: {age})")
                return None

            return data["pricing"]
        except Exception as e:
            logger.warning(f"Cache read error for {model}: {e}")
            return None

    def set(self, model: str, pricing: dict[str, float]) -> None:
        """
        Cache pricing data.

        Args:
            model: Model name
            pricing: Pricing data
        """
        cache_file = self._cache_path(model)
        data = {
            "model": model,
            "pricing": pricing,
            "cached_at": datetime.now().isoformat(),
        }
        try:
            cache_file.write_text(json.dumps(data, indent=2))
            logger.debug(f"Cached pricing for {model}")
        except Exception as e:
            logger.warning(f"Cache write error for {model}: {e}")

    def _cache_path(self, model: str) -> Path:
        """Get cache file path for model."""
        safe_name = model.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe_name}.json"


class PricingSource:
    """Pricing data sources."""

    @staticmethod
    def openrouter() -> OpenRouterSource:
        """Get OpenRouter pricing source."""
        return OpenRouterSource()

    @staticmethod
    def fallback() -> FallbackSource:
        """Get fallback pricing source."""
        return FallbackSource()


class OpenRouterSource:
    """Fetch pricing from OpenRouter API."""

    API_URL = "https://openrouter.ai/api/v1/models"

    def fetch(self, model: str) -> dict[str, float] | None:
        """
        Fetch pricing from OpenRouter.

        Args:
            model: Model name (e.g., "gpt-4o-mini" or "openai/gpt-4o-mini")

        Returns:
            Pricing dict or None on error
        """
        try:
            if requests is None:
                logger.warning("requests module not available")
                return None

            # Normalize model name for OpenRouter
            if "/" not in model:
                model = f"openai/{model}"

            response = requests.get(self.API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            for entry in data.get("data", []):
                if entry.get("id") == model:
                    pricing_data = entry.get("pricing", {})
                    return {
                        "input_cost_per_1m": float(pricing_data.get("prompt", 0)) * 1_000_000,
                        "output_cost_per_1m": float(pricing_data.get("completion", 0)) * 1_000_000,
                    }

            logger.warning(f"Model {model} not found in OpenRouter API")
            return None

        except Exception as e:
            logger.warning(f"OpenRouter API error: {e}")
            return None


class FallbackSource:
    """Fallback pricing based on known rates."""

    # Last known OpenAI pricing as of Jan 2025
    DEFAULT_PRICING = {
        "gpt-4o-mini": {"input_cost_per_1m": 0.150, "output_cost_per_1m": 0.600},
        "gpt-4o": {"input_cost_per_1m": 2.50, "output_cost_per_1m": 10.00},
        "gpt-4": {"input_cost_per_1m": 30.00, "output_cost_per_1m": 60.00},
        "gpt-3.5-turbo": {"input_cost_per_1m": 0.50, "output_cost_per_1m": 1.50},
    }

    def fetch(self, model: str) -> dict[str, float]:
        """
        Get fallback pricing.

        Args:
            model: Model name

        Returns:
            Pricing dict (always succeeds)
        """
        # Normalize model name
        base_model = model.split("/")[-1]

        if base_model in self.DEFAULT_PRICING:
            return self.DEFAULT_PRICING[base_model]

        # Unknown model - use gpt-4o-mini as safe default
        logger.warning(f"Unknown model {model}, using gpt-4o-mini pricing")
        return self.DEFAULT_PRICING["gpt-4o-mini"]


class ModelPricingFetcher:
    """Main pricing fetcher with caching and fallback."""

    def __init__(self, cache_dir: Path | str | None = None):
        """
        Initialize fetcher.

        Args:
            cache_dir: Cache directory path
        """
        self.cache = PricingCache(cache_dir)

    def fetch(self, model: str) -> dict[str, float]:
        """
        Fetch pricing with cache and fallback.

        Args:
            model: Model name

        Returns:
            Pricing dict (always succeeds via fallback)
        """
        # Try cache first
        cached = self.cache.get(model)
        if cached:
            logger.debug(f"Cache hit for {model}")
            return cached

        # Try API
        logger.debug(f"Cache miss for {model}, fetching from API")
        api_pricing = PricingSource.openrouter().fetch(model)

        if api_pricing:
            self.cache.set(model, api_pricing)
            return api_pricing

        # Fall back to defaults
        logger.debug(f"API failed for {model}, using fallback")
        fallback_pricing = PricingSource.fallback().fetch(model)
        self.cache.set(model, fallback_pricing)
        return fallback_pricing


def fetch_pricing_for_shell(model: str, cache_dir: Path | str | None = None) -> str:
    """
    Fetch pricing and format for shell consumption.

    Args:
        model: Model name
        cache_dir: Cache directory

    Returns:
        Shell env var string: "TARS_INPUT_COST_PER_1M=X TARS_OUTPUT_COST_PER_1M=Y"
    """
    fetcher = ModelPricingFetcher(cache_dir)
    pricing = fetcher.fetch(model)

    if not pricing:
        # Should never happen (fetcher has fallback), but be defensive
        pricing = PricingSource.fallback().fetch(model)

    return (
        f"TARS_INPUT_COST_PER_1M={pricing['input_cost_per_1m']:.3f} "
        f"TARS_OUTPUT_COST_PER_1M={pricing['output_cost_per_1m']:.3f}"
    )


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch real-time model pricing for TARS smoke tests"
    )
    parser.add_argument("model", help="Model name (e.g., gpt-4o-mini)")
    parser.add_argument("--cache-dir", help="Cache directory", type=Path, default=None)
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        output = fetch_pricing_for_shell(args.model, args.cache_dir)
        print(output)
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        # Still output fallback on error
        fallback = PricingSource.fallback().fetch(args.model)
        print(
            f"TARS_INPUT_COST_PER_1M={fallback['input_cost_per_1m']} "
            f"TARS_OUTPUT_COST_PER_1M={fallback['output_cost_per_1m']}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
