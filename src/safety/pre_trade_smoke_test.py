"""Pre-trade smoke tests to validate system health before trading.

CRITICAL: These tests MUST actually connect to Alpaca and validate.
If ANY test fails, trading MUST be blocked.

Fixed Dec 30, 2025 - Previous version was a stub that always returned True.
"""

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SmokeTestResult:
    """Result of smoke test execution."""

    # Individual test results - default to FALSE (fail-safe)
    alpaca_connected: bool = False
    account_readable: bool = False
    positions_readable: bool = False
    buying_power_valid: bool = False
    equity_valid: bool = False

    # Aggregate result
    all_passed: bool = False
    passed: bool = False  # Alias for backwards compatibility

    # Actual values from Alpaca
    buying_power: float = 0.0
    equity: float = 0.0
    positions_count: int = 0
    cash: float = 0.0

    # Error tracking
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def run_smoke_tests() -> SmokeTestResult:
    """Run REAL pre-trade smoke tests against Alpaca.

    This function MUST:
    1. Actually connect to Alpaca API
    2. Verify account is accessible
    3. Verify positions are readable
    4. Verify buying power > 0
    5. Verify equity > 0

    Returns:
        SmokeTestResult with all_passed=True ONLY if ALL tests pass.
    """
    result = SmokeTestResult()

    # ========== TEST 1: Environment Variables ==========
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    paper = os.getenv("PAPER_TRADING", "true").lower() == "true"

    if not api_key:
        result.errors.append("CRITICAL: ALPACA_API_KEY not set")
        logger.error("SMOKE TEST FAILED: ALPACA_API_KEY not set")
        return result

    if not secret_key:
        result.errors.append("CRITICAL: ALPACA_SECRET_KEY not set")
        logger.error("SMOKE TEST FAILED: ALPACA_SECRET_KEY not set")
        return result

    # ========== TEST 2: Alpaca Connection ==========
    try:
        from alpaca.trading.client import TradingClient

        client = TradingClient(api_key, secret_key, paper=paper)
        result.alpaca_connected = True
        logger.info("✅ SMOKE TEST: Alpaca connection successful")
    except ImportError as e:
        result.errors.append(f"CRITICAL: alpaca-py not installed: {e}")
        logger.error("SMOKE TEST FAILED: alpaca-py not installed")
        return result
    except Exception as e:
        result.errors.append(f"CRITICAL: Alpaca connection failed: {e}")
        logger.error(f"SMOKE TEST FAILED: Alpaca connection failed: {e}")
        return result

    # ========== TEST 3: Account Readable ==========
    try:
        account = client.get_account()
        result.account_readable = True
        logger.info("✅ SMOKE TEST: Account readable")

        # Extract account values
        result.equity = float(account.equity)
        result.buying_power = float(account.buying_power)
        result.cash = float(account.cash)

        logger.info(f"   Equity: ${result.equity:,.2f}")
        logger.info(f"   Buying Power: ${result.buying_power:,.2f}")
        logger.info(f"   Cash: ${result.cash:,.2f}")

    except Exception as e:
        result.errors.append(f"CRITICAL: Cannot read account: {e}")
        logger.error(f"SMOKE TEST FAILED: Cannot read account: {e}")
        return result

    # ========== TEST 4: Account Status Check ==========
    try:
        status = account.status
        if status != "ACTIVE":
            result.errors.append(f"CRITICAL: Account status is {status}, not ACTIVE")
            logger.error(f"SMOKE TEST FAILED: Account status is {status}")
            return result
        logger.info("✅ SMOKE TEST: Account status is ACTIVE")
    except Exception as e:
        result.warnings.append(f"Could not check account status: {e}")

    # ========== TEST 5: Positions Readable ==========
    try:
        positions = client.get_all_positions()
        result.positions_readable = True
        result.positions_count = len(positions)
        logger.info(f"✅ SMOKE TEST: Positions readable ({result.positions_count} positions)")
    except Exception as e:
        result.errors.append(f"CRITICAL: Cannot read positions: {e}")
        logger.error(f"SMOKE TEST FAILED: Cannot read positions: {e}")
        return result

    # ========== TEST 6: Buying Power Valid ==========
    if result.buying_power > 0:
        result.buying_power_valid = True
        logger.info(f"✅ SMOKE TEST: Buying power valid (${result.buying_power:,.2f})")
    else:
        result.errors.append(f"CRITICAL: Buying power is ${result.buying_power} (must be > 0)")
        logger.error(f"SMOKE TEST FAILED: Buying power is ${result.buying_power}")
        # Don't return - continue to check equity

    # ========== TEST 7: Equity Valid ==========
    if result.equity > 0:
        result.equity_valid = True
        logger.info(f"✅ SMOKE TEST: Equity valid (${result.equity:,.2f})")
    else:
        result.errors.append(f"CRITICAL: Equity is ${result.equity} (must be > 0)")
        logger.error(f"SMOKE TEST FAILED: Equity is ${result.equity}")

    # ========== FINAL RESULT ==========
    result.all_passed = (
        result.alpaca_connected
        and result.account_readable
        and result.positions_readable
        and result.buying_power_valid
        and result.equity_valid
    )
    result.passed = result.all_passed  # Backwards compatibility

    if result.all_passed:
        logger.info("=" * 50)
        logger.info("✅ ALL SMOKE TESTS PASSED - Trading can proceed")
        logger.info("=" * 50)
    else:
        logger.error("=" * 50)
        logger.error("❌ SMOKE TESTS FAILED - Trading BLOCKED")
        logger.error(f"   Errors: {result.errors}")
        logger.error("=" * 50)

    return result


def block_trading_on_failure() -> bool:
    """Run smoke tests and return True if trading should be blocked.

    Returns:
        True if trading should be BLOCKED (tests failed)
        False if trading can proceed (tests passed)
    """
    result = run_smoke_tests()
    return not result.all_passed


if __name__ == "__main__":
    # Allow running directly for testing
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    result = run_smoke_tests()

    print("\n" + "=" * 60)
    print("SMOKE TEST SUMMARY")
    print("=" * 60)
    print(f"Alpaca Connected:    {result.alpaca_connected}")
    print(f"Account Readable:    {result.account_readable}")
    print(f"Positions Readable:  {result.positions_readable}")
    print(f"Buying Power Valid:  {result.buying_power_valid}")
    print(f"Equity Valid:        {result.equity_valid}")
    print("-" * 60)
    print(f"Equity:              ${result.equity:,.2f}")
    print(f"Buying Power:        ${result.buying_power:,.2f}")
    print(f"Cash:                ${result.cash:,.2f}")
    print(f"Positions:           {result.positions_count}")
    print("-" * 60)
    print(f"ALL PASSED:          {result.all_passed}")
    print("=" * 60)

    if result.errors:
        print("\nERRORS:")
        for error in result.errors:
            print(f"  ❌ {error}")

    if result.warnings:
        print("\nWARNINGS:")
        for warning in result.warnings:
            print(f"  ⚠️ {warning}")

    sys.exit(0 if result.all_passed else 1)
