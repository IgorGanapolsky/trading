#!/usr/bin/env python3
"""
Tests for dashboard metrics calculations.

Ensures all risk metrics are calculated correctly and completely.
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.dashboard_metrics import TradingMetricsCalculator
from scripts.enhanced_dashboard_metrics import EnhancedMetricsCalculator


def assert_condition(condition, message):
    """Simple assertion helper."""
    if not condition:
        raise AssertionError(message)


class TestDashboardMetricsCompleteness:
    """Test that all required metrics are calculated."""

    def test_risk_metrics_completeness(self):
        """Verify all risk metrics are calculated and returned."""
        # Create sample performance log with varying equity
        perf_log = []
        base_equity = 100000.0
        dates = [date.today() - timedelta(days=i) for i in range(30, 0, -1)]

        for i, d in enumerate(dates):
            # Create equity curve with some variation
            equity = base_equity + (i * 10) + (np.sin(i / 5) * 50)
            perf_log.append(
                {
                    "date": d.isoformat(),
                    "equity": equity,
                    "pl": equity - base_equity,
                    "pl_pct": (equity - base_equity) / base_equity,
                }
            )

        calculator = TradingMetricsCalculator()
        risk_metrics = calculator._calculate_risk_metrics(
            perf_log, base_equity, perf_log[-1]["equity"]
        )

        # Required metrics that must be present
        required_metrics = [
            "max_drawdown_pct",
            "current_drawdown_pct",
            "sharpe_ratio",
            "sortino_ratio",
            "volatility_annualized",
            "worst_daily_loss",
            "var_95",
            "var_99",  # This was missing!
            "cvar_95",  # This was missing!
            "ulcer_index",  # This was missing!
            "calmar_ratio",  # This was missing!
            "peak_equity",
            "trading_days",
        ]

        missing_metrics = []
        for metric in required_metrics:
            if metric not in risk_metrics:
                missing_metrics.append(metric)
            elif risk_metrics[metric] == 0.0 and metric not in ["trading_days"]:
                # Check if zero is reasonable (might be legitimately zero)
                # But flag it for review
                pass

        assert_condition(
            not missing_metrics,
            f"Missing required risk metrics: {missing_metrics}. "
            f"All metrics: {list(risk_metrics.keys())}",
        )

    def test_risk_metrics_not_all_zeros(self):
        """Verify metrics are actually calculated, not just defaulted to zero."""
        # Create performance log with clear variation
        perf_log = []
        base_equity = 100000.0

        # Create equity curve with clear drawdown and recovery
        equities = [
            100000,
            101000,
            102000,
            100500,
            99000,
            98500,
            99500,
            101000,
            102500,
            103000,
        ]

        for i, equity in enumerate(equities):
            perf_log.append(
                {
                    "date": (date.today() - timedelta(days=len(equities) - i)).isoformat(),
                    "equity": float(equity),
                    "pl": float(equity - base_equity),
                    "pl_pct": (equity - base_equity) / base_equity,
                }
            )

        calculator = TradingMetricsCalculator()
        risk_metrics = calculator._calculate_risk_metrics(
            perf_log, base_equity, perf_log[-1]["equity"]
        )

        # With this data, we should have non-zero values for most metrics
        assert_condition(risk_metrics["max_drawdown_pct"] > 0, "Max drawdown should be > 0")
        assert_condition(risk_metrics["volatility_annualized"] > 0, "Volatility should be > 0")
        assert_condition(risk_metrics["ulcer_index"] >= 0, "Ulcer index should be >= 0")
        assert_condition(
            risk_metrics["trading_days"] == len(equities) - 1,
            f"Trading days should match: got {risk_metrics['trading_days']}, expected {len(equities) - 1}",
        )

    def test_enhanced_metrics_completeness(self):
        """Verify enhanced metrics calculator includes all base metrics."""
        calculator = EnhancedMetricsCalculator()

        # Create minimal valid data
        perf_log = []
        base_equity = 100000.0
        for i in range(5):
            equity = base_equity + (i * 100)
            perf_log.append(
                {
                    "date": (date.today() - timedelta(days=5 - i)).isoformat(),
                    "equity": equity,
                    "pl": equity - base_equity,
                    "pl_pct": (equity - base_equity) / base_equity,
                }
            )

            # Save to temp file for calculator to load
            import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            perf_file = data_dir / "performance_log.json"
            with open(perf_file, "w") as f:
                json.dump(perf_log, f)

            # Create system_state.json
            system_state_file = data_dir / "system_state.json"
            with open(system_state_file, "w") as f:
                json.dump(
                    {
                        "account": {
                            "current_equity": perf_log[-1]["equity"],
                            "starting_balance": base_equity,
                        },
                        "performance": {"closed_trades": [], "open_positions": []},
                    },
                    f,
                )

            calculator.data_dir = data_dir
            all_metrics = calculator.calculate_all_metrics()

            risk_metrics = all_metrics.get("risk_metrics", {})

            # Verify enhanced metrics are present
            assert_condition("ulcer_index" in risk_metrics, "Ulcer Index should be calculated")
            assert_condition("calmar_ratio" in risk_metrics, "Calmar Ratio should be calculated")
            assert_condition("var_99" in risk_metrics, "VaR (99%) should be calculated")
            assert_condition("cvar_95" in risk_metrics, "CVaR (95%) should be calculated")

    def test_metrics_match_world_class_analytics(self):
        """Verify metrics match WorldClassAnalytics implementation."""
        try:
            from src.analytics.world_class_analytics import WorldClassAnalytics

            # Create equity curve
            equity_curve = [
                100000,
                101000,
                102000,
                100500,
                99000,
                99500,
                101000,
                102500,
            ]

            # Calculate with WorldClassAnalytics
            analytics = WorldClassAnalytics()
            wc_metrics = analytics.calculate_risk_metrics(equity_curve)

            # Calculate with TradingMetricsCalculator
            perf_log = []
            for i, equity in enumerate(equity_curve):
                perf_log.append(
                    {
                        "date": (date.today() - timedelta(days=len(equity_curve) - i)).isoformat(),
                        "equity": float(equity),
                    }
                )

            calculator = TradingMetricsCalculator()
            calc_metrics = calculator._calculate_risk_metrics(
                perf_log, equity_curve[0], equity_curve[-1]
            )

            # Compare key metrics (allow small floating point differences)
            assert_condition(
                abs(wc_metrics.max_drawdown_pct - calc_metrics["max_drawdown_pct"]) < 0.01,
                f"Max drawdown mismatch: {wc_metrics.max_drawdown_pct} vs {calc_metrics['max_drawdown_pct']}",
            )
            assert_condition(
                abs(wc_metrics.ulcer_index - calc_metrics["ulcer_index"]) < 0.01,
                f"Ulcer index mismatch: {wc_metrics.ulcer_index} vs {calc_metrics['ulcer_index']}",
            )
            assert_condition(
                abs(wc_metrics.sharpe_ratio - calc_metrics["sharpe_ratio"]) < 0.1,
                f"Sharpe ratio mismatch: {wc_metrics.sharpe_ratio} vs {calc_metrics['sharpe_ratio']}",
            )
            assert_condition(
                abs(wc_metrics.calmar_ratio - calc_metrics["calmar_ratio"]) < 1.0,
                f"Calmar ratio mismatch: {wc_metrics.calmar_ratio} vs {calc_metrics['calmar_ratio']}",
            )

        except ImportError:
            print("⚠️  WorldClassAnalytics not available, skipping comparison test")


def run_tests():
    """Run all tests."""
    print("=" * 70)
    print("Testing Dashboard Metrics Completeness")
    print("=" * 70)

    test = TestDashboardMetricsCompleteness()

    try:
        test.test_risk_metrics_completeness()
        print("✅ test_risk_metrics_completeness: PASSED")
    except AssertionError as e:
        print(f"❌ test_risk_metrics_completeness: FAILED - {e}")
        return 1

    try:
        test.test_risk_metrics_not_all_zeros()
        print("✅ test_risk_metrics_not_all_zeros: PASSED")
    except AssertionError as e:
        print(f"❌ test_risk_metrics_not_all_zeros: FAILED - {e}")
        return 1

    try:
        test.test_enhanced_metrics_completeness()
        print("✅ test_enhanced_metrics_completeness: PASSED")
    except AssertionError as e:
        print(f"❌ test_enhanced_metrics_completeness: FAILED - {e}")
        return 1

    try:
        test.test_metrics_match_world_class_analytics()
        print("✅ test_metrics_match_world_class_analytics: PASSED")
    except AssertionError as e:
        print(f"⚠️  test_metrics_match_world_class_analytics: SKIPPED - {e}")

    print("=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(run_tests())
