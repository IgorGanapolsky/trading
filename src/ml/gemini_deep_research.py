"""
Gemini Deep Research - Autonomous market research for pre-trade analysis.

This module provides autonomous research capabilities using Google's Gemini
API with web search tools for comprehensive pre-trade analysis.

Based on: ll_027_gemini_deep_research.md
Skill: deep_research (SKILL.md)
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.utils.self_healing import with_retry

# Graceful import of google.genai (new unified SDK)
# Falls back to legacy google.generativeai if new SDK not available
try:
    from google import genai

    GENAI_AVAILABLE = True
    GENAI_NEW_SDK = True
except ImportError:
    try:
        import google.generativeai as genai

        GENAI_AVAILABLE = True
        GENAI_NEW_SDK = False
        logging.warning("Using legacy google.generativeai - consider upgrading to google.genai")
    except Exception as e:
        genai = None
        GENAI_AVAILABLE = False
        GENAI_NEW_SDK = False
        logging.warning(f"google.genai not available: {e}")

logger = logging.getLogger(__name__)

# Cache directory for research results
RESEARCH_CACHE_DIR = Path("data/research")
CACHE_TTL_HOURS = 2  # Cache validity in hours


class GeminiDeepResearch:
    """
    Autonomous research agent for pre-trade analysis.

    Uses Gemini's capabilities to research stocks, market conditions,
    and provide actionable trading insights with citations.

    Note: We do NOT trade crypto (lesson LL-052). Stock research only.
    """

    # Default model - using gemini-1.5-pro for web search capability
    DEFAULT_MODEL = "gemini-1.5-pro"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        Initialize Gemini Deep Research agent.

        Args:
            api_key: Google API key (defaults to GOOGLE_API_KEY or GEMINI_API_KEY env var)
            model: Gemini model to use (defaults to gemini-2.0-flash for new SDK)
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        # Use newer model with new SDK
        self.model_name = model or ("gemini-2.0-flash" if GENAI_NEW_SDK else self.DEFAULT_MODEL)
        self.client = None
        self._use_new_sdk = GENAI_NEW_SDK

        if not GENAI_AVAILABLE:
            logger.warning("google.genai not available - Deep Research disabled")
        elif not self.api_key:
            logger.warning("GOOGLE_API_KEY/GEMINI_API_KEY not found - Deep Research unavailable")
        else:
            try:
                if GENAI_NEW_SDK:
                    # New unified SDK
                    self.client = genai.Client(api_key=self.api_key)
                    logger.info(f"GeminiDeepResearch initialized with new SDK ({self.model_name})")
                else:
                    # Legacy SDK
                    genai.configure(api_key=self.api_key)
                    self.client = genai.GenerativeModel(self.model_name)
                    logger.info(
                        f"GeminiDeepResearch initialized with legacy SDK ({self.model_name})"
                    )
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.client = None

        # Ensure cache directory exists
        RESEARCH_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _is_cache_valid(self, cache_file: Path) -> bool:
        """Check if cached research is still valid."""
        if not cache_file.exists():
            return False

        # Check file age
        file_age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        return file_age_hours < CACHE_TTL_HOURS

    def _load_cached_research(self, symbol: str, research_type: str) -> dict | None:
        """Load cached research if valid."""
        today = datetime.now().strftime("%Y-%m-%d")
        cache_file = RESEARCH_CACHE_DIR / f"{symbol}_{research_type}_{today}.json"

        if self._is_cache_valid(cache_file):
            try:
                data = json.loads(cache_file.read_text())
                logger.info(f"Using cached research for {symbol}")
                return data
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")

        return None

    def _save_research_cache(self, symbol: str, research_type: str, data: dict) -> None:
        """Save research to cache."""
        today = datetime.now().strftime("%Y-%m-%d")
        cache_file = RESEARCH_CACHE_DIR / f"{symbol}_{research_type}_{today}.json"

        try:
            cache_file.write_text(json.dumps(data, indent=2))
            logger.info(f"Cached research for {symbol}")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _parse_json_from_response(self, text: str) -> dict | None:
        """Extract JSON from response text, handling markdown code blocks."""
        # Try to find JSON in code blocks first
        json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON object
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def _generate_content(self, prompt: str, temperature: float = 0.3) -> str | None:
        """
        Generate content using the appropriate SDK version.

        Args:
            prompt: The prompt to send
            temperature: Temperature for generation (0.0-1.0)

        Returns:
            Generated text or None on error
        """
        if not self.client:
            return None

        try:
            if self._use_new_sdk:
                # New unified SDK
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config={
                        "temperature": temperature,
                        "max_output_tokens": 4096,
                    },
                )
                return response.text if response else None
            else:
                # Legacy SDK
                response = self.client.generate_content(
                    prompt,
                    generation_config={
                        "temperature": temperature,
                        "top_p": 0.95,
                        "max_output_tokens": 4096,
                    },
                )
                return response.text if response and hasattr(response, "text") else None
        except Exception as e:
            logger.error(f"Content generation failed: {e}")
            return None

    @with_retry(max_attempts=3, backoff=2.0)
    def research_stock(self, symbol: str, context: str = "") -> dict[str, Any]:
        """
        Autonomous deep research on a stock before trading.

        Args:
            symbol: Stock ticker (e.g., "AAPL", "NVDA", "TSLA")
            context: Additional context (e.g., "upcoming earnings")

        Returns:
            Research results with recommendation, catalysts, risks, sources
        """
        if not self.client:
            logger.error("Gemini client not initialized")
            return self._error_response("Gemini client not initialized")

        # Check cache first
        cached = self._load_cached_research(symbol, "stock")
        if cached:
            return cached

        context_str = f" Context: {context}" if context else ""

        prompt = f"""You are a professional equity research analyst. Research {symbol} stock thoroughly and provide actionable trading insights.{context_str}

Analyze:
1. Recent news and developments (last 7 days)
2. Key catalysts (earnings, product launches, partnerships)
3. Major risks (competition, regulation, macro headwinds)
4. Technical levels (support/resistance if mentioned in news)
5. Analyst sentiment and price targets

Provide your response as JSON with this exact structure:
{{
    "symbol": "{symbol}",
    "research_date": "{datetime.now().strftime("%Y-%m-%d")}",
    "summary": "2-3 paragraph executive summary",
    "catalysts": ["catalyst 1", "catalyst 2"],
    "risks": ["risk 1", "risk 2"],
    "sentiment": "bullish/bearish/neutral with score 1-10",
    "recommendation": "BUY/HOLD/SELL",
    "confidence": 0.0 to 1.0,
    "entry_timing": "specific timing recommendation",
    "position_size": "standard/reduced/increased with reasoning",
    "sources": ["source 1", "source 2"]
}}

Be specific and cite real sources. If you cannot find recent information, say so."""

        try:
            response_text = self._generate_content(prompt, temperature=0.3)

            if not response_text:
                return self._error_response("Empty response from Gemini")

            # Parse JSON from response
            result = self._parse_json_from_response(response_text)

            if result:
                # Add metadata
                result["research_type"] = "stock"
                result["model"] = self.model_name
                result["timestamp"] = datetime.now().isoformat()

                # Cache the result
                self._save_research_cache(symbol, "stock", result)
                return result
            else:
                # Return raw text if JSON parsing fails
                return {
                    "symbol": symbol,
                    "research_date": datetime.now().strftime("%Y-%m-%d"),
                    "raw_research": response_text,
                    "recommendation": "HOLD",
                    "confidence": 0.5,
                    "parse_error": "Could not parse structured response",
                }

        except Exception as e:
            logger.error(f"Stock research failed for {symbol}: {e}")
            return self._error_response(str(e))

    @with_retry(max_attempts=3, backoff=2.0)
    def research_market_conditions(self) -> dict[str, Any]:
        """
        Research overall market conditions for risk management.

        Returns:
            Market regime, VIX analysis, Fed outlook, allocation recommendations
        """
        if not self.client:
            logger.error("Gemini client not initialized")
            return self._error_response("Gemini client not initialized")

        # Check cache
        cached = self._load_cached_research("MARKET", "conditions")
        if cached:
            return cached

        prompt = f"""You are a market strategist. Analyze current overall market conditions for trading decisions.

Research:
1. S&P 500 and major indices trend
2. VIX (volatility index) current level and trend
3. Federal Reserve policy outlook
4. Key geopolitical risks
5. Sector rotation trends
6. Risk-on vs risk-off sentiment

Provide your response as JSON:
{{
    "analysis_date": "{datetime.now().strftime("%Y-%m-%d")}",
    "market_regime": "bullish/bearish/neutral/volatile",
    "vix_analysis": {{
        "current": 15.0,
        "level": "low/medium/high",
        "trend": "rising/falling/stable"
    }},
    "fed_outlook": {{
        "next_meeting": "YYYY-MM-DD or unknown",
        "expected_action": "hold/cut/hike",
        "rate_path": "hawkish/dovish/neutral"
    }},
    "allocation": {{
        "stocks": 60,
        "bonds": 25,
        "cash": 15
    }},
    "risk_level": "low/moderate/high",
    "key_risks": ["risk 1", "risk 2"],
    "sector_rotation": {{
        "outperforming": ["sector1", "sector2"],
        "underperforming": ["sector3", "sector4"]
    }},
    "sentiment": "risk_on/risk_off/mixed",
    "sources": ["source 1", "source 2"]
}}

Use current data. If uncertain about specific values, provide reasonable estimates with caveats."""

        try:
            response_text = self._generate_content(prompt, temperature=0.3)

            if not response_text:
                return self._error_response("Empty response from Gemini")

            result = self._parse_json_from_response(response_text)

            if result:
                result["research_type"] = "market_conditions"
                result["model"] = self.model_name
                result["timestamp"] = datetime.now().isoformat()
                self._save_research_cache("MARKET", "conditions", result)
                return result
            else:
                return {
                    "analysis_date": datetime.now().strftime("%Y-%m-%d"),
                    "raw_research": response_text,
                    "market_regime": "unknown",
                    "risk_level": "moderate",
                    "parse_error": "Could not parse structured response",
                }

        except Exception as e:
            logger.error(f"Market conditions research failed: {e}")
            return self._error_response(str(e))

    def get_pre_trade_analysis(self, symbol: str, asset_type: str = "stock") -> dict[str, Any]:
        """
        Comprehensive pre-trade analysis before executing a trade.

        Args:
            symbol: Trading symbol
            asset_type: "stock" only (we don't trade crypto - LL-052)

        Returns:
            Combined analysis with recommendation
        """
        # Enforce no crypto trading (LL-052)
        if asset_type.lower() == "crypto":
            logger.warning(f"Crypto trading not allowed (LL-052): {symbol}")
            return {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "analysis_available": False,
                "error": "Crypto trading disabled per LL-052",
                "recommendation": "NO_TRADE",
                "confidence": 0.0,
            }

        # Get stock research
        research = self.research_stock(symbol)

        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "analysis_available": "error" not in research,
            "recommendation": research.get("recommendation", "HOLD"),
            "confidence": research.get("confidence", 0.5),
            "research": research,
        }

    def _error_response(self, error_msg: str) -> dict[str, Any]:
        """Generate standardized error response."""
        return {
            "error": error_msg,
            "timestamp": datetime.now().isoformat(),
            "recommendation": "HOLD",
            "confidence": 0.0,
            "analysis_available": False,
        }


# Singleton instance
_researcher: GeminiDeepResearch | None = None


@lru_cache(maxsize=1)
def get_researcher() -> GeminiDeepResearch:
    """
    Get singleton GeminiDeepResearch instance.

    Returns:
        Configured GeminiDeepResearch instance
    """
    global _researcher
    if _researcher is None:
        _researcher = GeminiDeepResearch()
    return _researcher


def clear_researcher_cache() -> None:
    """Clear the researcher singleton (for testing)."""
    global _researcher
    _researcher = None
    get_researcher.cache_clear()


if __name__ == "__main__":
    # Test the implementation
    import sys

    logging.basicConfig(level=logging.INFO)

    researcher = get_researcher()

    if not researcher.client:
        print("ERROR: GOOGLE_API_KEY not set")
        sys.exit(1)

    print("Testing GeminiDeepResearch...")
    print("-" * 50)

    # Test stock research
    print("\n1. Testing stock research (AAPL)...")
    result = researcher.research_stock("AAPL")
    print(json.dumps(result, indent=2, default=str))

    # Test market conditions
    print("\n2. Testing market conditions research...")
    result = researcher.research_market_conditions()
    print(json.dumps(result, indent=2, default=str))

    # Test pre-trade analysis
    print("\n3. Testing pre-trade analysis (NVDA)...")
    result = researcher.get_pre_trade_analysis("NVDA")
    print(json.dumps(result, indent=2, default=str))

    # Test crypto block (should fail)
    print("\n4. Testing crypto block (should fail)...")
    result = researcher.get_pre_trade_analysis("BTC", asset_type="crypto")
    print(json.dumps(result, indent=2, default=str))

    print("\n" + "-" * 50)
    print("Deep Research tests completed!")
