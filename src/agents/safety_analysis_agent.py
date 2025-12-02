"""
Safety Analysis Agent: Graham-Buffett Investment Safety

Responsibilities:
- Analyze investment opportunities using Graham-Buffett principles
- Calculate margin of safety (intrinsic value vs market price)
- Screen for quality companies (fundamentals, debt, earnings)
- Enforce circle of competence
- Provide safety ratings and recommendations

Ensures we only invest in quality companies at attractive prices.
"""

import builtins
import contextlib
import logging
from typing import Any

from src.safety.graham_buffett_safety import (
    SafetyRating,
    get_global_safety_analyzer,
)

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class SafetyAnalysisAgent(BaseAgent):
    """
    Safety Analysis Agent implements Graham-Buffett investment safety principles.

    Key functions:
    - Margin of Safety analysis (intrinsic value vs market price)
    - Quality company screening (fundamentals, debt, earnings)
    - Circle of competence enforcement
    - Safety rating assignment
    """

    def __init__(self, min_margin_of_safety: float = 0.20):
        super().__init__(
            name="SafetyAnalysisAgent",
            role="Graham-Buffett investment safety analysis",
        )
        self.safety_analyzer = get_global_safety_analyzer()
        self.min_margin_of_safety = min_margin_of_safety

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze investment opportunity using Graham-Buffett principles.

        Args:
            data: Contains symbol, market_price, and optional context

        Returns:
            Safety analysis with rating, margin of safety, quality score, and recommendation
        """
        symbol = data.get("symbol", "UNKNOWN")
        market_price = data.get("market_price", 0.0)
        force_refresh = data.get("force_refresh", False)

        if market_price <= 0:
            return {
                "action": "REJECT",
                "reason": "Invalid market price",
                "safety_rating": SafetyRating.REJECT.value,
                "confidence": 0.0,
            }

        # Perform safety analysis
        try:
            safety_analysis = self.safety_analyzer.analyze_safety(
                symbol=symbol,
                market_price=market_price,
                force_refresh=force_refresh,
            )

            # Get memory context for LLM reasoning
            memory_context = self.get_memory_context(limit=5)

            # Build comprehensive prompt for LLM reasoning
            prompt = self._build_analysis_prompt(safety_analysis, memory_context)

            # Get LLM analysis for additional insights
            llm_response = self.reason_with_llm(prompt)

            # Combine safety analysis with LLM insights
            analysis = self._combine_analysis(safety_analysis, llm_response)

            # Log decision
            self.log_decision(analysis)

            return analysis

        except Exception as e:
            logger.error(f"Safety analysis error for {symbol}: {e}")
            return {
                "action": "REJECT",
                "reason": f"Safety analysis failed: {str(e)}",
                "safety_rating": SafetyRating.REJECT.value,
                "confidence": 0.0,
            }

    def _build_analysis_prompt(self, safety_analysis: Any, memory_context: str) -> str:
        """Build LLM prompt for safety analysis reasoning."""

        margin_info = ""
        if safety_analysis.margin_of_safety_pct is not None:
            margin_info = f"""
MARGIN OF SAFETY: {safety_analysis.margin_of_safety_pct * 100:.1f}%
- Intrinsic Value: ${safety_analysis.intrinsic_value:.2f}
- Market Price: ${safety_analysis.market_price:.2f}
- Required Minimum: {self.min_margin_of_safety * 100:.1f}%
"""
        else:
            margin_info = "MARGIN OF SAFETY: Unable to calculate (DCF unavailable)"

        quality_info = ""
        if safety_analysis.quality:
            q = safety_analysis.quality
            quality_info = f"""
QUALITY METRICS:
- Quality Score: {q.quality_score:.1f}/100
- Debt-to-Equity: {q.debt_to_equity if q.debt_to_equity else "N/A"}
- Current Ratio: {q.current_ratio if q.current_ratio else "N/A"}
- ROE: {q.roe * 100 if q.roe else "N/A"}%
- ROA: {q.roa * 100 if q.roa else "N/A"}%
- Profit Margin: {q.profit_margin * 100 if q.profit_margin else "N/A"}%
- Earnings Growth (3Y): {q.earnings_growth_3y * 100 if q.earnings_growth_3y else "N/A"}%
- Earnings Consistency: {q.earnings_consistency:.2f}
"""
        else:
            quality_info = "QUALITY METRICS: Unable to calculate"

        # Goldilocks Prompt: Graham-Buffett principles with clear examples
        prompt = f"""Evaluate {safety_analysis.symbol} safety. Only invest in quality at fair prices.

ANALYSIS:
{margin_info}
{quality_info}
Rating: {safety_analysis.safety_rating.value.upper()}
Reasons: {", ".join(safety_analysis.reasons[:3])}
Warnings: {", ".join(safety_analysis.warnings[:2]) if safety_analysis.warnings else "None"}

{memory_context}

GRAHAM-BUFFETT PRINCIPLES:
- Margin of Safety >20% required (buy $1 for $0.80)
- Quality Score >60 (consistent earnings, low debt, strong ROE)
- Circle of Competence: only invest in understandable businesses
- Price is what you pay, value is what you get

EXAMPLES:
Example 1 - Approve (Strong Safety):
SAFETY_SCORE: 8
MARGIN_EVAL: EXCELLENT
QUALITY_EVAL: GOOD
RECOMMENDATION: APPROVE
CONFIDENCE: 0.85
SAFETY_FACTORS: 35% margin of safety, 15-year earnings consistency, fortress balance sheet
RISK_FACTORS: Cyclical business, commodity price exposure
THESIS: Trading well below intrinsic value with quality fundamentals. Classic Graham value opportunity.

Example 2 - Reject (Insufficient Margin):
SAFETY_SCORE: 4
MARGIN_EVAL: POOR
QUALITY_EVAL: GOOD
RECOMMENDATION: REJECT
CONFIDENCE: 0.72
SAFETY_FACTORS: Strong business quality, market leader position
RISK_FACTORS: Only 8% margin of safety - insufficient buffer for errors
THESIS: Good company but price offers no safety cushion. Wait for 20%+ discount.

Example 3 - Reject (Quality Concerns):
SAFETY_SCORE: 3
MARGIN_EVAL: ADEQUATE
QUALITY_EVAL: POOR
RECOMMENDATION: REJECT
CONFIDENCE: 0.80
SAFETY_FACTORS: 25% apparent margin, low P/E ratio
RISK_FACTORS: Erratic earnings, high debt, declining ROE - value trap signals
THESIS: Cheap for a reason. Low quality negates margin of safety. Avoid.

NOW EVALUATE {safety_analysis.symbol}:
SAFETY_SCORE: [1-10]
MARGIN_EVAL: [EXCELLENT/GOOD/ADEQUATE/POOR/NONE]
QUALITY_EVAL: [EXCELLENT/GOOD/ADEQUATE/POOR]
RECOMMENDATION: [APPROVE/REJECT]
CONFIDENCE: [0-1]
SAFETY_FACTORS: [top 2 safety factors]
RISK_FACTORS: [top 2 risks]
THESIS: [2 sentences on investment merit]"""

        return prompt

    def _combine_analysis(
        self, safety_analysis: Any, llm_response: dict[str, Any]
    ) -> dict[str, Any]:
        """Combine safety analysis with LLM insights."""

        # Parse LLM response
        llm_analysis = self._parse_llm_response(llm_response.get("reasoning", ""))

        # Determine action based on safety rating
        should_approve = safety_analysis.safety_rating in [
            SafetyRating.EXCELLENT,
            SafetyRating.GOOD,
            SafetyRating.ACCEPTABLE,
        ]

        action = "APPROVE" if should_approve else "REJECT"

        # Combine into comprehensive analysis
        analysis = {
            "symbol": safety_analysis.symbol,
            "market_price": safety_analysis.market_price,
            "intrinsic_value": safety_analysis.intrinsic_value,
            "margin_of_safety_pct": safety_analysis.margin_of_safety_pct,
            "quality_score": (
                safety_analysis.quality.quality_score if safety_analysis.quality else None
            ),
            "safety_rating": safety_analysis.safety_rating.value,
            "action": action,
            "confidence": llm_analysis.get("confidence", 0.5),
            "safety_score": llm_analysis.get("safety_score", 5),
            "margin_eval": llm_analysis.get("margin_eval", "NONE"),
            "quality_eval": llm_analysis.get("quality_eval", "POOR"),
            "safety_factors": llm_analysis.get("safety_factors", ""),
            "risk_factors": llm_analysis.get("risk_factors", ""),
            "thesis": llm_analysis.get("thesis", ""),
            "reasons": safety_analysis.reasons,
            "warnings": safety_analysis.warnings,
            "full_reasoning": llm_response.get("reasoning", ""),
            "timestamp": safety_analysis.timestamp.isoformat(),
        }

        return analysis

    def _parse_llm_response(self, reasoning: str) -> dict[str, Any]:
        """Parse LLM response into structured format."""
        lines = reasoning.split("\n")
        analysis = {
            "safety_score": 5,
            "margin_eval": "NONE",
            "quality_eval": "POOR",
            "recommendation": "REJECT",
            "confidence": 0.5,
            "safety_factors": "",
            "risk_factors": "",
            "thesis": "",
        }

        for line in lines:
            line = line.strip()
            if line.startswith("SAFETY_SCORE:"):
                with contextlib.suppress(builtins.BaseException):
                    analysis["safety_score"] = int(line.split(":")[1].strip())
            elif line.startswith("MARGIN_EVAL:"):
                eval_str = line.split(":")[1].strip().upper()
                if eval_str in ["EXCELLENT", "GOOD", "ADEQUATE", "POOR", "NONE"]:
                    analysis["margin_eval"] = eval_str
            elif line.startswith("QUALITY_EVAL:"):
                eval_str = line.split(":")[1].strip().upper()
                if eval_str in ["EXCELLENT", "GOOD", "ADEQUATE", "POOR"]:
                    analysis["quality_eval"] = eval_str
            elif line.startswith("RECOMMENDATION:"):
                rec = line.split(":")[1].strip().upper()
                if rec in ["APPROVE", "REJECT"]:
                    analysis["recommendation"] = rec
            elif line.startswith("CONFIDENCE:"):
                with contextlib.suppress(builtins.BaseException):
                    analysis["confidence"] = float(line.split(":")[1].strip())
            elif line.startswith("SAFETY_FACTORS:"):
                analysis["safety_factors"] = line.split(":", 1)[1].strip()
            elif line.startswith("RISK_FACTORS:"):
                analysis["risk_factors"] = line.split(":", 1)[1].strip()
            elif line.startswith("THESIS:"):
                analysis["thesis"] = line.split(":", 1)[1].strip()

        return analysis
