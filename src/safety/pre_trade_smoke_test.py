"""
Pre-Trade Smoke Tests - Verify Alpaca connectivity before trading.

This module runs mandatory checks before any trading execution to ensure
the system can communicate with Alpaca and has valid account data.

Created: Dec 19, 2025 - Fix for ModuleNotFoundError blocking all trades
"""

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SmokeTestResult:
    """Results from pre-trade smoke tests."""

    alpaca_connected: bool = False
    account_readable: bool = False
    positions_readable: bool = False
    buying_power_valid: bool = False
    equity_valid: bool = False
    equity: float = 0.0
    buying_power: float = 0.0
    positions_count: int = 0
    all_passed: bool = False
    errors: list[str] = field(default_factory=list)


def run_smoke_tests() -> SmokeTestResult:
    """
    Run pre-trade smoke tests to verify Alpaca connectivity.

    Returns:
        SmokeTestResult with all test outcomes
    """
    result = SmokeTestResult()

    try:
        # Import Alpaca client
        from alpaca.trading.client import TradingClient

        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        paper = os.getenv("PAPER_TRADING", "true").lower() == "true"

        if not api_key or not secret_key:
            result.errors.append("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY")
            return result

        # Test 1: Can we connect to Alpaca?
        try:
            client = TradingClient(api_key, secret_key, paper=paper)
            result.alpaca_connected = True
            logger.info("Alpaca connection OK")
        except Exception as e:
            result.errors.append(f"Alpaca connection failed: {e}")
            return result

        # Test 2: Can we read account data?
        try:
            account = client.get_account()
            result.account_readable = True
            logger.info("Account readable OK")
        except Exception as e:
            result.errors.append(f"Account read failed: {e}")
            return result

        # Test 3: Can we read positions?
        try:
            positions = client.get_all_positions()
            result.positions_readable = True
            result.positions_count = len(positions)
            logger.info(f"Positions readable OK ({result.positions_count} positions)")
        except Exception as e:
            result.errors.append(f"Positions read failed: {e}")
            return result

        # Test 4: Is buying power valid?
        try:
            buying_power = float(account.buying_power)
            result.buying_power = buying_power
            result.buying_power_valid = buying_power >= 0
            if not result.buying_power_valid:
                result.errors.append(f"Invalid buying power: {buying_power}")
            else:
                logger.info(f"Buying power OK: ${buying_power:,.2f}")
        except Exception as e:
            result.errors.append(f"Buying power check failed: {e}")

        # Test 5: Is equity valid?
        try:
            equity = float(account.equity)
            result.equity = equity
            result.equity_valid = equity > 0
            if not result.equity_valid:
                result.errors.append(f"Invalid equity: {equity}")
            else:
                logger.info(f"Equity OK: ${equity:,.2f}")
        except Exception as e:
            result.errors.append(f"Equity check failed: {e}")

        # All tests passed?
        result.all_passed = (
            result.alpaca_connected
            and result.account_readable
            and result.positions_readable
            and result.buying_power_valid
            and result.equity_valid
        )

    except ImportError as e:
        result.errors.append(f"Import error: {e}")
    except Exception as e:
        result.errors.append(f"Unexpected error: {e}")
        logger.exception("Smoke test unexpected error")

    return result


if __name__ == "__main__":
    # Allow running directly for testing
    import sys

    logging.basicConfig(level=logging.INFO)
    result = run_smoke_tests()

    print("\nSMOKE TEST RESULTS:")
    print(f"  Alpaca Connected: {result.alpaca_connected}")
    print(f"  Account Readable: {result.account_readable}")
    print(f"  Positions Readable: {result.positions_readable}")
    print(f"  Buying Power Valid: {result.buying_power_valid}")
    print(f"  Equity Valid: {result.equity_valid}")
    print(f"  Equity: ${result.equity:,.2f}")
    print(f"  Buying Power: ${result.buying_power:,.2f}")
    print(f"  Positions: {result.positions_count}")
    print()

    if result.all_passed:
        print("ALL SMOKE TESTS PASSED")
        sys.exit(0)
    else:
        print(f"SMOKE TESTS FAILED: {result.errors}")
        sys.exit(1)
