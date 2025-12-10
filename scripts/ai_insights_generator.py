#!/usr/bin/env python3
"""
AI Insights Generator for World-Class Dashboard

Generates AI-powered insights and commentary:
- Daily trading behavior summary
- Trade critiques
- Anomaly detection
- Regime shift detection
- Improvement recommendations
- Strategy health scoring
"""

import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.dashboard_metrics import load_json_file

DATA_DIR = Path("data")


class AIInsightsGenerator:
    """Generate AI-powered insights for the dashboard."""

    def __init__(self):
        self.data_dir = DATA_DIR

    def generate_daily_insights(
        self,
        perf_log: list[dict],
        all_trades: list[dict],
        risk_metrics: dict[str, Any],
        performance_metrics: dict[str, Any],
        attribution: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate comprehensive daily insights."""
        insights = {
            "summary": self._generate_summary(perf_log, all_trades),
            "trade_analysis": self._analyze_trades(all_trades),
            "anomalies": self._detect_anomalies(perf_log, all_trades),
            "regime_shift": self._detect_regime_shift(perf_log),
            "recommendations": self._generate_recommendations(
                risk_metrics, performance_metrics, attribution
            ),
            "strategy_health": self._score_strategy_health(risk_metrics, performance_metrics),
        }

        return insights

    def _generate_summary(self, perf_log: list[dict], all_trades: list[dict]) -> str:
        """Generate daily summary."""
        if not perf_log:
            return "No trading activity to summarize."

        latest = perf_log[-1]
        latest.get("equity", 100000)
        pl = latest.get("pl", 0)
        pl_pct = latest.get("pl_pct", 0) * 100

        # Count today's trades
        today = date.today().isoformat()
        today_trades = [t for t in all_trades if t.get("trade_date", "").startswith(today)]

        summary_parts = []

        if pl > 0:
            summary_parts.append(f"📈 Portfolio gained ${pl:.2f} ({pl_pct:+.2f}%) today.")
        elif pl < 0:
            summary_parts.append(f"📉 Portfolio declined ${abs(pl):.2f} ({pl_pct:+.2f}%) today.")
        else:
            summary_parts.append("➡️ Portfolio remained flat today.")

        if today_trades:
            summary_parts.append(f"Executed {len(today_trades)} trade(s) today.")

        # Performance trend
        if len(perf_log) >= 3:
            recent_pl = [e.get("pl", 0) for e in perf_log[-3:]]
            if all(p > 0 for p in recent_pl):
                summary_parts.append("✅ Three consecutive positive days - strong momentum.")
            elif all(p < 0 for p in recent_pl):
                summary_parts.append("⚠️ Three consecutive negative days - review strategy.")

        return " ".join(summary_parts) if summary_parts else "No significant activity."

    def _analyze_trades(self, all_trades: list[dict]) -> list[str]:
        """Analyze recent trades and provide critiques."""
        if not all_trades:
            return ["No trades to analyze."]

        critiques = []

        # Analyze trade distribution
        symbol_counts = defaultdict(int)
        for trade in all_trades[-10:]:  # Last 10 trades
            symbol = trade.get("symbol", "")
            symbol_counts[symbol] += 1

        # Check for over-concentration
        if symbol_counts:
            max_symbol = max(symbol_counts.items(), key=lambda x: x[1])
            if max_symbol[1] > len(all_trades[-10:]) * 0.5:
                critiques.append(
                    f"⚠️ Over-concentration detected: {max_symbol[0]} represents "
                    f"{max_symbol[1] / len(all_trades[-10:]) * 100:.0f}% of recent trades. "
                    "Consider diversification."
                )

        # Analyze trade timing
        morning_trades = sum(1 for t in all_trades[-10:] if self._is_morning_trade(t))
        if morning_trades > len(all_trades[-10:]) * 0.7:
            critiques.append(
                "✅ Good trade timing: Most trades executed during morning hours "
                "(typically higher liquidity)."
            )

        return critiques if critiques else ["✅ Trade execution appears balanced."]

    def _is_morning_trade(self, trade: dict) -> bool:
        """Check if trade was executed in morning hours."""
        timestamp = trade.get("timestamp", "")
        if not timestamp:
            return False

        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return 9 <= dt.hour < 12
        except Exception:
            return False

    def _detect_anomalies(self, perf_log: list[dict], all_trades: list[dict]) -> list[str]:
        """Detect anomalies in trading activity."""
        anomalies = []

        if not perf_log or len(perf_log) < 3:
            return anomalies

        # Check for unusual P/L
        recent_pl = [e.get("pl", 0) for e in perf_log[-5:]]
        if recent_pl:
            mean_pl = np.mean(recent_pl)
            std_pl = np.std(recent_pl) if len(recent_pl) > 1 else 0

            if std_pl > 0:
                latest_pl = recent_pl[-1]
                z_score = abs((latest_pl - mean_pl) / std_pl) if std_pl > 0 else 0

                if z_score > 2:
                    anomalies.append(
                        f"🚨 Anomaly detected: Today's P/L ({latest_pl:+.2f}) is "
                        f"{z_score:.1f} standard deviations from recent average. "
                        "Review for unusual market conditions or execution issues."
                    )

        # Check for missing trades
        today = date.today().isoformat()
        today_trades = [t for t in all_trades if t.get("trade_date", "").startswith(today)]

        # If we typically trade but didn't today
        if len(all_trades) > 5 and len(today_trades) == 0:
            anomalies.append(
                "⚠️ No trades executed today despite historical trading activity. "
                "Check for system issues or market conditions."
            )

        return anomalies

    def _detect_regime_shift(self, perf_log: list[dict]) -> str | None:
        """Detect market regime shifts."""
        if not perf_log or len(perf_log) < 10:
            return None

        # Compare recent vs older performance
        recent_equity = [e.get("equity", 100000) for e in perf_log[-5:]]
        older_equity = [e.get("equity", 100000) for e in perf_log[-10:-5]]

        if len(recent_equity) < 2 or len(older_equity) < 2:
            return None

        # Calculate returns
        recent_returns = [
            (recent_equity[i] - recent_equity[i - 1]) / recent_equity[i - 1]
            for i in range(1, len(recent_equity))
        ]
        older_returns = [
            (older_equity[i] - older_equity[i - 1]) / older_equity[i - 1]
            for i in range(1, len(older_equity))
        ]

        if recent_returns and older_returns:
            recent_mean = np.mean(recent_returns)
            older_mean = np.mean(older_returns)

            # Detect shift
            if recent_mean > older_mean * 1.5:
                return (
                    "📈 Regime shift detected: Recent performance significantly improved. "
                    "Market may be entering a more favorable regime."
                )
            elif recent_mean < older_mean * 0.5:
                return (
                    "📉 Regime shift detected: Recent performance declined. "
                    "Market conditions may have changed - review strategy."
                )

        return None

    def _generate_recommendations(
        self,
        risk_metrics: dict[str, Any],
        performance_metrics: dict[str, Any],
        attribution: dict[str, Any],
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Risk-based recommendations
        sharpe = risk_metrics.get("sharpe_ratio", 0)
        if sharpe < 0:
            recommendations.append(
                "🔴 CRITICAL: Sharpe ratio is negative. Consider pausing trading "
                "until risk-adjusted returns improve."
            )
        elif sharpe < 0.5:
            recommendations.append(
                "⚠️ Sharpe ratio below target (0.5). Focus on improving risk-adjusted returns "
                "through better entry/exit timing or position sizing."
            )

        max_dd = risk_metrics.get("max_drawdown_pct", 0)
        if max_dd > 5:
            recommendations.append(
                f"⚠️ Max drawdown ({max_dd:.2f}%) exceeds 5% threshold. "
                "Review risk management and consider reducing position sizes."
            )

        # Performance-based recommendations
        win_rate = performance_metrics.get("win_rate", 0)
        if win_rate < 50:
            recommendations.append(
                f"📊 Win rate ({win_rate:.1f}%) below 50%. Consider: "
                "1) Improving entry signals, 2) Better exit timing, "
                "3) Reviewing strategy logic."
            )

        # Attribution-based recommendations
        by_symbol = attribution.get("by_symbol", {})
        if by_symbol:
            best_symbol = max(by_symbol.items(), key=lambda x: x[1].get("total_pl", 0))
            worst_symbol = min(by_symbol.items(), key=lambda x: x[1].get("total_pl", 0))

            if best_symbol[1].get("total_pl", 0) > 0 and worst_symbol[1].get("total_pl", 0) < 0:
                recommendations.append(
                    f"💡 Consider increasing allocation to {best_symbol[0]} "
                    f"(best performer) and reducing {worst_symbol[0]} exposure."
                )

        return (
            recommendations
            if recommendations
            else ["✅ No critical recommendations. System performing within acceptable parameters."]
        )

    def _score_strategy_health(
        self, risk_metrics: dict[str, Any], performance_metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """Score overall strategy health."""
        score = 100.0
        factors = []

        # Sharpe ratio component (30 points)
        sharpe = risk_metrics.get("sharpe_ratio", 0)
        if sharpe >= 1.0:
            sharpe_score = 30
        elif sharpe >= 0.5:
            sharpe_score = 20
        elif sharpe >= 0:
            sharpe_score = 10
        else:
            sharpe_score = 0

        score -= 30 - sharpe_score
        factors.append(f"Sharpe Ratio: {sharpe:.2f} ({sharpe_score}/30)")

        # Win rate component (25 points)
        win_rate = performance_metrics.get("win_rate", 0)
        if win_rate >= 60:
            win_rate_score = 25
        elif win_rate >= 50:
            win_rate_score = 20
        elif win_rate >= 40:
            win_rate_score = 10
        else:
            win_rate_score = 0

        score -= 25 - win_rate_score
        factors.append(f"Win Rate: {win_rate:.1f}% ({win_rate_score}/25)")

        # Drawdown component (25 points)
        max_dd = risk_metrics.get("max_drawdown_pct", 0)
        if max_dd <= 2:
            dd_score = 25
        elif max_dd <= 5:
            dd_score = 20
        elif max_dd <= 10:
            dd_score = 10
        else:
            dd_score = 0

        score -= 25 - dd_score
        factors.append(f"Max Drawdown: {max_dd:.2f}% ({dd_score}/25)")

        # Profit factor component (20 points)
        profit_factor = performance_metrics.get("profit_factor", 0)
        if profit_factor >= 2.0:
            pf_score = 20
        elif profit_factor >= 1.5:
            pf_score = 15
        elif profit_factor >= 1.0:
            pf_score = 10
        else:
            pf_score = 0

        score -= 20 - pf_score
        factors.append(f"Profit Factor: {profit_factor:.2f} ({pf_score}/20)")

        # Ensure score is between 0 and 100
        score = max(0, min(100, score))

        # Determine health status
        if score >= 80:
            status = "EXCELLENT"
            emoji = "🟢"
        elif score >= 60:
            status = "GOOD"
            emoji = "🟡"
        elif score >= 40:
            status = "FAIR"
            emoji = "🟠"
        else:
            status = "POOR"
            emoji = "🔴"

        return {
            "score": score,
            "status": status,
            "emoji": emoji,
            "factors": factors,
        }


if __name__ == "__main__":
    generator = AIInsightsGenerator()

    perf_log = load_json_file(DATA_DIR / "performance_log.json")
    if not isinstance(perf_log, list):
        perf_log = []

    # Load sample metrics
    from scripts.dashboard_metrics import TradingMetricsCalculator

    calculator = TradingMetricsCalculator()
    metrics = calculator.calculate_all_metrics()

    insights = generator.generate_daily_insights(
        perf_log,
        calculator._load_all_trades(),
        metrics.get("risk_metrics", {}),
        metrics.get("performance_metrics", {}),
        metrics.get("performance_attribution", {}),
    )

    print(json.dumps(insights, indent=2, default=str))
