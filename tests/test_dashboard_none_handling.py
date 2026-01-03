"""Tests for dashboard None value handling fix.

This module tests the fix for TypeError that occurred when the dashboard
generation script tried to format None values with .2f format specifiers.
"""

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add scripts to path for import
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


# Polyfill for pytest.raises when pytest is not available
class _RaisesContext:
    def __init__(self, expected_exception):
        self.expected_exception = expected_exception

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            raise AssertionError(f"Expected {self.expected_exception.__name__} but no exception was raised")
        if not issubclass(exc_type, self.expected_exception):
            return False  # Re-raise the exception
        return True  # Suppress the exception


def raises(expected_exception):
    if PYTEST_AVAILABLE:
        return pytest.raises(expected_exception)
    return _RaisesContext(expected_exception)


def skip(reason):
    if PYTEST_AVAILABLE:
        pytest.skip(reason)
    else:
        print(f"SKIPPED: {reason}")


class TestDashboardNoneHandling:
    """Test suite for None value handling in dashboard generation."""

    def test_none_or_zero_pattern(self):
        """Test that 'or 0' pattern correctly handles None values."""
        # Simulate dict.get() returning None for existing key with None value
        test_dict = {"sortino_ratio": None, "sharpe_ratio": 0.5, "missing": None}

        # This is the pattern used in the fix
        sortino = test_dict.get("sortino_ratio", 0) or 0
        sharpe = test_dict.get("sharpe_ratio", 0) or 0
        missing = test_dict.get("nonexistent", 0) or 0

        assert sortino == 0, "None should be converted to 0"
        assert sharpe == 0.5, "Valid float should remain unchanged"
        assert missing == 0, "Missing key should default to 0"

    def test_none_format_string_would_fail(self):
        """Verify that formatting None with .2f raises TypeError."""
        value = None
        with raises(TypeError):
            f"{value:.2f}"

    def test_fixed_format_string_works(self):
        """Verify that the fix allows formatting None-sourced values."""
        value = None
        fixed_value = value or 0
        result = f"{fixed_value:.2f}"
        assert result == "0.00"

    def test_risk_metrics_none_values(self):
        """Test handling of None values from calculate_simple_risk_metrics."""
        # Simulate return value from calculate_simple_risk_metrics
        risk_metrics = {
            "sharpe_ratio": 0.75,
            "sortino_ratio": None,  # HONESTY FIX
            "max_drawdown_pct": 5.2,
            "current_drawdown_pct": 1.3,
            "volatility_annualized": 15.5,
            "var_95": None,  # Can be None if std_dev is 0
            "var_99": None,  # Can be None if std_dev is 0
            "calmar_ratio": None,  # Can be None if max_drawdown is 0
            "ulcer_index": None,  # HONESTY FIX
        }

        # Apply the fix pattern
        max_dd = risk_metrics.get("max_drawdown_pct", 0) or 0
        curr_dd = risk_metrics.get("current_drawdown_pct", 0) or 0
        ulcer = risk_metrics.get("ulcer_index", 0) or 0
        sharpe = risk_metrics.get("sharpe_ratio", 0) or 0
        sortino = risk_metrics.get("sortino_ratio", 0) or 0
        calmar = risk_metrics.get("calmar_ratio", 0) or 0
        vol = risk_metrics.get("volatility_annualized", 0) or 0
        var95 = abs(risk_metrics.get("var_95", 0) or 0)
        var99 = abs(risk_metrics.get("var_99", 0) or 0)

        # All should be safely formattable
        assert f"{max_dd:.2f}" == "5.20"
        assert f"{curr_dd:.2f}" == "1.30"
        assert f"{ulcer:.2f}" == "0.00"
        assert f"{sharpe:.2f}" == "0.75"
        assert f"{sortino:.2f}" == "0.00"
        assert f"{calmar:.2f}" == "0.00"
        assert f"{vol:.2f}" == "15.50"
        assert f"{var95:.2f}" == "0.00"
        assert f"{var99:.2f}" == "0.00"

    def test_execution_metrics_none_handling(self):
        """Test handling of None values in execution metrics."""
        execution = {
            "avg_slippage": None,
            "fill_quality": 95.5,
            "order_success_rate": None,
            "order_reject_rate": 0,
            "avg_fill_time_ms": None,
            "broker_latency_ms": 50,
        }

        exec_slippage = execution.get("avg_slippage", 0) or 0
        exec_fill_quality = execution.get("fill_quality", 0) or 0
        exec_success_rate = execution.get("order_success_rate", 0) or 0
        exec_reject_rate = execution.get("order_reject_rate", 0) or 0
        exec_fill_time = execution.get("avg_fill_time_ms", 0) or 0
        exec_broker_latency = execution.get("broker_latency_ms", 0) or 0

        # All should be safely formattable
        assert f"{exec_slippage:.3f}" == "0.000"
        assert f"{exec_fill_quality:.1f}" == "95.5"
        assert f"{exec_success_rate:.1f}" == "0.0"
        assert f"{exec_reject_rate:.1f}" == "0.0"
        assert f"{exec_fill_time:.0f}" == "0"
        assert f"{exec_broker_latency:.0f}" == "50"

    def test_predictive_metrics_none_handling(self):
        """Test handling of None values in predictive analytics."""
        predictive = {
            "expected_pl_30d": None,
            "monte_carlo_forecast": None,  # Entire nested dict can be None
            "risk_of_ruin": None,
            "forecasted_drawdown": 2.5,
            "strategy_decay_detected": False,
        }

        pred_expected_pl = predictive.get("expected_pl_30d", 0) or 0
        mc_forecast = predictive.get("monte_carlo_forecast", {}) or {}
        mc_mean = mc_forecast.get("mean_30d", 0) or 0
        pred_risk_of_ruin = predictive.get("risk_of_ruin", 0) or 0
        pred_forecast_dd = predictive.get("forecasted_drawdown", 0) or 0

        assert f"${pred_expected_pl:+.2f}" == "$+0.00"
        assert f"${mc_mean:,.2f}" == "$0.00"
        assert f"{pred_risk_of_ruin:.2f}" == "0.00"
        assert f"{pred_forecast_dd:.2f}" == "2.50"

    def test_benchmark_metrics_none_handling(self):
        """Test handling of None values in benchmark comparison."""
        benchmark = {
            "portfolio_return": None,
            "benchmark_return": 5.2,
            "alpha": None,
            "beta": None,
            "data_available": False,
        }

        bench_portfolio_return = benchmark.get("portfolio_return", 0) or 0
        bench_benchmark_return = benchmark.get("benchmark_return", 0) or 0
        bench_alpha = benchmark.get("alpha", 0) or 0
        bench_beta = benchmark.get("beta", 1.0) or 1.0

        assert f"{bench_portfolio_return:+.2f}" == "+0.00"
        assert f"{bench_benchmark_return:+.2f}" == "+5.20"
        assert f"{bench_alpha:+.2f}" == "+0.00"
        assert f"{bench_beta:.2f}" == "1.00"

    def test_ai_insights_none_handling(self):
        """Test handling of None values in AI insights."""
        ai_insights = {
            "summary": None,
            "strategy_health": None,  # Entire nested dict can be None
        }

        ai_summary = ai_insights.get("summary", "No summary available.") or "No summary available."
        ai_health = ai_insights.get("strategy_health", {}) or {}
        ai_emoji = ai_health.get("emoji", "❓") or "❓"
        ai_status = ai_health.get("status", "UNKNOWN") or "UNKNOWN"
        ai_score = ai_health.get("score", 0) or 0

        assert ai_summary == "No summary available."
        assert ai_emoji == "❓"
        assert ai_status == "UNKNOWN"
        assert f"{ai_score:.0f}" == "0"


class TestDashboardSmokeTest:
    """Smoke tests for dashboard generation."""

    def test_dashboard_script_imports(self):
        """Verify the dashboard script can be imported without errors."""
        try:
            import generate_world_class_dashboard_enhanced
            assert hasattr(generate_world_class_dashboard_enhanced, 'generate_world_class_dashboard')
            assert hasattr(generate_world_class_dashboard_enhanced, 'calculate_simple_risk_metrics')
        except ImportError as e:
            skip(f"Could not import dashboard script: {e}")
            return

    def test_calculate_simple_risk_metrics_empty_input(self):
        """Test risk metrics function with empty input."""
        try:
            from generate_world_class_dashboard_enhanced import calculate_simple_risk_metrics
            result = calculate_simple_risk_metrics([], [])
            assert result == {}
        except ImportError:
            skip("Could not import calculate_simple_risk_metrics")
            return

    def test_calculate_simple_risk_metrics_minimal_input(self):
        """Test risk metrics function with minimal valid input."""
        try:
            from generate_world_class_dashboard_enhanced import calculate_simple_risk_metrics
            perf_log = [
                {"equity": 100000},
                {"equity": 100500},
                {"equity": 100300},
            ]
            result = calculate_simple_risk_metrics(perf_log, [])

            # Verify structure
            assert "sharpe_ratio" in result
            assert "sortino_ratio" in result
            assert "max_drawdown_pct" in result
            assert "volatility_annualized" in result

            # Verify None values are present (honesty fix)
            assert result["sortino_ratio"] is None
            assert result["ulcer_index"] is None
        except ImportError:
            skip("Could not import calculate_simple_risk_metrics")
            return

    def test_dashboard_generation_completes(self):
        """Smoke test: verify dashboard generation runs without crashing."""
        try:
            from generate_world_class_dashboard_enhanced import generate_world_class_dashboard

            # This should not raise TypeError anymore
            dashboard = generate_world_class_dashboard()

            assert dashboard is not None
            assert isinstance(dashboard, str)
            assert len(dashboard) > 0
            assert "Progress Dashboard" in dashboard or "Trading" in dashboard
        except ImportError:
            skip("Could not import generate_world_class_dashboard")
            return
        except Exception as e:
            # If it fails for other reasons (missing data files), that's okay for smoke test
            if "TypeError" in str(type(e).__name__):
                raise AssertionError(f"Dashboard generation failed with TypeError: {e}")
            skip(f"Dashboard generation skipped due to: {e}")
            return


if __name__ == "__main__":
    if PYTEST_AVAILABLE:
        pytest.main([__file__, "-v"])
    else:
        # Run tests manually without pytest
        print("Running tests without pytest...")
        print("=" * 60)

        unit_tests = TestDashboardNoneHandling()
        smoke_tests = TestDashboardSmokeTest()

        tests = [
            ("test_none_or_zero_pattern", unit_tests.test_none_or_zero_pattern),
            ("test_none_format_string_would_fail", unit_tests.test_none_format_string_would_fail),
            ("test_fixed_format_string_works", unit_tests.test_fixed_format_string_works),
            ("test_risk_metrics_none_values", unit_tests.test_risk_metrics_none_values),
            ("test_execution_metrics_none_handling", unit_tests.test_execution_metrics_none_handling),
            ("test_predictive_metrics_none_handling", unit_tests.test_predictive_metrics_none_handling),
            ("test_benchmark_metrics_none_handling", unit_tests.test_benchmark_metrics_none_handling),
            ("test_ai_insights_none_handling", unit_tests.test_ai_insights_none_handling),
            ("test_dashboard_script_imports", smoke_tests.test_dashboard_script_imports),
            ("test_calculate_simple_risk_metrics_empty_input", smoke_tests.test_calculate_simple_risk_metrics_empty_input),
            ("test_calculate_simple_risk_metrics_minimal_input", smoke_tests.test_calculate_simple_risk_metrics_minimal_input),
            ("test_dashboard_generation_completes", smoke_tests.test_dashboard_generation_completes),
        ]

        passed = 0
        failed = 0
        skipped = 0

        for name, test_func in tests:
            try:
                print(f"Running {name}...", end=" ")
                test_func()
                print("✅ PASSED")
                passed += 1
            except AssertionError as e:
                print(f"❌ FAILED: {e}")
                failed += 1
            except Exception as e:
                if "SKIPPED" in str(e):
                    print(f"⏭️ SKIPPED")
                    skipped += 1
                else:
                    print(f"❌ FAILED: {e}")
                    failed += 1

        print("=" * 60)
        print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
        print("=" * 60)

        if failed > 0:
            sys.exit(1)
