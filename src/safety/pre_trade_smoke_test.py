"""
PRE-TRADE SMOKE TESTS - MANDATORY before ANY trading

This module MUST pass before a single dollar is traded.
If ANY test fails, trading is BLOCKED.

Created: Dec 17, 2025
Purpose: Prevent catastrophic operational failures like blind trading

NEVER SKIP THESE TESTS. They exist because we lost money due to broken connections.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SmokeTestResult:
    """Result of pre-trade smoke tests."""
    
    all_passed: bool = False
    alpaca_connected: bool = False
    account_readable: bool = False
    positions_readable: bool = False
    buying_power_valid: bool = False
    equity_valid: bool = False
    
    # Values retrieved
    equity: float = 0.0
    buying_power: float = 0.0
    cash: float = 0.0
    positions_count: int = 0
    
    # Errors
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    timestamp: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "alpaca_connected": self.alpaca_connected,
            "account_readable": self.account_readable,
            "positions_readable": self.positions_readable,
            "buying_power_valid": self.buying_power_valid,
            "equity_valid": self.equity_valid,
            "equity": self.equity,
            "buying_power": self.buying_power,
            "cash": self.cash,
            "positions_count": self.positions_count,
            "errors": self.errors,
            "warnings": self.warnings,
            "timestamp": self.timestamp,
        }


class PreTradeSmokeTest:
    """
    MANDATORY smoke tests before trading.
    
    These tests verify:
    1. Alpaca API is reachable
    2. We can read account info (equity, buying power, cash)
    3. We can read positions
    4. Buying power > 0 (we have money to trade)
    5. Equity is reasonable (not $0, not negative)
    
    If ANY test fails, trading MUST be blocked.
    """
    
    def __init__(self):
        self.result = SmokeTestResult()
        self.result.timestamp = datetime.now(timezone.utc).isoformat()
        
    def test_alpaca_connection(self) -> bool:
        """Test 1: Can we connect to Alpaca at all?"""
        try:
            from alpaca.trading.client import TradingClient
            
            api_key = os.getenv("ALPACA_API_KEY")
            secret_key = os.getenv("ALPACA_SECRET_KEY")
            
            if not api_key or not secret_key:
                self.result.errors.append("ALPACA_API_KEY or ALPACA_SECRET_KEY not set")
                return False
            
            # Try to create client
            paper = os.getenv("ALPACA_PAPER", "true").lower() in {"1", "true", "yes"}
            client = TradingClient(api_key, secret_key, paper=paper)
            
            # Store for later tests
            self._client = client
            self.result.alpaca_connected = True
            logger.info("✅ Smoke Test 1: Alpaca connection successful")
            return True
            
        except Exception as e:
            self.result.errors.append(f"Alpaca connection failed: {e}")
            logger.error(f"❌ Smoke Test 1 FAILED: {e}")
            return False
    
    def test_account_readable(self) -> bool:
        """Test 2: Can we read account info?"""
        if not hasattr(self, "_client"):
            self.result.errors.append("Cannot test account - no Alpaca connection")
            return False
            
        try:
            account = self._client.get_account()
            
            # Extract values
            self.result.equity = float(account.equity)
            self.result.buying_power = float(account.buying_power)
            self.result.cash = float(account.cash)
            
            self.result.account_readable = True
            logger.info(f"✅ Smoke Test 2: Account readable - Equity: ${self.result.equity:,.2f}")
            return True
            
        except Exception as e:
            self.result.errors.append(f"Account read failed: {e}")
            logger.error(f"❌ Smoke Test 2 FAILED: {e}")
            return False
    
    def test_positions_readable(self) -> bool:
        """Test 3: Can we read positions?"""
        if not hasattr(self, "_client"):
            self.result.errors.append("Cannot test positions - no Alpaca connection")
            return False
            
        try:
            positions = self._client.get_all_positions()
            self.result.positions_count = len(positions)
            
            self.result.positions_readable = True
            logger.info(f"✅ Smoke Test 3: Positions readable - {self.result.positions_count} positions")
            return True
            
        except Exception as e:
            self.result.errors.append(f"Positions read failed: {e}")
            logger.error(f"❌ Smoke Test 3 FAILED: {e}")
            return False
    
    def test_buying_power_valid(self) -> bool:
        """Test 4: Do we have buying power > 0?"""
        if not self.result.account_readable:
            self.result.errors.append("Cannot validate buying power - account not readable")
            return False
        
        if self.result.buying_power <= 0:
            self.result.errors.append(f"Buying power is ${self.result.buying_power} - cannot trade!")
            logger.error(f"❌ Smoke Test 4 FAILED: Buying power is ${self.result.buying_power}")
            return False
        
        # Warning if buying power is suspiciously low
        if self.result.buying_power < 100:
            self.result.warnings.append(f"Buying power is only ${self.result.buying_power:.2f}")
        
        self.result.buying_power_valid = True
        logger.info(f"✅ Smoke Test 4: Buying power valid - ${self.result.buying_power:,.2f}")
        return True
    
    def test_equity_valid(self) -> bool:
        """Test 5: Is equity reasonable (not $0, not negative)?"""
        if not self.result.account_readable:
            self.result.errors.append("Cannot validate equity - account not readable")
            return False
        
        if self.result.equity <= 0:
            self.result.errors.append(f"Equity is ${self.result.equity} - something is very wrong!")
            logger.error(f"❌ Smoke Test 5 FAILED: Equity is ${self.result.equity}")
            return False
        
        # Warning if equity dropped significantly from $100k starting balance
        if self.result.equity < 90000:
            self.result.warnings.append(f"Equity dropped to ${self.result.equity:,.2f} (>10% loss)")
        
        self.result.equity_valid = True
        logger.info(f"✅ Smoke Test 5: Equity valid - ${self.result.equity:,.2f}")
        return True
    
    def run_all_tests(self) -> SmokeTestResult:
        """
        Run ALL smoke tests.
        
        Returns SmokeTestResult with all_passed = True only if EVERY test passes.
        """
        logger.info("=" * 60)
        logger.info("🔥 RUNNING PRE-TRADE SMOKE TESTS")
        logger.info("=" * 60)
        
        # Run tests in order - some depend on previous ones
        tests = [
            ("Alpaca Connection", self.test_alpaca_connection),
            ("Account Readable", self.test_account_readable),
            ("Positions Readable", self.test_positions_readable),
            ("Buying Power Valid", self.test_buying_power_valid),
            ("Equity Valid", self.test_equity_valid),
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            try:
                passed = test_func()
                if not passed:
                    all_passed = False
            except Exception as e:
                self.result.errors.append(f"{test_name} exception: {e}")
                all_passed = False
                logger.error(f"❌ {test_name} EXCEPTION: {e}")
        
        self.result.all_passed = all_passed
        
        logger.info("=" * 60)
        if all_passed:
            logger.info("✅ ALL SMOKE TESTS PASSED - Trading can proceed")
        else:
            logger.error("❌ SMOKE TESTS FAILED - TRADING BLOCKED")
            logger.error(f"   Errors: {self.result.errors}")
        logger.info("=" * 60)
        
        return self.result


class TradingBlockedError(Exception):
    """Raised when trading is blocked due to failed smoke tests."""
    
    def __init__(self, result: SmokeTestResult):
        self.result = result
        super().__init__(f"Trading blocked: {result.errors}")


def run_smoke_tests() -> SmokeTestResult:
    """Run smoke tests and return result."""
    tester = PreTradeSmokeTest()
    return tester.run_all_tests()


def require_smoke_tests_pass() -> SmokeTestResult:
    """
    Run smoke tests and RAISE EXCEPTION if any fail.
    
    Call this before ANY trading to ensure system is operational.
    
    Raises:
        TradingBlockedError: If any smoke test fails
    """
    result = run_smoke_tests()
    
    if not result.all_passed:
        raise TradingBlockedError(result)
    
    return result


if __name__ == "__main__":
    # Run smoke tests directly
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    result = run_smoke_tests()
    
    print("\n" + "=" * 60)
    print("SMOKE TEST SUMMARY")
    print("=" * 60)
    print(f"All Passed: {'✅ YES' if result.all_passed else '❌ NO'}")
    print(f"Alpaca Connected: {result.alpaca_connected}")
    print(f"Account Readable: {result.account_readable}")
    print(f"Positions Readable: {result.positions_readable}")
    print(f"Buying Power Valid: {result.buying_power_valid}")
    print(f"Equity Valid: {result.equity_valid}")
    print()
    print(f"Equity: ${result.equity:,.2f}")
    print(f"Buying Power: ${result.buying_power:,.2f}")
    print(f"Cash: ${result.cash:,.2f}")
    print(f"Positions: {result.positions_count}")
    
    if result.errors:
        print(f"\n❌ ERRORS:")
        for err in result.errors:
            print(f"   - {err}")
    
    if result.warnings:
        print(f"\n⚠️ WARNINGS:")
        for warn in result.warnings:
            print(f"   - {warn}")
    
    sys.exit(0 if result.all_passed else 1)
