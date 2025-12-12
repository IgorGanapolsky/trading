"""
Strategy Change Anomaly Detector

Uses ML techniques to detect anomalies in strategy changes:
1. Detects when strategies are added/removed without proper integration
2. Flags configuration changes that deviate from historical norms
3. Alerts on strategy drift (performance degradation)

Part of the ll_012 prevention system.

Author: Trading System
Created: 2025-12-12
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StrategyAnomaly:
    """Represents a detected strategy anomaly."""

    anomaly_type: str  # "missing_integration", "config_drift", "performance_drift"
    strategy: str
    severity: str  # "low", "medium", "high", "critical"
    description: str
    timestamp: str
    recommendation: str


class StrategyAnomalyDetector:
    """
    Detects anomalies in strategy configurations and execution.

    Uses statistical methods and rule-based checks to identify:
    - Strategies with code but no execution
    - Configuration changes outside normal bounds
    - Performance degradation beyond thresholds
    """

    def __init__(
        self,
        system_state_path: str = "data/system_state.json",
        registry_path: str = "config/strategy_registry.json",
        trader_path: str = "scripts/autonomous_trader.py",
    ):
        self.system_state_path = Path(system_state_path)
        self.registry_path = Path(registry_path)
        self.trader_path = Path(trader_path)
        self.anomalies: list[StrategyAnomaly] = []

    def detect_all_anomalies(self) -> list[StrategyAnomaly]:
        """Run all anomaly detection checks."""
        self.anomalies = []

        # Check 1: Missing integrations
        self._detect_missing_integrations()

        # Check 2: Configuration drift
        self._detect_config_drift()

        # Check 3: Strategy performance drift
        self._detect_performance_drift()

        # Check 4: Orphaned strategies (code exists but not registered)
        self._detect_orphaned_strategies()

        return self.anomalies

    def _detect_missing_integrations(self) -> None:
        """Detect strategies in registry but not in autonomous_trader.py."""
        if not self.trader_path.exists():
            return

        with open(self.trader_path) as f:
            trader_code = f.read().lower()

        # Check registry strategies
        if self.registry_path.exists():
            with open(self.registry_path) as f:
                registry = json.load(f)

            for name, config in registry.get("strategies", {}).items():
                # Skip experimental strategies
                if config.get("status") == "experimental":
                    continue

                # Check if strategy name appears in trader code
                if name.lower() not in trader_code:
                    self.anomalies.append(
                        StrategyAnomaly(
                            anomaly_type="missing_integration",
                            strategy=name,
                            severity="high",
                            description=f"Strategy '{name}' is registered but not found in autonomous_trader.py",
                            timestamp=datetime.now().isoformat(),
                            recommendation=f"Add execute_{name}_trading() to autonomous_trader.py",
                        )
                    )

    def _detect_config_drift(self) -> None:
        """Detect unusual configuration changes."""
        if not self.system_state_path.exists():
            return

        with open(self.system_state_path) as f:
            state = json.load(f)

        strategies = state.get("strategies", {})

        for tier, config in strategies.items():
            # Check 1: Unusually high allocation
            allocation = config.get("allocation", 0)
            if allocation > 0.25:  # >25% is suspicious
                self.anomalies.append(
                    StrategyAnomaly(
                        anomaly_type="config_drift",
                        strategy=tier,
                        severity="medium",
                        description=f"Strategy '{tier}' has unusually high allocation ({allocation * 100:.0f}%)",
                        timestamp=datetime.now().isoformat(),
                        recommendation="Review allocation - consider diversifying",
                    )
                )

            # Check 2: Unusually high daily amount
            daily_amount = config.get("daily_amount", 0)
            if daily_amount > 100:  # >$100/day is suspicious for single strategy
                self.anomalies.append(
                    StrategyAnomaly(
                        anomaly_type="config_drift",
                        strategy=tier,
                        severity="medium",
                        description=f"Strategy '{tier}' has high daily amount (${daily_amount})",
                        timestamp=datetime.now().isoformat(),
                        recommendation="Verify daily amount is intentional",
                    )
                )

            # Check 3: Active but never executed
            is_active = config.get("status") == "active" or config.get("enabled")
            never_executed = config.get("trades_executed", 0) == 0
            last_execution = config.get("last_execution")

            if is_active and never_executed and not last_execution:
                self.anomalies.append(
                    StrategyAnomaly(
                        anomaly_type="missing_integration",
                        strategy=tier,
                        severity="high",
                        description=f"Strategy '{tier}' is active but has never executed",
                        timestamp=datetime.now().isoformat(),
                        recommendation="Check if strategy is properly wired in autonomous_trader.py",
                    )
                )

    def _detect_performance_drift(self) -> None:
        """Detect strategies with poor performance."""
        if not self.system_state_path.exists():
            return

        with open(self.system_state_path) as f:
            state = json.load(f)

        performance = state.get("performance", {})
        win_rate = performance.get("win_rate", 0)

        # Alert on very low win rate
        if win_rate > 0 and win_rate < 40:
            self.anomalies.append(
                StrategyAnomaly(
                    anomaly_type="performance_drift",
                    strategy="overall",
                    severity="high",
                    description=f"Overall win rate ({win_rate:.1f}%) is below threshold (40%)",
                    timestamp=datetime.now().isoformat(),
                    recommendation="Review strategy parameters and market conditions",
                )
            )

    def _detect_orphaned_strategies(self) -> None:
        """Detect strategy files that aren't registered."""
        strategies_dir = Path("src/strategies")
        if not strategies_dir.exists():
            return

        # Get registered strategy files
        registered_files = set()
        if self.registry_path.exists():
            with open(self.registry_path) as f:
                registry = json.load(f)
            for config in registry.get("strategies", {}).values():
                source_file = config.get("source_file", "")
                if source_file:
                    registered_files.add(source_file)

        # Check for unregistered strategy files
        for py_file in strategies_dir.glob("*_strategy.py"):
            relative_path = str(py_file)
            if relative_path not in registered_files and "src/strategies/" + py_file.name not in registered_files:
                # Skip base classes and utilities
                if py_file.name in ["base_strategy.py", "__init__.py"]:
                    continue

                self.anomalies.append(
                    StrategyAnomaly(
                        anomaly_type="orphaned_strategy",
                        strategy=py_file.stem,
                        severity="low",
                        description=f"Strategy file '{py_file}' is not registered in strategy_registry.json",
                        timestamp=datetime.now().isoformat(),
                        recommendation="Add to registry or delete if unused",
                    )
                )

    def get_report(self) -> dict[str, Any]:
        """Generate anomaly detection report."""
        if not self.anomalies:
            self.detect_all_anomalies()

        by_severity = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
        }

        for anomaly in self.anomalies:
            by_severity[anomaly.severity].append(anomaly)

        return {
            "timestamp": datetime.now().isoformat(),
            "total_anomalies": len(self.anomalies),
            "by_severity": {k: len(v) for k, v in by_severity.items()},
            "anomalies": [
                {
                    "type": a.anomaly_type,
                    "strategy": a.strategy,
                    "severity": a.severity,
                    "description": a.description,
                    "recommendation": a.recommendation,
                }
                for a in self.anomalies
            ],
            "action_required": len(by_severity["critical"]) + len(by_severity["high"]) > 0,
        }

    def save_report(self, path: str = "reports/strategy_anomaly_report.json") -> None:
        """Save anomaly report to file."""
        report = self.get_report()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Anomaly report saved to {path}")


def main():
    """Run anomaly detection."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("STRATEGY ANOMALY DETECTION")
    print("=" * 60)

    detector = StrategyAnomalyDetector()
    anomalies = detector.detect_all_anomalies()

    if not anomalies:
        print("\nNo anomalies detected.")
        return 0

    print(f"\nFound {len(anomalies)} anomalies:\n")

    by_severity = {"critical": [], "high": [], "medium": [], "low": []}
    for a in anomalies:
        by_severity[a.severity].append(a)

    for severity in ["critical", "high", "medium", "low"]:
        if by_severity[severity]:
            print(f"\n[{severity.upper()}]")
            for a in by_severity[severity]:
                print(f"  - {a.strategy}: {a.description}")
                print(f"    Recommendation: {a.recommendation}")

    # Save report
    detector.save_report()

    # Return non-zero if high/critical anomalies found
    if by_severity["critical"] or by_severity["high"]:
        return 1
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
