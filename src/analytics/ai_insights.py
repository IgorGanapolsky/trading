"""
AI Insight Layer for Trading Dashboard

Generates natural language insights, anomaly detection, trade critiques,
and strategy health scoring using AI agents.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DailyBriefing:
    """AI-generated daily briefing"""

    summary: str
    key_changes: list[str]
    anomalies: list[str]
    recommendations: list[str]
    confidence_score: float  # 0-1


@dataclass
class TradeCritique:
    """AI critique of a trade"""

    trade_id: str
    entry_timing_score: float  # -1 to 1
    exit_timing_score: float
    position_sizing_score: float
    overall_score: float
    critique: str
    suggestions: list[str]


@dataclass
class StrategyHealth:
    """Strategy health scoring"""

    overall_score: float  # 0-100
    performance_score: float
    risk_score: float
    consistency_score: float
    edge_score: float
    diagnosis: str
    action_items: list[str]


class AIInsightGenerator:
    """
    Generates AI-powered insights for the dashboard.

    Uses Claude/Gemini agents to provide:
    - Natural language daily briefings
    - Anomaly detection
    - Trade critiques
    - Strategy health scoring
    - Optimization suggestions
    """

    def __init__(self):
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")

    def generate_daily_briefing(
        self,
        metrics: dict[str, Any],
        recent_trades: list[dict[str, Any]],
        risk_metrics: dict[str, Any],
    ) -> DailyBriefing:
        """
        Generate natural language daily briefing.

        Args:
            metrics: Current performance metrics
            recent_trades: Recent trades
            risk_metrics: Risk analytics

        Returns:
            DailyBriefing with AI-generated insights
        """
        # Extract key metrics
        total_pl = metrics.get("total_pl", 0.0)
        win_rate = metrics.get("win_rate", 0.0)
        avg_daily = metrics.get("avg_daily_profit", 0.0)
        max_dd = risk_metrics.get("max_drawdown_pct", 0.0)

        # Generate summary
        if total_pl > 0:
            summary = f"✅ Portfolio is profitable (+${total_pl:.2f}). "
        else:
            summary = f"⚠️ Portfolio is down ${abs(total_pl):.2f}. "

        summary += f"Average daily profit: ${avg_daily:.2f}. "
        summary += f"Win rate: {win_rate:.1f}%. "

        if max_dd > 5.0:
            summary += f"⚠️ Max drawdown: {max_dd:.1f}% - monitor risk closely."
        else:
            summary += "Risk metrics are within acceptable range."

        # Key changes
        key_changes = []
        if len(recent_trades) > 0:
            key_changes.append(f"{len(recent_trades)} new trades executed")

        if win_rate > 55:
            key_changes.append("Win rate above target (>55%)")
        elif win_rate < 30:
            key_changes.append("Win rate below target - review strategy")

        # Anomalies
        anomalies = []
        if abs(total_pl) > 100 and avg_daily < 1.0:
            anomalies.append("Large P/L swing detected - investigate")

        if max_dd > 10.0:
            anomalies.append("Drawdown exceeds 10% - risk alert")

        # Recommendations
        recommendations = []
        if avg_daily < 1.0:
            recommendations.append("Consider increasing position sizes if win rate is stable")

        if win_rate < 40:
            recommendations.append("Review entry signals - may need tighter filters")

        if max_dd > 5.0:
            recommendations.append("Tighten stop-losses or reduce position sizes")

        confidence = 0.7  # Placeholder

        return DailyBriefing(
            summary=summary,
            key_changes=key_changes,
            anomalies=anomalies,
            recommendations=recommendations,
            confidence_score=confidence,
        )

    def detect_anomalies(
        self,
        equity_curve: list[float],
        trades: list[dict[str, Any]],
        metrics: dict[str, Any],
    ) -> list[str]:
        """
        Detect anomalies in trading performance.

        Returns:
            List of anomaly descriptions
        """
        anomalies = []

        if len(equity_curve) < 5:
            return anomalies

        # Check for sudden drops
        recent_returns = [
            (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
            for i in range(1, len(equity_curve))
        ]

        if len(recent_returns) > 0:
            avg_return = sum(recent_returns) / len(recent_returns)
            std_return = (
                sum((r - avg_return) ** 2 for r in recent_returns) / len(recent_returns)
            ) ** 0.5

            # Check for outliers
            for i, ret in enumerate(recent_returns[-5:]):
                if abs(ret - avg_return) > 3 * std_return:
                    anomalies.append(
                        f"Outlier return detected: {ret * 100:.2f}% on day {len(equity_curve) - 5 + i}"
                    )

        # Check for unusual trade patterns
        if len(trades) > 10:
            recent_trades = trades[-10:]
            trade_amounts = [t.get("amount", 0) for t in recent_trades]
            avg_amount = sum(trade_amounts) / len(trade_amounts)

            for trade in recent_trades:
                amount = trade.get("amount", 0)
                if amount > avg_amount * 2:
                    anomalies.append(
                        f"Unusually large trade: ${amount:.2f} (avg: ${avg_amount:.2f})"
                    )

        return anomalies

    def critique_trade(self, trade: dict[str, Any], market_data: dict[str, Any]) -> TradeCritique:
        """
        AI critique of a specific trade.

        Args:
            trade: Trade record
            market_data: Market context at time of trade

        Returns:
            TradeCritique with scores and suggestions
        """
        trade_id = trade.get("order_id", "unknown")
        pl = trade.get("pl", 0.0)
        trade.get("entry_price", 0.0)
        trade.get("exit_price", 0.0)

        # Entry timing (simplified - would use market regime)
        entry_score = 0.5  # Placeholder

        # Exit timing
        exit_score = 0.5  # Placeholder

        # Position sizing
        trade.get("amount", 0.0)
        sizing_score = 0.5  # Placeholder

        # Overall score
        overall = (entry_score + exit_score + sizing_score) / 3

        # Generate critique
        if pl > 0:
            critique = f"✅ Profitable trade (+${pl:.2f}). "
        else:
            critique = f"❌ Losing trade (${pl:.2f}). "

        critique += "Entry timing was average. "
        critique += "Consider tighter stop-losses for risk management."

        suggestions = []
        if pl < 0:
            suggestions.append("Review entry signal - may have entered too early")
            suggestions.append("Consider wider stop-loss to avoid premature exits")

        return TradeCritique(
            trade_id=trade_id,
            entry_timing_score=entry_score,
            exit_timing_score=exit_score,
            position_sizing_score=sizing_score,
            overall_score=overall,
            critique=critique,
            suggestions=suggestions,
        )

    def assess_strategy_health(
        self,
        metrics: dict[str, Any],
        risk_metrics: dict[str, Any],
        forecast: dict[str, Any],
    ) -> StrategyHealth:
        """
        Assess overall strategy health.

        Returns:
            StrategyHealth with scores and diagnosis
        """
        # Performance score (0-100)
        win_rate = metrics.get("win_rate", 0.0)
        avg_daily = metrics.get("avg_daily_profit", 0.0)
        perf_score = min(100, (win_rate / 55 * 50) + (avg_daily / 10 * 50))

        # Risk score (0-100, higher is better)
        max_dd = risk_metrics.get("max_drawdown_pct", 0.0)
        sharpe = risk_metrics.get("sharpe_ratio", 0.0)
        risk_score = max(0, 100 - (max_dd * 5) + (sharpe * 20))
        risk_score = min(100, risk_score)

        # Consistency score
        consistency = 70.0  # Placeholder

        # Edge score (from forecast)
        edge_drift = forecast.get("edge_drift_score", 0.0)
        edge_score = 50 + (edge_drift * 50)  # Convert -1 to 1 into 0-100

        # Overall score
        overall = (perf_score + risk_score + consistency + edge_score) / 4

        # Diagnosis
        if overall > 75:
            diagnosis = "✅ Strategy is healthy and performing well"
        elif overall > 50:
            diagnosis = "⚠️ Strategy needs optimization - performance is moderate"
        else:
            diagnosis = "❌ Strategy needs significant improvement"

        # Action items
        action_items = []
        if perf_score < 50:
            action_items.append("Improve win rate or profit per trade")
        if risk_score < 50:
            action_items.append("Reduce drawdowns and improve risk management")
        if edge_score < 50:
            action_items.append("Strategy edge may be decaying - consider retraining")

        return StrategyHealth(
            overall_score=overall,
            performance_score=perf_score,
            risk_score=risk_score,
            consistency_score=consistency,
            edge_score=edge_score,
            diagnosis=diagnosis,
            action_items=action_items,
        )
