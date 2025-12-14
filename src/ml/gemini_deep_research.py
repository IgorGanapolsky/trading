"""
Gemini Deep Research Integration for Trading
Uses Google's new Interactions API for autonomous market research
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Check if google-genai is available
try:
    from google import genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-genai not installed. Run: pip install google-genai")


class GeminiDeepResearch:
    """
    Autonomous market research using Gemini Deep Research agent.
    Analyzes financials, news, sentiment before trading decisions.
    """

    def __init__(self):
        self.client = None
        if GEMINI_AVAILABLE:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if api_key:
                self.client = genai.Client(api_key=api_key)
                logger.info("✅ Gemini Deep Research initialized")
            else:
                logger.warning("⚠️ No GOOGLE_API_KEY found")

    def research_crypto_market(self, symbol: str = "BTC") -> Optional[dict[str, Any]]:
        """
        Deep research on crypto market conditions before trading.
        Returns sentiment, key news, and trading recommendation.
        """
        if not self.client:
            return None

        query = f"""
        Research current {symbol} cryptocurrency market conditions for trading:

        1. Latest news and developments (last 24-48 hours)
        2. Market sentiment from social media and news
        3. Key support/resistance levels
        4. Any upcoming events (ETF decisions, halvings, regulations)
        5. Fear & Greed index analysis
        6. Whale wallet movements if available

        Provide a trading recommendation: BUY, SELL, or HOLD with confidence level.
        Format as JSON with keys: sentiment, news_summary, recommendation, confidence, key_levels
        """

        return self._run_research(query, f"{symbol}_market_research")

    def research_stock(self, symbol: str) -> Optional[dict[str, Any]]:
        """
        Deep research on a stock before trading.
        """
        if not self.client:
            return None

        query = f"""
        Research {symbol} stock for trading decision:

        1. Recent earnings and financial health
        2. Latest news and analyst ratings
        3. Technical analysis (RSI, MACD, moving averages)
        4. Institutional ownership changes
        5. Upcoming catalysts (earnings dates, FDA approvals, etc.)
        6. Sector performance comparison

        Provide a trading recommendation: BUY, SELL, or HOLD with confidence level.
        Format as JSON with keys: fundamentals, technicals, sentiment, recommendation, confidence, target_price
        """

        return self._run_research(query, f"{symbol}_stock_research")

    def research_market_conditions(self) -> Optional[dict[str, Any]]:
        """
        Research overall market conditions for risk management.
        """
        if not self.client:
            return None

        query = """
        Research current overall market conditions:

        1. S&P 500 and major indices trend
        2. VIX (volatility index) analysis
        3. Fed policy and interest rate outlook
        4. Geopolitical risks
        5. Sector rotation trends
        6. Risk-on vs Risk-off sentiment

        Recommend portfolio allocation: % stocks, % crypto, % cash
        Format as JSON with keys: market_regime, vix_analysis, allocation, risk_level, key_risks
        """

        return self._run_research(query, "market_conditions")

    def _run_research(
        self, query: str, research_name: str, timeout: int = 300
    ) -> Optional[dict[str, Any]]:
        """
        Execute deep research query and wait for results.
        """
        try:
            logger.info(f"🔍 Starting deep research: {research_name}")

            interaction = self.client.interactions.create(
                input=query, agent="deep-research-pro-preview-12-2025", background=True
            )

            logger.info(f"Research ID: {interaction.id}")

            start_time = time.time()
            while time.time() - start_time < timeout:
                interaction = self.client.interactions.get(interaction.id)

                if interaction.status == "completed":
                    result_text = interaction.outputs[-1].text
                    logger.info(f"✅ Research completed: {research_name}")

                    # Try to parse as JSON
                    try:
                        # Find JSON in response
                        import re

                        json_match = re.search(r"\{.*\}", result_text, re.DOTALL)
                        if json_match:
                            return json.loads(json_match.group())
                    except:
                        pass

                    # Return raw text if JSON parse fails
                    return {"raw_research": result_text, "research_name": research_name}

                elif interaction.status == "failed":
                    logger.error(f"❌ Research failed: {interaction.error}")
                    return None

                time.sleep(10)

            logger.warning(f"⚠️ Research timeout: {research_name}")
            return None

        except Exception as e:
            logger.error(f"Research error: {e}")
            return None

    def get_pre_trade_analysis(self, symbol: str, asset_type: str = "crypto") -> dict[str, Any]:
        """
        Get comprehensive pre-trade analysis before executing a trade.
        """
        result = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "analysis_available": False,
            "recommendation": "HOLD",
            "confidence": 0.5,
        }

        if not self.client:
            logger.warning("Gemini not available, using default analysis")
            return result

        if asset_type == "crypto":
            research = self.research_crypto_market(symbol.replace("USD", "").replace("/", ""))
        else:
            research = self.research_stock(symbol)

        if research:
            result["analysis_available"] = True
            result["research"] = research
            result["recommendation"] = research.get("recommendation", "HOLD")
            result["confidence"] = research.get("confidence", 0.5)

        return result


# Singleton instance
_researcher = None


def get_researcher() -> GeminiDeepResearch:
    global _researcher
    if _researcher is None:
        _researcher = GeminiDeepResearch()
    return _researcher


if __name__ == "__main__":
    # Test the integration
    logging.basicConfig(level=logging.INFO)
    researcher = get_researcher()

    print("Testing Gemini Deep Research for Trading...")
    result = researcher.research_crypto_market("BTC")
    print(json.dumps(result, indent=2) if result else "No result (API key needed)")
