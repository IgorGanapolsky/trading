#!/usr/bin/env python3
"""
Trading System Validation Test Script

This script validates that all critical components of the trading system are functional.
Run this after fixing dependencies to ensure the system is ready for operation.

Exit Codes:
    0: All tests passed
    1: One or more tests failed

Usage:
    python test_system.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Test results tracker
test_results = []


def print_header(text):
    """Print a formatted header."""
    print(f"\n{'=' * 80}")
    print(f"  {text}")
    print(f"{'=' * 80}\n")


def print_test(name, passed, details=""):
    """Print test result with formatting."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {name}")
    if details:
        print(f"       {details}")
    test_results.append((name, passed, details))
    return passed


def test_imports():
    """Test 1: Validate all critical module imports."""
    print_header("TEST 1: Module Imports")

    all_passed = True

    # Test standard library imports
    try:
        import dataclasses  # noqa: F401 - testing importability
        import enum  # noqa: F401 - testing importability
        import logging  # noqa: F401 - testing importability
        import typing  # noqa: F401 - testing importability

        print_test("Standard library imports", True, "logging, typing, dataclasses, enum")
    except ImportError as e:
        print_test("Standard library imports", False, str(e))
        all_passed = False

    # Test third-party dependencies
    dependencies = [
        ("pandas", "pandas"),
        ("numpy", "numpy"),
        ("yfinance", "yfinance"),
        ("python-dotenv", "dotenv"),
        ("alpaca-trade-api", "alpaca_trade_api"),
    ]

    for package_name, import_name in dependencies:
        try:
            __import__(import_name)
            print_test(f"{package_name} import", True, f"import {import_name}")
        except ImportError as e:
            print_test(f"{package_name} import", False, str(e))
            all_passed = False

    # Test project module imports
    project_modules = [
        ("src.core.alpaca_trader", "AlpacaTrader"),
        ("src.core.risk_manager", "RiskManager"),
        ("src.core.multi_llm_analysis", "MultiLLMAnalyzer"),
        ("src.strategies.core_strategy", "CoreStrategy"),
    ]

    for module_path, class_name in project_modules:
        try:
            module = __import__(module_path, fromlist=[class_name])
            getattr(module, class_name)
            print_test(f"{module_path}.{class_name}", True)
        except ImportError as e:
            print_test(f"{module_path}.{class_name}", False, str(e))
            all_passed = False
        except AttributeError as e:
            print_test(f"{module_path}.{class_name}", False, f"Class not found: {e}")
            all_passed = False

    return all_passed


def test_environment():
    """Test 2: Validate environment variables."""
    print_header("TEST 2: Environment Variables")

    from dotenv import load_dotenv

    # Load .env file
    env_file = Path("/home/user/trading/.env")
    if env_file.exists():
        load_dotenv(env_file)
        print_test(".env file exists", True, str(env_file))
    else:
        print_test(".env file exists", False, f"Not found: {env_file}")
        return False

    # Check required environment variables
    required_vars = {
        "ALPACA_API_KEY": "Alpaca API key",
        "ALPACA_SECRET_KEY": "Alpaca secret key",
        "PAPER_TRADING": "Paper trading flag",
        "DAILY_INVESTMENT": "Daily investment amount",
    }

    all_passed = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if "KEY" in var or "SECRET" in var:
                display_value = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
            else:
                display_value = value
            print_test(f"Environment: {var}", True, display_value)
        else:
            print_test(f"Environment: {var}", False, f"{description} not set")
            all_passed = False

    return all_passed


def test_file_structure():
    """Test 3: Validate required file paths exist."""
    print_header("TEST 3: File Structure")

    base_dir = Path("/home/user/trading")
    required_paths = {
        "src/": "Source code directory",
        "src/core/": "Core modules directory",
        "src/strategies/": "Strategies directory",
        "data/": "Data directory",
        "reports/": "Reports directory",
        "logs/": "Logs directory (will be created)",
        "data/system_state.json": "System state file",
        ".env": "Environment configuration",
    }

    all_passed = True
    for path, description in required_paths.items():
        full_path = base_dir / path
        exists = full_path.exists()

        # Create logs directory if it doesn't exist
        if path == "logs/" and not exists:
            full_path.mkdir(parents=True, exist_ok=True)
            exists = True

        print_test(f"Path: {path}", exists, description)
        if not exists:
            all_passed = False

    return all_passed


def test_alpaca_connection():
    """Test 4: Validate Alpaca API connection (paper trading)."""
    print_header("TEST 4: Alpaca API Connection")

    try:
        from dotenv import load_dotenv
        from src.core.alpaca_trader import AlpacaTrader

        load_dotenv("/home/user/trading/.env")

        # Initialize trader in paper mode
        trader = AlpacaTrader(paper=True)
        print_test("AlpacaTrader initialization", True, "Paper trading mode")

        # Test account info retrieval
        try:
            account = trader.get_account_info()
            print_test(
                "Account info retrieval",
                True,
                f"Equity: ${account.get('equity', 0):,.2f}, Cash: ${account.get('cash', 0):,.2f}",
            )
            return True
        except Exception as e:
            print_test("Account info retrieval", False, str(e))
            return False

    except Exception as e:
        print_test("AlpacaTrader initialization", False, str(e))
        return False


def test_core_strategy():
    """Test 5: Validate CoreStrategy initialization."""
    print_header("TEST 5: CoreStrategy Initialization")

    try:
        from dotenv import load_dotenv
        from src.core.alpaca_trader import AlpacaTrader
        from src.core.risk_manager import RiskManager
        from src.strategies.core_strategy import CoreStrategy

        load_dotenv("/home/user/trading/.env")

        # Initialize dependencies
        trader = AlpacaTrader(paper=True)
        risk_manager = RiskManager(trader)

        print_test("Dependencies initialized", True, "AlpacaTrader + RiskManager")

        # Initialize CoreStrategy (without sentiment to avoid API costs)
        strategy = CoreStrategy(
            trader=trader,
            risk_manager=risk_manager,
            daily_amount=6.0,
            use_sentiment=False,  # Disable AI calls for testing
        )

        print_test("CoreStrategy initialization", True, "Daily amount: $6.00, Sentiment: OFF")

        # Test ETF list
        if strategy.etf_universe:
            print_test(
                "ETF universe loaded",
                True,
                f"{len(strategy.etf_universe)} ETFs: {', '.join(strategy.etf_universe)}",
            )
        else:
            print_test("ETF universe loaded", False, "No ETFs configured")
            return False

        return True

    except Exception as e:
        print_test("CoreStrategy initialization", False, str(e))
        return False


def test_simulated_trade():
    """Test 6: Simulate trade execution (dry run)."""
    print_header("TEST 6: Simulated Trade Execution")

    try:
        from dotenv import load_dotenv
        from src.core.alpaca_trader import AlpacaTrader
        from src.core.risk_manager import RiskManager
        from src.strategies.core_strategy import CoreStrategy

        load_dotenv("/home/user/trading/.env")

        # Initialize components
        trader = AlpacaTrader(paper=True)
        risk_manager = RiskManager(trader)
        strategy = CoreStrategy(trader, risk_manager, daily_amount=6.0, use_sentiment=False)

        print_test("Strategy components ready", True, "Trader + RiskManager + CoreStrategy")

        # Get ETF prices (this validates yfinance works)
        try:
            import yfinance as yf

            spy = yf.Ticker("SPY")
            price = spy.history(period="1d")["Close"].iloc[-1]
            print_test("Market data retrieval", True, f"SPY current price: ${price:.2f}")
        except Exception as e:
            print_test("Market data retrieval", False, str(e))
            return False

        # Calculate momentum scores (validates strategy logic)
        try:
            momentum_scores = strategy._calculate_momentum_scores(use_sentiment=False)
            if momentum_scores:
                best_etf = max(momentum_scores, key=momentum_scores.get)
                best_score = momentum_scores[best_etf]
                print_test(
                    "Momentum calculation", True, f"Best ETF: {best_etf} (score: {best_score:.4f})"
                )
            else:
                print_test("Momentum calculation", False, "No momentum scores calculated")
                return False
        except Exception as e:
            print_test("Momentum calculation", False, str(e))
            return False

        # Note: We don't actually execute a trade to avoid hitting the API
        print_test("Trade simulation", True, "Dry run successful (no actual order placed)")

        return True

    except Exception as e:
        print_test("Trade simulation", False, str(e))
        return False


def test_state_persistence():
    """Test 7: Validate state persistence works."""
    print_header("TEST 7: State Persistence")

    state_file = Path("/home/user/trading/data/system_state.json")

    # Check if state file exists
    if not state_file.exists():
        print_test("System state file exists", False, f"Not found: {state_file}")
        return False

    print_test("System state file exists", True, str(state_file))

    # Try to read and parse state file
    try:
        with open(state_file) as f:
            state = json.load(f)

        print_test("State file readable", True, "Valid JSON format")

        # Validate key sections exist
        required_sections = ["meta", "challenge", "account", "investments", "performance"]
        all_sections_present = True

        for section in required_sections:
            if section in state:
                print_test(f"State section: {section}", True, f"Keys: {len(state[section])}")
            else:
                print_test(f"State section: {section}", False, "Section missing")
                all_sections_present = False

        # Test write capability (create backup first)
        try:
            backup_file = state_file.with_suffix(".json.bak")
            with open(backup_file, "w") as f:
                json.dump(state, f, indent=2)

            print_test("State file writable", True, f"Backup created: {backup_file.name}")

            # Clean up backup
            backup_file.unlink()

        except Exception as e:
            print_test("State file writable", False, str(e))
            return False

        return all_sections_present

    except json.JSONDecodeError as e:
        print_test("State file readable", False, f"Invalid JSON: {e}")
        return False
    except Exception as e:
        print_test("State file readable", False, str(e))
        return False


def generate_summary():
    """Generate test summary."""
    print_header("TEST SUMMARY")

    total_tests = len(test_results)
    passed_tests = sum(1 for _, passed, _ in test_results if passed)
    failed_tests = total_tests - passed_tests

    print(f"Total Tests:  {total_tests}")
    print(f"Passed:       {passed_tests} ✅")
    print(f"Failed:       {failed_tests} ❌")
    print(f"Success Rate: {(passed_tests / total_tests) * 100:.1f}%")

    if failed_tests > 0:
        print("\n" + "=" * 80)
        print("FAILED TESTS:")
        print("=" * 80)
        for name, passed, details in test_results:
            if not passed:
                print(f"\n❌ {name}")
                if details:
                    print(f"   Error: {details}")

    return failed_tests == 0


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("  TRADING SYSTEM VALIDATION TEST")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Run all tests
    tests = [
        test_imports,
        test_environment,
        test_file_structure,
        test_alpaca_connection,
        test_core_strategy,
        test_simulated_trade,
        test_state_persistence,
    ]

    try:
        for test_func in tests:
            test_func()
            print()  # Add spacing between test groups

        # Generate summary
        all_passed = generate_summary()

        # Final verdict
        print("\n" + "=" * 80)
        if all_passed:
            print("✅ ALL TESTS PASSED - System is ready for operation!")
            print("=" * 80 + "\n")
            return 0
        else:
            print("❌ SOME TESTS FAILED - Please fix errors before proceeding")
            print("=" * 80 + "\n")
            return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ FATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
