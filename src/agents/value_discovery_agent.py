"""
Value Discovery Agent: Find Undervalued Opportunities

Responsibilities:
- Scan for undervalued stocks with margin of safety
- Identify quality companies trading below intrinsic value
- Rank opportunities by safety and value
- Provide investment recommendations

Finds the best value investment opportunities.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from src.safety.graham_buffett_safety import (
    get_global_safety_analyzer,
)

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ValueDiscoveryAgent(BaseAgent):
    """
    Value Discovery Agent finds undervalued investment opportunities.

    Key functions:
    - Scan watchlist for undervalued stocks
    - Calculate margin of safety for each
    - Rank by safety and value
    - Recommend best opportunities
    """

    def __init__(self):
        super().__init__(
            name="ValueDiscoveryAgent",
            role="Discover undervalued investment opportunities",
        )
        self.safety_analyzer = get_global_safety_analyzer()

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Discover undervalued opportunities from watchlist.

        Args:
            data: Contains watchlist (list of symbols) and optional market prices

        Returns:
            List of undervalued opportunities ranked by safety and value
        """
        watchlist = data.get("watchlist", [])
        market_prices = data.get("market_prices", {})

        if not watchlist:
            return {
                "action": "NO_OPPORTUNITIES",
                "message": "No symbols in watchlist",
                "opportunities": [],
            }

        opportunities = []

        # Analyze each symbol in watchlist
        for symbol in watchlist:
            try:
                # Get market price
                market_price = market_prices.get(symbol)
                if not market_price:
                    # Try to fetch current price
                    market_price = self._get_current_price(symbol)
                    if not market_price:
                        continue

                # Perform safety analysis
                safety_analysis = self.safety_analyzer.analyze_safety(
                    symbol=symbol,
                    market_price=market_price,
                    force_refresh=False,
                )

                # Only include opportunities with margin of safety
                if (
                    safety_analysis.margin_of_safety_pct is not None
                    and safety_analysis.margin_of_safety_pct > 0
                ):
                    opportunity = {
                        "symbol": symbol,
                        "market_price": market_price,
                        "intrinsic_value": safety_analysis.intrinsic_value,
                        "margin_of_safety_pct": safety_analysis.margin_of_safety_pct,
                        "quality_score": (
                            safety_analysis.quality.quality_score
                            if safety_analysis.quality
                            else None
                        ),
                        "safety_rating": safety_analysis.safety_rating.value,
                        "reasons": safety_analysis.reasons,
                        "warnings": safety_analysis.warnings,
                    }

                    # Calculate opportunity score (combination of margin and quality)
                    opportunity["opportunity_score"] = self._calculate_opportunity_score(
                        opportunity
                    )

                    opportunities.append(opportunity)

            except Exception as e:
                logger.warning(f"Error analyzing {symbol} for value discovery: {e}")
                continue

        # Sort by opportunity score (highest first)
        opportunities.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)

        # Get LLM analysis of top opportunities
        memory_context = self.get_memory_context(limit=5)

        prompt = self._build_discovery_prompt(opportunities[:10], memory_context)

        llm_response = self.reason_with_llm(prompt)

        # Combine analysis
        analysis = self._combine_discovery_analysis(opportunities, llm_response)

        # Log decision
        self.log_decision(analysis)

        return analysis

    def _calculate_opportunity_score(self, opportunity: dict[str, Any]) -> float:
        """Calculate composite opportunity score (0-100)."""

        margin_pct = opportunity.get("margin_of_safety_pct", 0.0)
        quality_score = opportunity.get("quality_score", 0.0)
        safety_rating = opportunity.get("safety_rating", "reject")

        # Margin of safety component (0-50 points)
        margin_score = min(margin_pct * 100, 50.0)  # Cap at 50 points

        # Quality component (0-40 points)
        quality_component = (quality_score / 100.0) * 40.0

        # Safety rating component (0-10 points)
        rating_scores = {
            "excellent": 10,
            "good": 7,
            "acceptable": 4,
            "poor": 1,
            "reject": 0,
        }
        rating_component = rating_scores.get(safety_rating, 0)

        total_score = margin_score + quality_component + rating_component

        return round(total_score, 1)

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for symbol."""
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d")
            if not data.empty:
                return float(data["Close"].iloc[-1])
            return None
        except Exception as e:
            logger.warning(f"Error fetching price for {symbol}: {e}")
            return None

    def _build_discovery_prompt(self, opportunities: list[dict], memory_context: str) -> str:
        """Build LLM prompt for value discovery analysis."""

        opportunities_summary = ""
        for i, opp in enumerate(opportunities[:5], 1):  # Top 5
            opportunities_summary += f"""
{i}. {opp["symbol"]}:
   - Market Price: ${opp["market_price"]:.2f}
   - Intrinsic Value: ${opp["intrinsic_value"]:.2f}
   - Margin of Safety: {opp["margin_of_safety_pct"] * 100:.1f}%
   - Quality Score: {opp["quality_score"]:.1f}/100
   - Safety Rating: {opp["safety_rating"].upper()}
   - Opportunity Score: {opp["opportunity_score"]:.1f}/100
"""

        prompt = f"""You are a Value Discovery Agent identifying the best investment opportunities.

TOP OPPORTUNITIES:
{opportunities_summary}

{memory_context}

TASK: Provide value discovery analysis:
1. Best Opportunity (symbol and why)
2. Overall Market Assessment (VALUE-RICH / MIXED / OVERVALUED)
3. Recommended Action (BUY_NOW / WAIT / AVOID)
4. Top 3 Picks (ranked by safety and value)
5. Investment Strategy (how to approach these opportunities)

Format your response as:
BEST_OPPORTUNITY: [symbol and reasoning]
MARKET_ASSESSMENT: [VALUE-RICH/MIXED/OVERVALUED]
RECOMMENDED_ACTION: [BUY_NOW/WAIT/AVOID]
TOP_3_PICKS: [symbol1, symbol2, symbol3]
STRATEGY: [investment strategy]"""

        return prompt

    def _combine_discovery_analysis(
        self, opportunities: list[dict], llm_response: dict[str, Any]
    ) -> dict[str, Any]:
        """Combine opportunities with LLM insights."""

        llm_analysis = self._parse_llm_response(llm_response.get("reasoning", ""))

        analysis = {
            "action": "OPPORTUNITIES_FOUND" if opportunities else "NO_OPPORTUNITIES",
            "total_opportunities": len(opportunities),
            "opportunities": opportunities,
            "best_opportunity": llm_analysis.get("best_opportunity", ""),
            "market_assessment": llm_analysis.get("market_assessment", "MIXED"),
            "recommended_action": llm_analysis.get("recommended_action", "WAIT"),
            "top_3_picks": llm_analysis.get("top_3_picks", []),
            "strategy": llm_analysis.get("strategy", ""),
            "full_reasoning": llm_response.get("reasoning", ""),
            "timestamp": datetime.now().isoformat(),
        }

        return analysis

    def _parse_llm_response(self, reasoning: str) -> dict[str, Any]:
        """Parse LLM response."""
        lines = reasoning.split("\n")
        analysis = {
            "best_opportunity": "",
            "market_assessment": "MIXED",
            "recommended_action": "WAIT",
            "top_3_picks": [],
            "strategy": "",
        }

        for line in lines:
            line = line.strip()
            if line.startswith("BEST_OPPORTUNITY:"):
                analysis["best_opportunity"] = line.split(":", 1)[1].strip()
            elif line.startswith("MARKET_ASSESSMENT:"):
                assessment = line.split(":")[1].strip().upper()
                if assessment in ["VALUE-RICH", "MIXED", "OVERVALUED"]:
                    analysis["market_assessment"] = assessment
            elif line.startswith("RECOMMENDED_ACTION:"):
                action = line.split(":")[1].strip().upper()
                if action in ["BUY_NOW", "WAIT", "AVOID"]:
                    analysis["recommended_action"] = action
            elif line.startswith("TOP_3_PICKS:"):
                picks_str = line.split(":")[1].strip()
                # Parse comma-separated list
                picks = [p.strip() for p in picks_str.split(",")]
                analysis["top_3_picks"] = picks[:3]
            elif line.startswith("STRATEGY:"):
                analysis["strategy"] = line.split(":", 1)[1].strip()

        return analysis
