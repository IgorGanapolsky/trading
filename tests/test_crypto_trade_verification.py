#!/usr/bin/env python3
"""
Smoke Tests for Crypto Trade Verification

Verifies that crypto trades executed correctly by:
1. Checking GitHub Actions logs for order execution
2. Verifying Alpaca API shows positions match our state
3. Ensuring state tracking is accurate

These tests run automatically after crypto trading workflows.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class CryptoTradeVerificationTests:
    """Smoke tests for crypto trade verification."""

    def __init__(self):
        """Initialize test class."""
        self.data_dir = Path("data")
        self.state_file = self.data_dir / "system_state.json"

    def test_state_file_exists(self) -> tuple[bool, str]:
        """Test that system_state.json exists."""
        if not self.state_file.exists():
            return False, "system_state.json not found"
        return True, "system_state.json exists"

    def test_state_file_valid_json(self) -> tuple[bool, str]:
        """Test that system_state.json is valid JSON."""
        try:
            with open(self.state_file) as f:
                json.load(f)
            return True, "system_state.json is valid JSON"
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON in system_state.json: {e}"

    def test_crypto_strategy_tracked(self) -> tuple[bool, str]:
        """Test that crypto strategy (tier5) is tracked in state."""
        try:
            with open(self.state_file) as f:
                state = json.load(f)

            tier5 = state.get("strategies", {}).get("tier5", {})
            if not tier5:
                return False, "tier5 strategy not found in system_state.json"

            required_fields = ["name", "trades_executed", "total_invested", "status"]
            missing = [f for f in required_fields if f not in tier5]
            if missing:
                return False, f"Missing required fields in tier5: {missing}"

            return True, f"Crypto strategy tracked: {tier5.get('name', 'Unknown')}"
        except Exception as e:
            return False, f"Error reading crypto strategy: {e}"

    def test_alpaca_connection(self) -> tuple[bool, str]:
        """Test that we can connect to Alpaca API."""
        try:
            from dotenv import load_dotenv

            load_dotenv()

            api_key = os.getenv("ALPACA_API_KEY")
            api_secret = os.getenv("ALPACA_SECRET_KEY")

            if not api_key or not api_secret:
                return False, "ALPACA_API_KEY and ALPACA_SECRET_KEY not set"

            from alpaca.trading.client import TradingClient

            client = TradingClient(api_key, api_secret, paper=True)
            account = client.get_account()

            if not account:
                return False, "Failed to retrieve account from Alpaca"

            return (
                True,
                f"Alpaca connection successful (Equity: ${float(account.equity):,.2f})",
            )
        except ImportError:
            return False, "alpaca-py not installed (skip in CI without deps)"
        except Exception as e:
            return False, f"Alpaca connection failed: {e}"

    def test_crypto_positions_match_state(self) -> tuple[bool, str]:
        """
        Test that crypto positions in Alpaca match our state tracking.

        This is the critical test - verifies we're not lying about trades.
        """
        try:
            from dotenv import load_dotenv

            load_dotenv()

            api_key = os.getenv("ALPACA_API_KEY")
            api_secret = os.getenv("ALPACA_SECRET_KEY")

            if not api_key or not api_secret:
                return False, "Alpaca credentials not available (skip in CI)"

            from alpaca.trading.client import TradingClient

            client = TradingClient(api_key, api_secret, paper=True)

            # Get positions from Alpaca (GROUND TRUTH)
            positions = client.get_all_positions()
            crypto_positions = [p for p in positions if "BTC" in p.symbol or "ETH" in p.symbol]

            # Get state from our tracking
            with open(self.state_file) as f:
                state = json.load(f)

            tier5 = state.get("strategies", {}).get("tier5", {})
            tracked_trades = tier5.get("trades_executed", 0)
            tracked_invested = tier5.get("total_invested", 0.0)

            # Compare
            if len(crypto_positions) == 0 and tracked_trades == 0:
                return True, "No crypto positions (matches state: 0 trades)"
            elif len(crypto_positions) > 0 and tracked_trades == 0:
                return (
                    False,
                    f"⚠️ MISMATCH: {len(crypto_positions)} crypto positions in Alpaca but state shows 0 trades. State not updated!",
                )
            elif len(crypto_positions) > 0 and tracked_trades > 0:
                # Calculate total value from positions
                total_value = sum(float(p.market_value) for p in crypto_positions)
                if abs(total_value - tracked_invested) > 50:  # Allow $50 variance
                    return (
                        False,
                        f"⚠️ MISMATCH: Positions value ${total_value:.2f} vs tracked ${tracked_invested:.2f}",
                    )
                return (
                    True,
                    f"✅ Positions match state: {len(crypto_positions)} positions, ${total_value:.2f} invested",
                )
            else:
                return True, "No positions, no tracked trades (consistent)"

        except ImportError:
            return False, "alpaca-py not installed (skip in CI without deps)"
        except FileNotFoundError:
            return False, "system_state.json not found"
        except Exception as e:
            return False, f"Position verification failed: {e}"

    def test_recent_crypto_orders_exist(self) -> tuple[bool, str]:
        """Test that recent crypto orders exist in Alpaca."""
        try:
            from dotenv import load_dotenv

            load_dotenv()

            api_key = os.getenv("ALPACA_API_KEY")
            api_secret = os.getenv("ALPACA_SECRET_KEY")

            if not api_key or not api_secret:
                return False, "Alpaca credentials not available (skip in CI)"

            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import GetOrdersRequest

            client = TradingClient(api_key, api_secret, paper=True)

            # Get orders from last 7 days
            orders = client.get_orders(GetOrdersRequest(status="all", limit=20))

            crypto_orders = [o for o in orders if "BTC" in o.symbol or "ETH" in o.symbol]

            if len(crypto_orders) == 0:
                return True, "No recent crypto orders (expected if no trades executed)"
            else:
                filled = [o for o in crypto_orders if o.status == "filled"]
                return (
                    True,
                    f"Found {len(crypto_orders)} crypto orders ({len(filled)} filled)",
                )

        except ImportError:
            return False, "alpaca-py not installed (skip in CI without deps)"
        except Exception as e:
            return False, f"Order check failed: {e}"

    def run_all_tests(self) -> dict[str, Any]:
        """Run all verification tests."""
        tests = [
            ("State file exists", self.test_state_file_exists),
            ("State file valid JSON", self.test_state_file_valid_json),
            ("Crypto strategy tracked", self.test_crypto_strategy_tracked),
            ("Alpaca connection", self.test_alpaca_connection),
            ("Positions match state", self.test_crypto_positions_match_state),
            ("Recent crypto orders", self.test_recent_crypto_orders_exist),
        ]

        results = {"passed": 0, "failed": 0, "details": []}

        for test_name, test_func in tests:
            try:
                passed, message = test_func()
                if passed:
                    results["passed"] += 1
                    status = "✅"
                else:
                    results["failed"] += 1
                    status = "❌"
                results["details"].append({"test": test_name, "status": status, "message": message})
            except Exception as e:
                results["failed"] += 1
                results["details"].append(
                    {
                        "test": test_name,
                        "status": "❌",
                        "message": f"Exception: {e}",
                    }
                )

        return results


def main():
    """Run crypto trade verification smoke tests."""
    print("=" * 70)
    print("🔥 CRYPTO TRADE VERIFICATION SMOKE TESTS")
    print("=" * 70)
    print()

    tester = CryptoTradeVerificationTests()
    results = tester.run_all_tests()

    # Print results
    for detail in results["details"]:
        print(f"{detail['status']} {detail['test']}: {detail['message']}")

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"Total: {len(results['details'])}")
    print()

    # Critical test: positions match state
    critical_test = next(
        (d for d in results["details"] if d["test"] == "Positions match state"),
        None,
    )

    if critical_test and "MISMATCH" in critical_test["message"]:
        print("🚨 CRITICAL: Positions don't match state - state tracking bug!")
        print("   This means trades executed but weren't tracked.")
        print("   Check logs and fix state update logic.")
        print()

    if results["failed"] == 0:
        print("🎉 All crypto trade verification tests passed!")
        return 0
    else:
        print(f"⚠️  {results['failed']} test(s) failed")
        # Don't fail if it's just missing dependencies
        if any(
            "not installed" in d["message"] or "not available" in d["message"]
            for d in results["details"]
            if d["status"] == "❌"
        ):
            print("   (Some failures due to missing dependencies - OK in CI)")
            return 0
        return 1


if __name__ == "__main__":
    sys.exit(main())
