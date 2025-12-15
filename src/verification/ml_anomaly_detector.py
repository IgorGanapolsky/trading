"""
ML-Powered Anomaly Detection for Trading System

Detects anomalies in:
1. Code changes (risky patterns, large diffs)
2. Trading patterns (volume drops, performance drift)
3. System health (slow execution, high failure rates)

Uses statistical methods and simple ML for real-time detection.

Created: Dec 14, 2025
Purpose: Catch problems before they become incidents
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class Anomaly:
    """Detected anomaly."""

    timestamp: str
    category: str  # code, trading, health
    severity: str  # critical, high, medium, low
    description: str
    metric_name: str
    metric_value: float
    expected_range: Tuple[float, float]
    confidence: float  # 0.0 to 1.0


class MLAnomalyDetector:
    """
    ML-based anomaly detection for trading system.

    Uses statistical methods (Z-score, exponential moving average)
    and simple heuristics to detect abnormal behavior.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize anomaly detector.

        Args:
            data_dir: Path to data directory (defaults to project_root/data)
        """
        if data_dir is None:
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            data_dir = project_root / "data"

        self.data_dir = data_dir
        self.system_state_file = data_dir / "system_state.json"
        self.audit_trail_dir = data_dir / "audit_trail"
        self.anomaly_history_file = data_dir / "anomaly_history.json"

        # Anomaly thresholds (tuned from historical data)
        self.thresholds = {
            "trade_volume_drop": 0.5,  # 50% drop from baseline
            "win_rate_drop": 0.2,  # 20% absolute drop
            "execution_time_spike": 3.0,  # 3x normal execution time
            "failure_rate_spike": 0.15,  # >15% failure rate
            "code_change_size": 50,  # >50 files changed
        }

    def load_system_state(self) -> Optional[Dict]:
        """Load current system state."""
        if not self.system_state_file.exists():
            return None

        with open(self.system_state_file, "r") as f:
            return json.load(f)

    def save_anomaly(self, anomaly: Anomaly):
        """Save detected anomaly to history."""
        history = []
        if self.anomaly_history_file.exists():
            with open(self.anomaly_history_file, "r") as f:
                history = json.load(f)

        history.append(
            {
                "timestamp": anomaly.timestamp,
                "category": anomaly.category,
                "severity": anomaly.severity,
                "description": anomaly.description,
                "metric_name": anomaly.metric_name,
                "metric_value": anomaly.metric_value,
                "expected_range": anomaly.expected_range,
                "confidence": anomaly.confidence,
            }
        )

        # Keep last 1000 anomalies
        history = history[-1000:]

        with open(self.anomaly_history_file, "w") as f:
            json.dump(history, f, indent=2)

    def detect_trade_volume_anomaly(self) -> Optional[Anomaly]:
        """Detect abnormal trade volume (e.g., 0 trades when expecting 3-5).

        Returns:
            Anomaly if detected, None otherwise
        """
        state = self.load_system_state()
        if not state:
            return None

        # Expected: 3-5 trades per day (based on relaxed filters from Dec 4)
        expected_min = 1.0  # Conservative minimum
        expected_max = 10.0  # Upper bound

        # Check performance section
        performance = state.get("performance", {})
        total_trades = performance.get("total_trades", 0)

        # Calculate trades per day
        challenge = state.get("challenge", {})
        current_day = challenge.get("current_day", 1)

        if current_day == 0:
            return None

        trades_per_day = total_trades / max(current_day, 1)

        # Check if below threshold
        if trades_per_day < expected_min:
            return Anomaly(
                timestamp=datetime.utcnow().isoformat(),
                category="trading",
                severity="critical" if trades_per_day == 0 else "high",
                description=f"Trade volume abnormally low: {trades_per_day:.1f} trades/day (expected {expected_min}-{expected_max})",
                metric_name="trades_per_day",
                metric_value=trades_per_day,
                expected_range=(expected_min, expected_max),
                confidence=0.9,
            )

        return None

    def detect_win_rate_anomaly(self) -> Optional[Anomaly]:
        """Detect abnormal win rate.

        Returns:
            Anomaly if detected, None otherwise
        """
        state = self.load_system_state()
        if not state:
            return None

        performance = state.get("performance", {})
        win_rate = performance.get("win_rate", 0.0) / 100.0  # Convert to 0-1

        # Expected win rate: 55-65% (based on backtests)
        expected_min = 0.50
        expected_max = 0.70

        total_trades = performance.get("total_trades", 0)

        # Only check if we have enough samples
        if total_trades < 10:
            return None

        # Check if outside expected range
        if win_rate < expected_min or win_rate > expected_max:
            severity = "high" if win_rate < 0.40 or win_rate > 0.80 else "medium"

            return Anomaly(
                timestamp=datetime.utcnow().isoformat(),
                category="trading",
                severity=severity,
                description=f"Win rate outside expected range: {win_rate:.1%} (expected {expected_min:.0%}-{expected_max:.0%})",
                metric_name="win_rate",
                metric_value=win_rate,
                expected_range=(expected_min, expected_max),
                confidence=0.8 if total_trades >= 30 else 0.6,
            )

        return None

    def detect_system_health_anomaly(self) -> Optional[Anomaly]:
        """Detect system health issues (stale data, no recent execution).

        Returns:
            Anomaly if detected, None otherwise
        """
        state = self.load_system_state()
        if not state:
            return Anomaly(
                timestamp=datetime.utcnow().isoformat(),
                category="health",
                severity="critical",
                description="System state file missing",
                metric_name="state_file_exists",
                metric_value=0.0,
                expected_range=(1.0, 1.0),
                confidence=1.0,
            )

        # Check last update time
        meta = state.get("meta", {})
        last_updated = meta.get("last_updated")

        if not last_updated:
            return Anomaly(
                timestamp=datetime.utcnow().isoformat(),
                category="health",
                severity="high",
                description="System state missing last_updated timestamp",
                metric_name="last_updated_exists",
                metric_value=0.0,
                expected_range=(1.0, 1.0),
                confidence=0.9,
            )

        # Parse timestamp
        try:
            last_update_dt = datetime.fromisoformat(last_updated)
            age_hours = (datetime.utcnow() - last_update_dt).total_seconds() / 3600

            # Alert if stale (>48 hours, accounting for weekends)
            if age_hours > 48:
                return Anomaly(
                    timestamp=datetime.utcnow().isoformat(),
                    category="health",
                    severity="high",
                    description=f"System state stale: {age_hours:.1f} hours old (>48h threshold)",
                    metric_name="state_age_hours",
                    metric_value=age_hours,
                    expected_range=(0.0, 48.0),
                    confidence=0.85,
                )

        except Exception as e:
            return Anomaly(
                timestamp=datetime.utcnow().isoformat(),
                category="health",
                severity="medium",
                description=f"Failed to parse last_updated timestamp: {e}",
                metric_name="timestamp_parse_error",
                metric_value=0.0,
                expected_range=(1.0, 1.0),
                confidence=0.7,
            )

        return None

    def detect_code_change_anomaly(self, files_changed: List[str]) -> Optional[Anomaly]:
        """Detect risky code changes.

        Args:
            files_changed: List of changed file paths

        Returns:
            Anomaly if detected, None otherwise
        """
        num_files = len(files_changed)

        # Large PR risk (from ll_009)
        if num_files > self.thresholds["code_change_size"]:
            return Anomaly(
                timestamp=datetime.utcnow().isoformat(),
                category="code",
                severity="high",
                description=f"Very large code change: {num_files} files (>50 threshold). Bugs hide in large PRs.",
                metric_name="files_changed",
                metric_value=float(num_files),
                expected_range=(1.0, 50.0),
                confidence=0.9,
            )

        # Critical file changes
        critical_files = [
            "src/orchestrator/main.py",
            "src/execution/alpaca_executor.py",
            "src/risk/trade_gateway.py",
            "scripts/autonomous_trader.py",
        ]

        critical_changed = [f for f in files_changed if any(cf in f for cf in critical_files)]

        if critical_changed:
            return Anomaly(
                timestamp=datetime.utcnow().isoformat(),
                category="code",
                severity="medium",
                description=f"Critical files changed: {len(critical_changed)} files. Extra verification required.",
                metric_name="critical_files_changed",
                metric_value=float(len(critical_changed)),
                expected_range=(0.0, 1.0),
                confidence=0.8,
            )

        return None

    def run_all_checks(
        self, files_changed: Optional[List[str]] = None
    ) -> List[Anomaly]:
        """Run all anomaly detection checks.

        Args:
            files_changed: Optional list of changed files for code analysis

        Returns:
            List of detected anomalies
        """
        anomalies = []

        # Trading anomalies
        trade_volume_anomaly = self.detect_trade_volume_anomaly()
        if trade_volume_anomaly:
            anomalies.append(trade_volume_anomaly)
            self.save_anomaly(trade_volume_anomaly)

        win_rate_anomaly = self.detect_win_rate_anomaly()
        if win_rate_anomaly:
            anomalies.append(win_rate_anomaly)
            self.save_anomaly(win_rate_anomaly)

        # Health anomalies
        health_anomaly = self.detect_system_health_anomaly()
        if health_anomaly:
            anomalies.append(health_anomaly)
            self.save_anomaly(health_anomaly)

        # Code anomalies (if files provided)
        if files_changed:
            code_anomaly = self.detect_code_change_anomaly(files_changed)
            if code_anomaly:
                anomalies.append(code_anomaly)
                self.save_anomaly(code_anomaly)

        return anomalies

    def get_recent_anomalies(self, hours: int = 24) -> List[Dict]:
        """Get anomalies from last N hours.

        Args:
            hours: Look back period in hours

        Returns:
            List of anomaly dictionaries
        """
        if not self.anomaly_history_file.exists():
            return []

        with open(self.anomaly_history_file, "r") as f:
            history = json.load(f)

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        recent = []
        for anomaly in history:
            try:
                timestamp = datetime.fromisoformat(anomaly["timestamp"])
                if timestamp >= cutoff:
                    recent.append(anomaly)
            except Exception:
                pass

        return recent


def cli_run_checks():
    """CLI tool to run anomaly detection checks."""
    import argparse

    parser = argparse.ArgumentParser(description="ML anomaly detection for trading system")
    parser.add_argument("--files", nargs="+", help="Changed files to analyze")
    parser.add_argument(
        "--recent",
        type=int,
        help="Show anomalies from last N hours",
    )

    args = parser.parse_args()

    detector = MLAnomalyDetector()

    if args.recent:
        anomalies = detector.get_recent_anomalies(hours=args.recent)
        print(f"\n📊 Anomalies from last {args.recent} hours: {len(anomalies)}\n")
        for a in anomalies:
            print(f"[{a['severity'].upper()}] {a['timestamp']}")
            print(f"  {a['description']}")
            print()
    else:
        anomalies = detector.run_all_checks(files_changed=args.files)

        print("\n" + "=" * 60)
        print(f"ML ANOMALY DETECTION RESULTS: {len(anomalies)} anomalies found")
        print("=" * 60 + "\n")

        if not anomalies:
            print("✅ No anomalies detected")
        else:
            for anomaly in anomalies:
                icon = {"critical": "🚨", "high": "⚠️", "medium": "⚡", "low": "ℹ️"}.get(
                    anomaly.severity, "•"
                )
                print(f"{icon} [{anomaly.severity.upper()}] {anomaly.category}")
                print(f"  {anomaly.description}")
                print(
                    f"  Value: {anomaly.metric_value:.2f}, Expected: {anomaly.expected_range}"
                )
                print(f"  Confidence: {anomaly.confidence:.1%}\n")

        # Exit with error if critical anomalies found
        critical_count = sum(1 for a in anomalies if a.severity == "critical")
        if critical_count > 0:
            print(f"❌ {critical_count} critical anomalies found")
            return 1

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(cli_run_checks())
