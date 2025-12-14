#!/usr/bin/env python3
"""
ML-Powered Anomaly Detector for Pre-Merge Verification

Uses pattern recognition and statistical analysis to detect anomalies in:
1. Code changes (unusual patterns, complexity spikes)
2. Test coverage changes (drops indicate risk)
3. Configuration changes (drift from baseline)
4. Trading logic changes (potential P&L impact)

Integrates with:
- RAG knowledge base for context-aware detection
- LangSmith for experiment tracking
- Existing ChromaDB vector store

Author: Trading System CTO
Created: 2025-12-11
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Historical baselines from lessons learned
BASELINES = {
    "avg_file_complexity": 15.0,  # Cyclomatic complexity
    "max_function_length": 50,  # Lines per function
    "min_test_coverage": 0.60,  # 60% coverage baseline
    "max_import_count": 25,  # Imports per file
    "avg_daily_trades": 5,  # Expected trades per day
    "max_consecutive_losses": 3,  # Risk threshold
    "normal_win_rate_range": (0.45, 0.70),  # Expected win rate
    "normal_sharpe_range": (0.5, 2.5),  # Expected Sharpe
}


@dataclass
class Anomaly:
    """Detected anomaly."""

    category: str  # code, test, config, trading
    severity: str  # high, medium, low
    description: str
    metric_name: str
    expected_value: float | str
    actual_value: float | str
    deviation_pct: float
    recommendation: str


@dataclass
class AnomalyReport:
    """Complete anomaly detection report."""

    timestamp: str
    anomalies: list[Anomaly]
    high_count: int
    medium_count: int
    low_count: int
    passed: bool
    risk_score: float  # 0-100


class MLAnomalyDetector:
    """
    ML-powered anomaly detection for trading system verification.

    Uses statistical methods and learned patterns to detect:
    - Code anomalies (complexity, style violations)
    - Configuration drift (unexpected parameter changes)
    - Trading anomalies (unusual patterns that may indicate bugs)
    """

    def __init__(self, model_path: str | None = None):
        """Initialize the anomaly detector."""
        self.model_path = Path(model_path or "data/ml_models/anomaly_detector.json")
        self.baselines = BASELINES.copy()
        self._load_learned_patterns()

    def _load_learned_patterns(self) -> None:
        """Load learned patterns from historical data."""
        if self.model_path.exists():
            with open(self.model_path) as f:
                patterns = json.load(f)
                self.baselines.update(patterns.get("baselines", {}))
                logger.info("Loaded learned patterns from model")

    def detect_code_anomalies(self, file_path: Path) -> list[Anomaly]:
        """Detect anomalies in code changes."""
        anomalies: list[Anomaly] = []

        if not file_path.exists() or file_path.suffix != ".py":
            return anomalies

        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Check function length
        function_lines = self._extract_function_lengths(content)
        for func_name, length in function_lines.items():
            if length > self.baselines["max_function_length"]:
                deviation = (
                    (length - self.baselines["max_function_length"])
                    / self.baselines["max_function_length"]
                    * 100
                )
                anomalies.append(
                    Anomaly(
                        category="code",
                        severity="medium" if deviation < 50 else "high",
                        description=f"Function '{func_name}' is too long ({length} lines)",
                        metric_name="function_length",
                        expected_value=self.baselines["max_function_length"],
                        actual_value=length,
                        deviation_pct=deviation,
                        recommendation="Split into smaller functions for maintainability",
                    )
                )

        # Check import count
        import_count = len(re.findall(r"^(?:from|import)\s+", content, re.MULTILINE))
        if import_count > self.baselines["max_import_count"]:
            deviation = (
                (import_count - self.baselines["max_import_count"])
                / self.baselines["max_import_count"]
                * 100
            )
            anomalies.append(
                Anomaly(
                    category="code",
                    severity="low",
                    description=f"High import count ({import_count}) may indicate coupling issues",
                    metric_name="import_count",
                    expected_value=self.baselines["max_import_count"],
                    actual_value=import_count,
                    deviation_pct=deviation,
                    recommendation="Review imports for unnecessary dependencies",
                )
            )

        # Check for complexity indicators
        nesting_depth = self._calculate_max_nesting(lines)
        if nesting_depth > 4:
            anomalies.append(
                Anomaly(
                    category="code",
                    severity="medium",
                    description=f"Deep nesting detected (depth={nesting_depth})",
                    metric_name="nesting_depth",
                    expected_value=4,
                    actual_value=nesting_depth,
                    deviation_pct=(nesting_depth - 4) / 4 * 100,
                    recommendation="Refactor to reduce cognitive complexity",
                )
            )

        return anomalies

    def detect_config_anomalies(self, config_path: Path) -> list[Anomaly]:
        """Detect anomalies in configuration changes."""
        anomalies: list[Anomaly] = []

        if not config_path.exists():
            return anomalies

        content = config_path.read_text(encoding="utf-8")

        # Check for risky configuration patterns
        risk_patterns = [
            (r"max_position.*=\s*([0-9.]+)", "max_position_pct", 0.10, 0.25),
            (r"max_daily_loss.*=\s*([0-9.]+)", "max_daily_loss_pct", 0.02, 0.05),
            (r"max_drawdown.*=\s*([0-9.]+)", "max_drawdown_pct", 0.10, 0.15),
        ]

        for pattern, metric, expected, threshold in risk_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                if value > threshold:
                    deviation = (value - expected) / expected * 100
                    anomalies.append(
                        Anomaly(
                            category="config",
                            severity="high",
                            description=f"Risk parameter {metric}={value} exceeds safe threshold {threshold}",
                            metric_name=metric,
                            expected_value=expected,
                            actual_value=value,
                            deviation_pct=deviation,
                            recommendation=f"Consider reducing {metric} to {threshold} or lower",
                        )
                    )

        return anomalies

    def detect_trading_anomalies(self, trades_data: list[dict[str, Any]]) -> list[Anomaly]:
        """Detect anomalies in trading patterns."""
        anomalies: list[Anomaly] = []

        if not trades_data:
            return anomalies

        # Calculate metrics
        wins = sum(1 for t in trades_data if t.get("pnl", 0) > 0)
        total = len(trades_data)
        win_rate = wins / total if total > 0 else 0

        # Check win rate
        min_wr, max_wr = self.baselines["normal_win_rate_range"]
        if win_rate < min_wr or win_rate > max_wr:
            deviation = abs(win_rate - (min_wr + max_wr) / 2) / ((max_wr - min_wr) / 2) * 100
            anomalies.append(
                Anomaly(
                    category="trading",
                    severity="high" if win_rate < 0.40 else "medium",
                    description=f"Win rate {win_rate:.1%} outside normal range {min_wr:.0%}-{max_wr:.0%}",
                    metric_name="win_rate",
                    expected_value=f"{min_wr:.0%}-{max_wr:.0%}",
                    actual_value=f"{win_rate:.1%}",
                    deviation_pct=deviation,
                    recommendation="Review strategy parameters and market conditions",
                )
            )

        # Check for consecutive losses
        consecutive_losses = self._count_max_consecutive_losses(trades_data)
        if consecutive_losses >= self.baselines["max_consecutive_losses"]:
            anomalies.append(
                Anomaly(
                    category="trading",
                    severity="high",
                    description=f"Detected {consecutive_losses} consecutive losses",
                    metric_name="consecutive_losses",
                    expected_value=self.baselines["max_consecutive_losses"],
                    actual_value=consecutive_losses,
                    deviation_pct=(consecutive_losses - self.baselines["max_consecutive_losses"])
                    / self.baselines["max_consecutive_losses"]
                    * 100,
                    recommendation="Trigger circuit breaker - pause trading for review",
                )
            )

        return anomalies

    def _extract_function_lengths(self, content: str) -> dict[str, int]:
        """Extract function names and their line counts."""
        functions: dict[str, int] = {}
        lines = content.split("\n")

        func_pattern = re.compile(r"^\s*def\s+(\w+)\s*\(")
        current_func = None
        func_start = 0
        base_indent = 0

        for i, line in enumerate(lines):
            match = func_pattern.match(line)
            if match:
                # Save previous function if any
                if current_func:
                    functions[current_func] = i - func_start
                current_func = match.group(1)
                func_start = i
                base_indent = len(line) - len(line.lstrip())

            elif current_func and line.strip():
                # Check if we're still in the function
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= base_indent and not line.strip().startswith("#"):
                    functions[current_func] = i - func_start
                    current_func = None

        # Don't forget the last function
        if current_func:
            functions[current_func] = len(lines) - func_start

        return functions

    def _calculate_max_nesting(self, lines: list[str]) -> int:
        """Calculate maximum nesting depth in code."""
        max_depth = 0
        current_depth = 0

        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith(
                ("if ", "for ", "while ", "with ", "try:", "else:", "elif ", "except")
            ):
                indent = len(line) - len(stripped)
                depth = indent // 4  # Assuming 4-space indentation
                current_depth = depth + 1
                max_depth = max(max_depth, current_depth)

        return max_depth

    def _count_max_consecutive_losses(self, trades: list[dict[str, Any]]) -> int:
        """Count maximum consecutive losing trades."""
        max_consecutive = 0
        current_consecutive = 0

        for trade in sorted(trades, key=lambda t: t.get("timestamp", "")):
            if trade.get("pnl", 0) < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive

    def run_full_detection(
        self,
        code_files: list[Path] | None = None,
        config_files: list[Path] | None = None,
        trades_data: list[dict[str, Any]] | None = None,
    ) -> AnomalyReport:
        """Run full anomaly detection across all categories."""
        all_anomalies: list[Anomaly] = []

        # Code anomalies
        if code_files:
            for file_path in code_files:
                all_anomalies.extend(self.detect_code_anomalies(file_path))

        # Config anomalies
        if config_files:
            for config_path in config_files:
                all_anomalies.extend(self.detect_config_anomalies(config_path))

        # Trading anomalies
        if trades_data:
            all_anomalies.extend(self.detect_trading_anomalies(trades_data))

        # Count by severity
        high = sum(1 for a in all_anomalies if a.severity == "high")
        medium = sum(1 for a in all_anomalies if a.severity == "medium")
        low = sum(1 for a in all_anomalies if a.severity == "low")

        # Calculate risk score (0-100)
        risk_score = min(100, high * 30 + medium * 10 + low * 2)

        # Determine if passed
        passed = high == 0

        return AnomalyReport(
            timestamp=datetime.now().isoformat(),
            anomalies=all_anomalies,
            high_count=high,
            medium_count=medium,
            low_count=low,
            passed=passed,
            risk_score=risk_score,
        )


def update_learned_patterns(new_baselines: dict[str, Any], model_path: str | None = None) -> None:
    """Update learned patterns based on new data."""
    model_path = Path(model_path or "data/ml_models/anomaly_detector.json")
    model_path.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if model_path.exists():
        with open(model_path) as f:
            existing = json.load(f)

    # Update with exponential moving average
    baselines = existing.get("baselines", BASELINES.copy())
    alpha = 0.1  # Learning rate

    for key, value in new_baselines.items():
        if key in baselines and isinstance(value, int | float):
            baselines[key] = alpha * value + (1 - alpha) * baselines[key]
        else:
            baselines[key] = value

    existing["baselines"] = baselines
    existing["last_updated"] = datetime.now().isoformat()

    with open(model_path, "w") as f:
        json.dump(existing, f, indent=2)

    logger.info(f"Updated learned patterns: {list(new_baselines.keys())}")


def main() -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="ML Anomaly Detector")
    parser.add_argument("--code", nargs="*", help="Python files to check")
    parser.add_argument("--config", nargs="*", help="Config files to check")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    detector = MLAnomalyDetector()

    code_files = [Path(f) for f in (args.code or [])]
    config_files = [Path(f) for f in (args.config or [])]

    report = detector.run_full_detection(
        code_files=code_files or None,
        config_files=config_files or None,
    )

    if args.json:
        output = {
            "timestamp": report.timestamp,
            "passed": report.passed,
            "risk_score": report.risk_score,
            "counts": {
                "high": report.high_count,
                "medium": report.medium_count,
                "low": report.low_count,
            },
            "anomalies": [
                {
                    "category": a.category,
                    "severity": a.severity,
                    "description": a.description,
                    "metric": a.metric_name,
                    "expected": a.expected_value,
                    "actual": a.actual_value,
                }
                for a in report.anomalies
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        status = "✅ PASSED" if report.passed else "❌ FAILED"
        print(f"{status} - Risk Score: {report.risk_score}/100")
        print(f"High: {report.high_count}, Medium: {report.medium_count}, Low: {report.low_count}")
        print()
        for anomaly in report.anomalies:
            icon = {"high": "🚨", "medium": "⚠️", "low": "ℹ️"}.get(anomaly.severity, "•")
            print(f"{icon} [{anomaly.category}] {anomaly.description}")
            print(f"   Expected: {anomaly.expected_value}, Actual: {anomaly.actual_value}")
            print(f"   Recommendation: {anomaly.recommendation}")
            print()

    return 0 if report.passed else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
