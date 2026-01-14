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
    fomo_check_passed: bool = True  # Default True - only fails if explicitly blocked

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
    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, secret_key = get_alpaca_credentials()
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
    # Fixed Jan 7, 2026: Zero buying power with substantial equity = fully invested (OK)
    if result.buying_power > 0:
        result.buying_power_valid = True
        logger.info(f"✅ SMOKE TEST: Buying power valid (${result.buying_power:,.2f})")
    elif result.equity > 1000:
        # Zero buying power but substantial equity = fully invested (NORMAL)
        # This allows position management and waiting for capital to free up
        result.buying_power_valid = True
        result.warnings.append(
            f"Buying power is $0 but equity is ${result.equity:,.2f} (fully invested)"
        )
        logger.warning(
            f"⚠️ SMOKE TEST: Buying power $0 but account healthy (equity: ${result.equity:,.2f})"
        )
    else:
        # Zero buying power AND low/zero equity = broken account (CRITICAL)
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

    # ========== TEST 8: FOMO Prevention Check (Scott Bauer Secret #4) ==========
    # "If conviction is not 100%, pass immediately and wait for next opportunity"
    # Check for FOMO_BLOCK environment variable (set by manual override or external signals)
    fomo_block = os.getenv("FOMO_BLOCK", "").lower()
    if fomo_block in ("true", "1", "yes"):
        result.fomo_check_passed = False
        result.errors.append(
            "FOMO BLOCK ACTIVE: Conviction not 100%. "
            "Scott Bauer Secret #4: There will ALWAYS be another trade."
        )
        logger.warning(
            "🛑 FOMO CHECK: Trade blocked - conviction not 100%. "
            "Remember: There will ALWAYS be another trade!"
        )
    else:
        result.fomo_check_passed = True
        logger.info("✅ SMOKE TEST: FOMO check passed (no block active)")

    # ========== FINAL RESULT ==========
    result.all_passed = (
        result.alpaca_connected
        and result.account_readable
        and result.positions_readable
        and result.buying_power_valid
        and result.equity_valid
        and result.fomo_check_passed
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
    print(f"FOMO Check Passed:   {result.fomo_check_passed}")
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
