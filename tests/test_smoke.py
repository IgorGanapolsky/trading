#!/usr/bin/env python3
"""
Smoke Tests - Quick Critical Path Verification

These tests verify the system is fundamentally working:
- Fast execution (< 30 seconds)
- No external API calls (or mocked)
- Critical paths only
- Catches major breakages before they reach production

Run before commits, deployments, or when you need quick confidence.
"""

import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def assert_condition(condition, message):
    """Simple assertion helper."""
    if not condition:
        raise AssertionError(message)


class SmokeTests:
    """Quick smoke tests for critical functionality."""

    def test_imports(self):
        """Test that critical modules can be imported."""
        try:
            # Import and verify modules are accessible
            from scripts.dashboard_metrics import TradingMetricsCalculator  # noqa: F401
            from scripts.enhanced_dashboard_metrics import (  # noqa: F401
                EnhancedMetricsCalculator,
            )
            from scripts.generate_world_class_dashboard_enhanced import (  # noqa: F401
                generate_world_class_dashboard,
            )

            return True, "All critical imports successful"
        except ImportError as e:
            return False, f"Import failed: {e}"

    def test_dashboard_metrics_calculation(self):
        """Test that dashboard metrics can be calculated."""
        try:
            from scripts.dashboard_metrics import TradingMetricsCalculator

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

            calculator = TradingMetricsCalculator()
            risk_metrics = calculator._calculate_risk_metrics(
                perf_log, base_equity, perf_log[-1]["equity"]
            )

            # Verify required metrics exist
            required = [
                "max_drawdown_pct",
                "sharpe_ratio",
                "var_95",
                "var_99",
                "cvar_95",
                "ulcer_index",
                "calmar_ratio",
            ]

            missing = [m for m in required if m not in risk_metrics]
            if missing:
                return False, f"Missing metrics: {missing}"

            return True, "Dashboard metrics calculated successfully"
        except Exception as e:
            return False, f"Dashboard metrics calculation failed: {e}"

    def test_dashboard_generation(self):
        """Test that dashboard can be generated without errors."""
        try:
            from scripts.enhanced_dashboard_metrics import EnhancedMetricsCalculator

            # Create temp data directory with minimal valid data
            with tempfile.TemporaryDirectory() as tmpdir:
                data_dir = Path(tmpdir)

                # Create minimal performance log
                perf_log = []
                base_equity = 100000.0
                for i in range(3):
                    equity = base_equity + (i * 50)
                    perf_log.append(
                        {
                            "date": (date.today() - timedelta(days=3 - i)).isoformat(),
                            "equity": equity,
                            "pl": equity - base_equity,
                            "pl_pct": (equity - base_equity) / base_equity,
                        }
                    )

                perf_file = data_dir / "performance_log.json"
                with open(perf_file, "w") as f:
                    json.dump(perf_log, f)

                # Create minimal system_state.json
                system_state_file = data_dir / "system_state.json"
                with open(system_state_file, "w") as f:
                    json.dump(
                        {
                            "account": {
                                "current_equity": perf_log[-1]["equity"],
                                "starting_balance": base_equity,
                            },
                            "performance": {"closed_trades": [], "open_positions": []},
                            "challenge": {"current_day": 1, "total_days": 90},
                        },
                        f,
                    )

                calculator = EnhancedMetricsCalculator(data_dir)
                all_metrics = calculator.calculate_all_metrics()

                # Verify metrics structure
                if "risk_metrics" not in all_metrics:
                    return False, "Missing risk_metrics in all_metrics"

                if "performance_metrics" not in all_metrics:
                    return False, "Missing performance_metrics in all_metrics"

                return True, "Dashboard generation successful"
        except Exception as e:
            return False, f"Dashboard generation failed: {e}"

    def test_data_structures(self):
        """Test that data structures are valid."""
        try:
            # Test JSON loading
            from scripts.dashboard_metrics import load_json_file

            # Test with non-existent file (should return empty dict/list)
            result = load_json_file(Path("/nonexistent/file.json"))
            if not isinstance(result, dict):
                return False, "load_json_file should return dict for .json files"

            # Test with temp file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump({"test": "data"}, f)
                temp_path = Path(f.name)

            try:
                result = load_json_file(temp_path)
                if result.get("test") != "data":
                    return False, "load_json_file not loading data correctly"
            finally:
                temp_path.unlink()

            return True, "Data structures valid"
        except Exception as e:
            return False, f"Data structure test failed: {e}"

    def test_risk_metrics_completeness(self):
        """Quick test that all risk metrics are calculated."""
        try:
            from scripts.dashboard_metrics import TradingMetricsCalculator

            # Create equity curve with variation
            perf_log = []
            base_equity = 100000.0
            equities = [100000, 101000, 100500, 99000, 99500, 101000]

            for i, equity in enumerate(equities):
                perf_log.append(
                    {
                        "date": (date.today() - timedelta(days=len(equities) - i)).isoformat(),
                        "equity": float(equity),
                    }
                )

            calculator = TradingMetricsCalculator()
            risk_metrics = calculator._calculate_risk_metrics(
                perf_log, base_equity, perf_log[-1]["equity"]
            )

            # Verify all required metrics exist
            required_metrics = [
                "max_drawdown_pct",
                "sharpe_ratio",
                "sortino_ratio",
                "volatility_annualized",
                "var_95",
                "var_99",
                "cvar_95",
                "ulcer_index",
                "calmar_ratio",
            ]

            missing = [m for m in required_metrics if m not in risk_metrics]
            if missing:
                return False, f"Missing required metrics: {missing}"

            # Verify metrics are not all zeros (with this data)
            if risk_metrics["max_drawdown_pct"] == 0.0:
                return False, "Max drawdown should be > 0 with this data"

            return True, "Risk metrics completeness verified"
        except Exception as e:
            return False, f"Risk metrics completeness test failed: {e}"

    def test_no_critical_errors(self):
        """Test that no critical errors occur during basic operations."""
        try:
            # Test that calculators can be instantiated
            from scripts.dashboard_metrics import TradingMetricsCalculator
            from scripts.enhanced_dashboard_metrics import EnhancedMetricsCalculator

            calc1 = TradingMetricsCalculator()
            calc2 = EnhancedMetricsCalculator()

            # Test that methods exist
            assert hasattr(calc1, "_calculate_risk_metrics")
            assert hasattr(calc2, "calculate_all_metrics")

            return True, "No critical errors detected"
        except Exception as e:
            return False, f"Critical error detected: {e}"

    def test_crypto_trade_verification(self):
        """Test that crypto trade verification module works."""
        try:
            from tests.test_crypto_trade_verification import (
                CryptoTradeVerificationTests,
            )

            tester = CryptoTradeVerificationTests()
            results = tester.run_all_tests()

            # At minimum, state file should exist and be valid
            if results["failed"] > 0:
                # Check if failures are just missing dependencies or credentials (OK in CI)
                critical_failures = [
                    d
                    for d in results["details"]
                    if d["status"] == "❌"
                    and "not installed" not in d["message"]
                    and "not available" not in d["message"]
                    and "not set" not in d["message"]  # Skip API key failures in CI
                ]
                if critical_failures:
                    return (
                        False,
                        f"Crypto verification failed: {critical_failures[0]['message']}",
                    )

            return (
                True,
                f"Crypto verification tests passed ({results['passed']}/{len(results['details'])})",
            )
        except ImportError as e:
            return False, f"Crypto verification module import failed: {e}"
        except Exception as e:
            return False, f"Crypto verification test failed: {e}"

    def run_all(self):
        """Run all smoke tests."""
        tests = [
            ("Imports", self.test_imports),
            ("Dashboard Metrics Calculation", self.test_dashboard_metrics_calculation),
            ("Dashboard Generation", self.test_dashboard_generation),
            ("Data Structures", self.test_data_structures),
            ("Risk Metrics Completeness", self.test_risk_metrics_completeness),
            ("No Critical Errors", self.test_no_critical_errors),
            ("Crypto Trade Verification", self.test_crypto_trade_verification),
        ]

        results = []
        for test_name, test_func in tests:
            try:
                passed, message = test_func()
                results.append((test_name, passed, message))
            except Exception as e:
                results.append((test_name, False, f"Test exception: {e}"))

        return results


def main():
    """Run smoke tests."""
    print("=" * 70)
    print("SMOKE TESTS - Quick Critical Path Verification")
    print("=" * 70)
    print()

    smoke = SmokeTests()
    results = smoke.run_all()

    passed = 0
    failed = 0

    for test_name, passed_test, message in results:
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status} {test_name}")
        if not passed_test:
            print(f"   └─ {message}")
        if passed_test:
            passed += 1
        else:
            failed += 1

    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed == 0:
        print("\n✅ ALL SMOKE TESTS PASSED - System is fundamentally working!")
        return 0
    else:
        print(f"\n❌ {failed} SMOKE TEST(S) FAILED - Review before proceeding")
        return 1


if __name__ == "__main__":
    sys.exit(main())
