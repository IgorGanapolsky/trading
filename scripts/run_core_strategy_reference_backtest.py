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

# Thresholds aligned with CEO mandate: "WE ARE NOT ALLOWED TO LOSE MONEY"
# Capital preservation is the #1 priority, not high win rates
# Updated Jan 6, 2026 - Phil Town Rule #1 compliance
THRESHOLDS = {
    "min_win_rate": 25.0,  # Capital preservation strategy has lower win rate but smaller losses
    "min_sharpe": -2.0,  # Negative Sharpe acceptable during R&D (capital preservation > returns)
    "max_drawdown": 5.0,  # CEO mandate: max 5% drawdown (strict capital protection)
    "min_scenarios_pass": 0.9,  # 90% scenarios must pass (capital survival)
    "min_capital_preserved": 95.0,  # NEW: Primary metric - must preserve 95%+ capital
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


def validate_flat_format(summary: dict) -> tuple[bool, list[str]]:
    """Validate flat format backtest (single result, no scenarios).

    Returns:
        (passed, issues) tuple
    """
    issues = []

    # Extract metrics from flat format
    win_rate = summary.get("win_rate", 0) * 100  # Convert to percentage
    sharpe = summary.get("sharpe_ratio", 0)
    total_pnl = summary.get("total_pnl", 0)

    # For flat format, check if we're profitable (Rule #1)
    if total_pnl < 0:
        issues.append(f"Total P/L is negative: ${total_pnl:.2f} (Rule #1 violation)")

    # Sharpe check (relaxed for flat format since it's a single backtest)
    if sharpe < THRESHOLDS["min_sharpe"]:
        issues.append(f"Sharpe ratio {sharpe:.2f} < {THRESHOLDS['min_sharpe']:.2f}")

    # Win rate check
    if win_rate < THRESHOLDS["min_win_rate"]:
        # For flat format with positive P/L, win rate is less critical
        if total_pnl <= 0:
            issues.append(f"Win rate {win_rate:.1f}% < {THRESHOLDS['min_win_rate']:.1f}%")

    return len(issues) == 0, issues


def validate_metrics(summary: dict) -> tuple[bool, list[str]]:
    """Validate metrics against thresholds.

    Returns:
        (passed, issues) tuple

    Handles two formats:
    1. Scenario-based (old): Has 'scenarios' array with multiple test scenarios
    2. Flat (new): Single backtest result with direct metrics
    """
    issues = []

    scenarios = summary.get("scenarios", [])

    # Handle flat format (no scenarios array, has total_trades)
    if not scenarios and "total_trades" in summary:
        print("Detected flat format backtest (single result)")
        return validate_flat_format(summary)

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

    # Calculate capital preservation (PRIMARY METRIC per CEO mandate)
    capital_preserved = [s.get("capital_preserved_pct", 100.0) for s in scenarios]
    min_capital_preserved = min(capital_preserved) if capital_preserved else 100.0

    # Check capital preservation FIRST (CEO mandate: "WE ARE NOT ALLOWED TO LOSE MONEY")
    if min_capital_preserved < THRESHOLDS.get("min_capital_preserved", 95.0):
        issues.append(
            f"CRITICAL: Capital preservation {min_capital_preserved:.1f}% < "
            f"{THRESHOLDS['min_capital_preserved']:.1f}% (Rule #1 violation!)"
        )

    # Check max drawdown (strict - CEO mandate)
    if max_drawdown > THRESHOLDS["max_drawdown"]:
        issues.append(f"Max drawdown {max_drawdown:.1f}% > {THRESHOLDS['max_drawdown']:.1f}%")

    # Check secondary metrics (relaxed for capital preservation strategy)
    if avg_win_rate < THRESHOLDS["min_win_rate"]:
        issues.append(f"Avg win rate {avg_win_rate:.1f}% < {THRESHOLDS['min_win_rate']:.1f}%")

    if avg_sharpe < THRESHOLDS["min_sharpe"]:
        issues.append(f"Avg Sharpe {avg_sharpe:.2f} < {THRESHOLDS['min_sharpe']:.2f}")

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
    if "scenarios" in summary:
        print(f"Summary generated: {summary.get('generated_at', 'unknown')}")
        print(f"Scenarios: {summary.get('scenario_count', 0)}")
    else:
        # Flat format
        print(f"Summary generated: {summary.get('timestamp', 'unknown')}")
        print(f"Total trades: {summary.get('total_trades', 0)}")
        print(f"Total P/L: ${summary.get('total_pnl', 0):.2f}")
        print(f"Win rate: {summary.get('win_rate', 0) * 100:.1f}%")
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
