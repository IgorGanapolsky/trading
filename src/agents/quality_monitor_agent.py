"""
Quality Monitor Agent: Portfolio Quality Monitoring

Responsibilities:
- Monitor portfolio quality over time
- Detect quality deterioration in holdings
- Recommend position adjustments based on quality changes
- Track quality trends and provide alerts

Ensures portfolio maintains high quality standards.
"""

import builtins
import contextlib
import logging
from datetime import datetime
from typing import Any

from src.safety.graham_buffett_safety import (
    CompanyQuality,
    get_global_safety_analyzer,
)

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class QualityMonitorAgent(BaseAgent):
    """
    Quality Monitor Agent tracks portfolio quality over time.

    Key functions:
    - Monitor quality scores of all holdings
    - Detect quality deterioration
    - Recommend position adjustments
    - Track quality trends
    """

    def __init__(self):
        super().__init__(
            name="QualityMonitorAgent",
            role="Portfolio quality monitoring and deterioration detection",
        )
        self.safety_analyzer = get_global_safety_analyzer()
        self.quality_history: dict[str, list[dict[str, Any]]] = {}

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Monitor portfolio quality and detect issues.

        Args:
            data: Contains portfolio positions (list of {symbol, quantity, price})

        Returns:
            Quality monitoring report with alerts and recommendations
        """
        positions = data.get("positions", [])
        data.get("portfolio_value", 0.0)

        if not positions:
            return {
                "action": "NO_ACTION",
                "message": "No positions to monitor",
                "alerts": [],
                "recommendations": [],
            }

        alerts = []
        recommendations = []
        quality_scores = {}

        # Analyze each position
        for position in positions:
            symbol = position.get("symbol", "")
            quantity = position.get("quantity", 0.0)
            current_price = position.get("current_price", 0.0)

            if not symbol or quantity <= 0:
                continue

            try:
                # Get current quality analysis
                safety_analysis = self.safety_analyzer.analyze_safety(
                    symbol=symbol,
                    market_price=current_price,
                    force_refresh=False,
                )

                quality = safety_analysis.quality
                if quality:
                    quality_scores[symbol] = quality.quality_score

                    # Check for quality deterioration
                    deterioration = self._check_quality_deterioration(symbol, quality)
                    if deterioration:
                        alerts.append(deterioration)
                        recommendations.append(self._generate_recommendation(symbol, deterioration))

                    # Store quality history
                    self._store_quality_history(symbol, quality)

            except Exception as e:
                logger.warning(f"Error monitoring quality for {symbol}: {e}")
                continue

        # Build comprehensive monitoring report
        memory_context = self.get_memory_context(limit=5)

        prompt = self._build_monitoring_prompt(positions, quality_scores, alerts, memory_context)

        llm_response = self.reason_with_llm(prompt)

        # Combine analysis
        analysis = self._combine_monitoring_analysis(
            quality_scores, alerts, recommendations, llm_response
        )

        # Log decision
        self.log_decision(analysis)

        return analysis

    def _check_quality_deterioration(
        self, symbol: str, current_quality: CompanyQuality
    ) -> dict[str, Any] | None:
        """Check if quality has deteriorated compared to history."""

        if symbol not in self.quality_history:
            return None

        history = self.quality_history[symbol]
        if len(history) < 2:
            return None

        # Get previous quality score
        previous_score = history[-1].get("quality_score", current_quality.quality_score)
        current_score = current_quality.quality_score

        # Check for significant deterioration (>10 points)
        if current_score < previous_score - 10:
            return {
                "symbol": symbol,
                "severity": "HIGH" if current_score < 40 else "MEDIUM",
                "previous_score": previous_score,
                "current_score": current_score,
                "deterioration": previous_score - current_score,
                "message": (
                    f"{symbol} quality deteriorated from {previous_score:.1f} "
                    f"to {current_score:.1f} (drop of {previous_score - current_score:.1f} points)"
                ),
            }

        # Check if quality is now below threshold
        if current_score < 40 and previous_score >= 40:
            return {
                "symbol": symbol,
                "severity": "HIGH",
                "previous_score": previous_score,
                "current_score": current_score,
                "deterioration": previous_score - current_score,
                "message": (f"{symbol} quality dropped below threshold ({current_score:.1f} < 40)"),
            }

        return None

    def _store_quality_history(self, symbol: str, quality: CompanyQuality) -> None:
        """Store quality metrics in history."""
        if symbol not in self.quality_history:
            self.quality_history[symbol] = []

        entry = {
            "timestamp": quality.timestamp.isoformat(),
            "quality_score": quality.quality_score,
            "debt_to_equity": quality.debt_to_equity,
            "current_ratio": quality.current_ratio,
            "roe": quality.roe,
            "roa": quality.roa,
            "profit_margin": quality.profit_margin,
            "earnings_growth_3y": quality.earnings_growth_3y,
            "earnings_consistency": quality.earnings_consistency,
        }

        self.quality_history[symbol].append(entry)

        # Keep only last 30 entries per symbol
        if len(self.quality_history[symbol]) > 30:
            self.quality_history[symbol] = self.quality_history[symbol][-30:]

    def _generate_recommendation(
        self, symbol: str, deterioration: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate recommendation based on quality deterioration."""

        severity = deterioration["severity"]
        current_score = deterioration["current_score"]

        if severity == "HIGH" and current_score < 40:
            return {
                "symbol": symbol,
                "action": "CONSIDER_REDUCE",
                "reason": f"Quality score {current_score:.1f} below threshold (40)",
                "priority": "HIGH",
            }
        elif severity == "MEDIUM":
            return {
                "symbol": symbol,
                "action": "MONITOR_CLOSELY",
                "reason": f"Quality deteriorating (current: {current_score:.1f})",
                "priority": "MEDIUM",
            }
        else:
            return {
                "symbol": symbol,
                "action": "CONTINUE_HOLDING",
                "reason": "Quality acceptable but declining",
                "priority": "LOW",
            }

    def _build_monitoring_prompt(
        self,
        positions: list[dict],
        quality_scores: dict[str, float],
        alerts: list[dict],
        memory_context: str,
    ) -> str:
        """Build LLM prompt for quality monitoring."""

        positions_summary = ""
        for pos in positions:
            symbol = pos.get("symbol", "")
            qty = pos.get("quantity", 0.0)
            price = pos.get("current_price", 0.0)
            value = qty * price
            quality = quality_scores.get(symbol, 0.0)

            positions_summary += (
                f"- {symbol}: {qty:.2f} shares @ ${price:.2f} = ${value:,.2f} "
                f"(Quality: {quality:.1f}/100)\n"
            )

        alerts_summary = ""
        if alerts:
            for alert in alerts:
                alerts_summary += f"- {alert['message']} (Severity: {alert['severity']})\n"
        else:
            alerts_summary = "No quality alerts"

        prompt = f"""You are a Quality Monitor Agent reviewing portfolio quality.

PORTFOLIO POSITIONS:
{positions_summary}

QUALITY ALERTS:
{alerts_summary}

{memory_context}

TASK: Provide quality monitoring assessment:
1. Overall Portfolio Quality (1-10, where 10 is highest quality)
2. Quality Trend (IMPROVING / STABLE / DECLINING)
3. Risk Assessment (LOW / MEDIUM / HIGH)
4. Recommendations (what actions to take)
5. Priority Actions (most important actions first)

Format your response as:
PORTFOLIO_QUALITY: [1-10]
QUALITY_TREND: [IMPROVING/STABLE/DECLINING]
RISK_LEVEL: [LOW/MEDIUM/HIGH]
RECOMMENDATIONS: [your recommendations]
PRIORITY_ACTIONS: [priority actions]"""

        return prompt

    def _combine_monitoring_analysis(
        self,
        quality_scores: dict[str, float],
        alerts: list[dict],
        recommendations: list[dict],
        llm_response: dict[str, Any],
    ) -> dict[str, Any]:
        """Combine monitoring data with LLM insights."""

        llm_analysis = self._parse_llm_response(llm_response.get("reasoning", ""))

        # Calculate average quality score
        avg_quality = sum(quality_scores.values()) / len(quality_scores) if quality_scores else 0.0

        analysis = {
            "action": "MONITOR" if not alerts else "ALERT",
            "portfolio_quality": avg_quality,
            "quality_scores": quality_scores,
            "alerts": alerts,
            "recommendations": recommendations,
            "quality_trend": llm_analysis.get("quality_trend", "STABLE"),
            "risk_level": llm_analysis.get("risk_level", "MEDIUM"),
            "llm_recommendations": llm_analysis.get("recommendations", ""),
            "priority_actions": llm_analysis.get("priority_actions", ""),
            "full_reasoning": llm_response.get("reasoning", ""),
            "timestamp": datetime.now().isoformat(),
        }

        return analysis

    def _parse_llm_response(self, reasoning: str) -> dict[str, Any]:
        """Parse LLM response."""
        lines = reasoning.split("\n")
        analysis = {
            "portfolio_quality": 5,
            "quality_trend": "STABLE",
            "risk_level": "MEDIUM",
            "recommendations": "",
            "priority_actions": "",
        }

        for line in lines:
            line = line.strip()
            if line.startswith("PORTFOLIO_QUALITY:"):
                with contextlib.suppress(builtins.BaseException):
                    analysis["portfolio_quality"] = int(line.split(":")[1].strip())
            elif line.startswith("QUALITY_TREND:"):
                trend = line.split(":")[1].strip().upper()
                if trend in ["IMPROVING", "STABLE", "DECLINING"]:
                    analysis["quality_trend"] = trend
            elif line.startswith("RISK_LEVEL:"):
                risk = line.split(":")[1].strip().upper()
                if risk in ["LOW", "MEDIUM", "HIGH"]:
                    analysis["risk_level"] = risk
            elif line.startswith("RECOMMENDATIONS:"):
                analysis["recommendations"] = line.split(":", 1)[1].strip()
            elif line.startswith("PRIORITY_ACTIONS:"):
                analysis["priority_actions"] = line.split(":", 1)[1].strip()

        return analysis
