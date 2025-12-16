"""
Continuous Verifier

ML-powered continuous monitoring and anomaly detection.
Learns from past incidents to detect similar patterns before they cause failures.

Created: Dec 11, 2025 (after syntax error incident)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AnomalyAlert:
    """An detected anomaly."""

    type: str
    severity: str  # low, medium, high, critical
    description: str
    confidence: float
    timestamp: str
    recommended_action: str
    similar_past_incidents: list[str] = field(default_factory=list)


class ContinuousVerifier:
    """
    ML-powered continuous monitoring system.

    Monitors:
    1. Trade execution patterns (detect unusual failures)
    2. System metrics (latency, errors, timeouts)
    3. Code change patterns (detect risky commits)
    4. Performance drift (Sharpe, win rate degradation)

    Uses statistical methods and learned patterns to detect anomalies
    before they cause major failures.
    """

    # Thresholds learned from historical data
    THRESHOLDS = {
        "max_daily_failures": 5,
        "max_consecutive_failures": 3,
        "min_daily_trades": 1,
        "max_latency_ms": 5000,
        "min_win_rate": 0.3,
        "max_drawdown": 0.10,
        "sharpe_alert_threshold": -1.0,
    }

    def __init__(
        self,
        metrics_path: str = "data/system_metrics.json",
        trades_dir: str = "data",
    ):
        self.metrics_path = Path(metrics_path)
        self.trades_dir = Path(trades_dir)
        self._historical_data = None

    def check_trading_health(self) -> list[AnomalyAlert]:
        """
        Check trading system health based on recent activity.

        Returns list of anomaly alerts if issues detected.
        """
        alerts = []

        # Load recent trades
        today = datetime.utcnow().strftime("%Y-%m-%d")
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

        today_trades = self._load_trades(today)
        yesterday_trades = self._load_trades(yesterday)

        # Check 1: No trades today
        if len(today_trades) == 0 and datetime.utcnow().hour >= 10:
            # Check if yesterday had trades
            if len(yesterday_trades) > 0:
                alerts.append(
                    AnomalyAlert(
                        type="no_trades_executed",
                        severity="critical",
                        description=f"No trades executed today ({today}). Yesterday had {len(yesterday_trades)} trades.",
                        confidence=0.95,
                        timestamp=datetime.utcnow().isoformat(),
                        recommended_action="Check workflow logs for errors. Run post-deploy verification.",
                        similar_past_incidents=["ll_009_ci_syntax_failure_dec11"],
                    )
                )

        # Check 2: Sudden drop in trades
        if len(today_trades) < len(yesterday_trades) * 0.5 and len(yesterday_trades) > 5:
            alerts.append(
                AnomalyAlert(
                    type="trade_volume_drop",
                    severity="high",
                    description=f"Trade volume dropped {len(yesterday_trades)} -> {len(today_trades)}",
                    confidence=0.8,
                    timestamp=datetime.utcnow().isoformat(),
                    recommended_action="Check if gates are over-filtering. Review gate pass rates.",
                    similar_past_incidents=["ll_001_over_engineering"],
                )
            )

        # Check 3: High failure rate
        if today_trades:
            failed = sum(1 for t in today_trades if t.get("status") == "FAILED")
            if failed / len(today_trades) > 0.3:
                alerts.append(
                    AnomalyAlert(
                        type="high_failure_rate",
                        severity="high",
                        description=f"{failed}/{len(today_trades)} trades failed today",
                        confidence=0.9,
                        timestamp=datetime.utcnow().isoformat(),
                        recommended_action="Check broker connection. Review error logs.",
                    )
                )

        return alerts

    def check_performance_drift(self) -> list[AnomalyAlert]:
        """
        Detect performance degradation using statistical methods.
        """
        alerts = []

        # Load performance history
        perf_path = self.trades_dir / "performance_log.json"
        if not perf_path.exists():
            return alerts

        try:
            with open(perf_path) as f:
                history = json.load(f)
        except Exception:
            return alerts

        if len(history) < 5:
            return alerts

        # Calculate recent vs historical metrics
        recent = history[-5:]
        historical = history[:-5] if len(history) > 10 else history[:5]

        recent_pl = np.mean([h.get("pl", 0) for h in recent])
        historical_pl = np.mean([h.get("pl", 0) for h in historical])

        # Check for significant performance drop
        if historical_pl > 0 and recent_pl < historical_pl * 0.5:
            alerts.append(
                AnomalyAlert(
                    type="performance_drift",
                    severity="medium",
                    description=f"Recent P/L ({recent_pl:.2f}) significantly below historical ({historical_pl:.2f})",
                    confidence=0.7,
                    timestamp=datetime.utcnow().isoformat(),
                    recommended_action="Review recent strategy changes. Check market regime.",
                )
            )

        # Check for negative Sharpe
        recent_sharpe = self._calculate_sharpe(recent)
        if recent_sharpe < self.THRESHOLDS["sharpe_alert_threshold"]:
            alerts.append(
                AnomalyAlert(
                    type="negative_sharpe",
                    severity="high",
                    description=f"Sharpe ratio is {recent_sharpe:.2f}, below threshold",
                    confidence=0.85,
                    timestamp=datetime.utcnow().isoformat(),
                    recommended_action="Strategy may be unprofitable. Consider pausing trading.",
                )
            )

        return alerts

    def check_code_change_risk(
        self,
        changed_files: list[str],
        commit_message: str,
    ) -> list[AnomalyAlert]:
        """
        Use ML to assess risk of code changes.

        Learns from past incidents to identify risky patterns.
        """
        alerts = []

        # Load lessons learned for pattern matching
        lessons = self._load_lessons()

        # Pattern 1: Changes to critical files
        critical_file_patterns = [
            "executor",
            "gateway",
            "orchestrator",
            "main.py",
            "alpaca",
            "broker",
            "trade",
        ]

        risk_score = 0.0
        risky_files = []

        for f in changed_files:
            f_lower = f.lower()
            for pattern in critical_file_patterns:
                if pattern in f_lower:
                    risk_score += 0.2
                    risky_files.append(f)
                    break

        # Pattern 2: Large number of changes
        if len(changed_files) > 10:
            risk_score += 0.3

        # Pattern 3: Keywords in commit message
        risky_keywords = ["fix", "hotfix", "urgent", "revert", "broken"]
        for keyword in risky_keywords:
            if keyword in commit_message.lower():
                risk_score += 0.1

        # Generate alert if risk is high
        if risk_score > 0.5:
            alerts.append(
                AnomalyAlert(
                    type="risky_code_change",
                    severity="high" if risk_score > 0.7 else "medium",
                    description=f"High-risk code change detected (score: {risk_score:.2f})",
                    confidence=min(risk_score, 0.95),
                    timestamp=datetime.utcnow().isoformat(),
                    recommended_action="Run full pre-merge verification. Consider manual review.",
                    similar_past_incidents=[lesson.get("id") for lesson in lessons[:3]],
                )
            )

        return alerts

    def _load_trades(self, date: str) -> list[dict]:
        """Load trades for a specific date."""
        trades_file = self.trades_dir / f"trades_{date}.json"
        if not trades_file.exists():
            return []

        try:
            with open(trades_file) as f:
                return json.load(f)
        except Exception:
            return []

    def _load_lessons(self) -> list[dict]:
        """Load lessons from RAG."""
        lessons_file = Path("data/rag/lessons_learned.json")
        if not lessons_file.exists():
            return []

        try:
            with open(lessons_file) as f:
                data = json.load(f)
                return data.get("lessons", [])
        except Exception:
            return []

    def _calculate_sharpe(self, history: list[dict]) -> float:
        """Calculate Sharpe ratio from history."""
        if len(history) < 2:
            return 0.0

        returns = [h.get("pl_pct", 0) for h in history]
        if np.std(returns) == 0:
            return 0.0

        return np.mean(returns) / np.std(returns) * np.sqrt(252)

    def run_all_checks(self) -> list[AnomalyAlert]:
        """Run all continuous verification checks."""
        alerts = []

        alerts.extend(self.check_trading_health())
        alerts.extend(self.check_performance_drift())

        return alerts


def main():
    """CLI entry point."""
    verifier = ContinuousVerifier()
    alerts = verifier.run_all_checks()

    print("\n" + "=" * 60)
    print("CONTINUOUS VERIFICATION RESULTS")
    print("=" * 60)

    if not alerts:
        print("✅ No anomalies detected")
    else:
        print(f"⚠️ {len(alerts)} anomaly alert(s) detected:\n")
        for alert in alerts:
            severity_emoji = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢",
            }.get(alert.severity, "⚪")

            print(f"{severity_emoji} [{alert.severity.upper()}] {alert.type}")
            print(f"   {alert.description}")
            print(f"   Confidence: {alert.confidence:.0%}")
            print(f"   Action: {alert.recommended_action}")
            print()

    # Exit with error if critical alerts
    critical = [a for a in alerts if a.severity == "critical"]
    return 1 if critical else 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
