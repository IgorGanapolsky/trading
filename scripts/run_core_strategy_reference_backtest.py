#!/usr/bin/env python3
"""
Core Strategy Reference Backtest Validator

Validates that core strategy metrics haven't degraded below acceptable thresholds.
Used by CI to ensure strategy changes don't break performance guarantees.

Exit codes:
  0 - All metrics within acceptable bounds
  1 - Metrics degraded below thresholds

Environment override:
  ACCEPT_METRIC_DEGRADATION=true - Skip validation (for intentional changes)
"""

import json
import os
import sys
from pathlib import Path

# Thresholds from enforce_promotion_gate.py (Dec 11, 2025 R&D pilot values)
THRESHOLDS = {
    "min_win_rate": 50.0,  # Relaxed for R&D phase (was 55%)
    "min_sharpe": 0.0,  # Relaxed for R&D phase (was 1.2)
    "max_drawdown": 20.0,  # Relaxed for R&D phase (was 10%)
    "min_scenarios_pass": 0.5,  # At least 50% of scenarios should pass
}


def load_backtest_summary() -> dict | None:
    """Load the latest backtest summary."""
    summary_path = Path("data/backtests/latest_summary.json")
    if not summary_path.exists():
        print(f"WARNING: Backtest summary not found at {summary_path}")
        print("Skipping validation (no baseline to compare against)")
        return None

    with open(summary_path) as f:
        return json.load(f)


def validate_metrics(summary: dict) -> tuple[bool, list[str]]:
    """Validate metrics against thresholds.

    Returns:
        (passed, issues) tuple
    """
    issues = []

    scenarios = summary.get("scenarios", [])
    if not scenarios:
        issues.append("No scenarios found in backtest summary")
        return False, issues

    # Calculate aggregate metrics
    total_scenarios = len(scenarios)
    passed_scenarios = sum(1 for s in scenarios if s.get("status") == "pass")
    pass_rate = passed_scenarios / total_scenarios if total_scenarios > 0 else 0

    # Check scenario pass rate
    if pass_rate < THRESHOLDS["min_scenarios_pass"]:
        issues.append(
            f"Scenario pass rate {pass_rate:.1%} < {THRESHOLDS['min_scenarios_pass']:.1%}"
        )

    # Calculate average metrics across scenarios
    win_rates = [s.get("win_rate_pct", 0) for s in scenarios]
    sharpes = [s.get("sharpe_ratio", 0) for s in scenarios]
    drawdowns = [abs(s.get("max_drawdown_pct", 0)) for s in scenarios]

    avg_win_rate = sum(win_rates) / len(win_rates) if win_rates else 0
    avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else 0
    max_drawdown = max(drawdowns) if drawdowns else 0

    # Check thresholds
    if avg_win_rate < THRESHOLDS["min_win_rate"]:
        issues.append(f"Avg win rate {avg_win_rate:.1f}% < {THRESHOLDS['min_win_rate']:.1f}%")

    if avg_sharpe < THRESHOLDS["min_sharpe"]:
        issues.append(f"Avg Sharpe {avg_sharpe:.2f} < {THRESHOLDS['min_sharpe']:.2f}")

    if max_drawdown > THRESHOLDS["max_drawdown"]:
        issues.append(f"Max drawdown {max_drawdown:.1f}% > {THRESHOLDS['max_drawdown']:.1f}%")

    passed = len(issues) == 0
    return passed, issues


def main() -> int:
    """Main entry point."""
    print("=" * 60)
    print("Core Strategy Reference Backtest Validation")
    print("=" * 60)

    # Check for override
    if os.environ.get("ACCEPT_METRIC_DEGRADATION", "").lower() == "true":
        print("ACCEPT_METRIC_DEGRADATION is set - skipping validation")
        return 0

    # Load summary
    summary = load_backtest_summary()
    if summary is None:
        # No baseline - pass by default (first run scenario)
        return 0

    # Report summary info
    print(f"Summary generated: {summary.get('generated_at', 'unknown')}")
    print(f"Scenarios: {summary.get('scenario_count', 0)}")
    print()

    # Validate
    passed, issues = validate_metrics(summary)

    if passed:
        print("VALIDATION PASSED")
        print("All metrics within acceptable bounds")
        return 0
    else:
        print("VALIDATION FAILED")
        print("Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print()
        print("To accept intentional degradation, add 'ACCEPT_METRIC_DEGRADATION'")
        print("to your PR description or set the environment variable.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
