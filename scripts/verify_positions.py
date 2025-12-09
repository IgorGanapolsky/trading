#!/usr/bin/env python3
"""
Position Verification Script - Alpaca API vs Local State

Compares current positions from Alpaca API with our local system_state.json
to detect any discrepancies. Designed for both local development and CI/CD.

Exit Codes:
    0 - All positions match (success)
    1 - Discrepancies found or errors occurred (failure)

GitHub Actions Integration:
    Writes to GITHUB_OUTPUT if running in CI:
    - positions_match=true/false
    - discrepancy_count=N

Usage:
    # Local development
    python scripts/verify_positions.py

    # In GitHub Actions
    python scripts/verify_positions.py
    # Reads: ALPACA_API_KEY, ALPACA_SECRET_KEY, GITHUB_OUTPUT

Author: Trading System CTO
Created: 2025-12-08
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Load environment variables from .env if available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv not available, rely on system environment variables

# Environment variables
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
GITHUB_OUTPUT = os.getenv("GITHUB_OUTPUT")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
STATE_FILE = PROJECT_ROOT / "data" / "system_state.json"

# Comparison tolerances
QTY_TOLERANCE = 0.0001  # Allow tiny floating point differences
VALUE_TOLERANCE_PCT = 0.01  # 1% difference for value comparisons


@dataclass
class Position:
    """Represents a position from either source."""

    symbol: str
    quantity: float
    market_value: float
    avg_entry_price: float
    current_price: float
    unrealized_pl: float


@dataclass
class Discrepancy:
    """Represents a position discrepancy."""

    symbol: str
    issue: str
    local_value: Optional[float]
    alpaca_value: Optional[float]
    difference: Optional[float]


def load_local_positions() -> dict[str, Position]:
    """Load positions from local system_state.json."""
    if not STATE_FILE.exists():
        print(f"❌ ERROR: Local state file not found: {STATE_FILE}")
        return {}

    try:
        with open(STATE_FILE) as f:
            state = json.load(f)

        positions = {}
        for pos_data in state.get("performance", {}).get("open_positions", []):
            symbol = pos_data.get("symbol")
            if symbol:
                positions[symbol] = Position(
                    symbol=symbol,
                    quantity=float(pos_data.get("quantity", 0)),
                    market_value=float(pos_data.get("amount", 0)),
                    avg_entry_price=float(pos_data.get("entry_price", 0)),
                    current_price=float(pos_data.get("current_price", 0)),
                    unrealized_pl=float(pos_data.get("unrealized_pl", 0)),
                )

        return positions

    except Exception as e:
        print(f"❌ ERROR: Failed to load local state: {e}")
        return {}


def load_alpaca_positions() -> dict[str, Position]:
    """Load current positions from Alpaca API."""
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print("❌ ERROR: ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables required")
        return {}

    try:
        from alpaca.trading.client import TradingClient

        client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
        alpaca_positions = client.get_all_positions()

        positions = {}
        for pos in alpaca_positions:
            positions[pos.symbol] = Position(
                symbol=pos.symbol,
                quantity=float(pos.qty),
                market_value=float(pos.market_value),
                avg_entry_price=float(pos.avg_entry_price),
                current_price=float(pos.current_price),
                unrealized_pl=float(pos.unrealized_pl),
            )

        return positions

    except ImportError:
        print("❌ ERROR: alpaca-py not installed. Run: pip install alpaca-py")
        return {}
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch Alpaca positions: {e}")
        return {}


def compare_positions(local: dict[str, Position], alpaca: dict[str, Position]) -> list[Discrepancy]:
    """Compare positions and return list of discrepancies."""
    discrepancies = []

    all_symbols = set(local.keys()) | set(alpaca.keys())

    for symbol in sorted(all_symbols):
        local_pos = local.get(symbol)
        alpaca_pos = alpaca.get(symbol)

        # Case 1: Position in Alpaca but not locally
        if alpaca_pos and not local_pos:
            discrepancies.append(
                Discrepancy(
                    symbol=symbol,
                    issue="Position in Alpaca but NOT in local state",
                    local_value=None,
                    alpaca_value=alpaca_pos.quantity,
                    difference=alpaca_pos.quantity,
                )
            )
            continue

        # Case 2: Position locally but not in Alpaca
        if local_pos and not alpaca_pos:
            discrepancies.append(
                Discrepancy(
                    symbol=symbol,
                    issue="Position in local state but NOT in Alpaca (phantom)",
                    local_value=local_pos.quantity,
                    alpaca_value=None,
                    difference=local_pos.quantity,
                )
            )
            continue

        # Case 3: Both have position - compare details
        if local_pos and alpaca_pos:
            # Check quantity mismatch
            qty_diff = abs(local_pos.quantity - alpaca_pos.quantity)
            if qty_diff > QTY_TOLERANCE:
                discrepancies.append(
                    Discrepancy(
                        symbol=symbol,
                        issue="Quantity mismatch",
                        local_value=local_pos.quantity,
                        alpaca_value=alpaca_pos.quantity,
                        difference=qty_diff,
                    )
                )

            # Check value mismatch (>1% difference)
            value_diff = abs(local_pos.market_value - alpaca_pos.market_value)
            value_diff_pct = (
                (value_diff / alpaca_pos.market_value * 100) if alpaca_pos.market_value else 0
            )

            if value_diff_pct > VALUE_TOLERANCE_PCT:
                discrepancies.append(
                    Discrepancy(
                        symbol=symbol,
                        issue=f"Value mismatch (>{VALUE_TOLERANCE_PCT}% difference)",
                        local_value=local_pos.market_value,
                        alpaca_value=alpaca_pos.market_value,
                        difference=value_diff,
                    )
                )

    return discrepancies


def write_github_output(positions_match: bool, discrepancy_count: int) -> None:
    """Write results to GITHUB_OUTPUT for GitHub Actions."""
    if not GITHUB_OUTPUT:
        return

    try:
        with open(GITHUB_OUTPUT, "a") as f:
            f.write(f"positions_match={'true' if positions_match else 'false'}\n")
            f.write(f"discrepancy_count={discrepancy_count}\n")
        print(f"\n📝 GitHub Actions output written to {GITHUB_OUTPUT}")
    except Exception as e:
        print(f"⚠️  WARNING: Failed to write to GITHUB_OUTPUT: {e}")


def main() -> int:
    """Main verification logic."""
    print("=" * 70)
    print("🔍 POSITION VERIFICATION: Alpaca API vs Local State")
    print("=" * 70)

    # Load positions from both sources
    print("\n📥 Loading positions...")
    local_positions = load_local_positions()
    alpaca_positions = load_alpaca_positions()

    # Handle errors in loading
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print("\n❌ FAILED: Missing Alpaca credentials")
        write_github_output(positions_match=False, discrepancy_count=-1)
        return 1

    if not STATE_FILE.exists():
        print(f"\n❌ FAILED: Local state file not found: {STATE_FILE}")
        write_github_output(positions_match=False, discrepancy_count=-1)
        return 1

    print(f"   Local positions: {len(local_positions)}")
    print(f"   Alpaca positions: {len(alpaca_positions)}")

    # Compare positions
    print("\n🔬 Comparing positions...")
    discrepancies = compare_positions(local_positions, alpaca_positions)

    # Display results
    print("\n" + "=" * 70)
    print("📊 COMPARISON RESULTS")
    print("=" * 70)

    if not discrepancies:
        print("\n✅ SUCCESS: All positions match!")
        print(f"   {len(local_positions)} positions verified")

        # Show position details
        if local_positions:
            print("\n📈 Verified Positions:")
            for symbol in sorted(local_positions.keys()):
                pos = local_positions[symbol]
                print(
                    f"   {symbol:8s} | Qty: {pos.quantity:>12.6f} | Value: ${pos.market_value:>10,.2f}"
                )

        write_github_output(positions_match=True, discrepancy_count=0)
        print("\n" + "=" * 70)
        return 0

    else:
        print(f"\n❌ FAILED: {len(discrepancies)} discrepancies found")
        print("\n🚨 Discrepancies:")

        for i, d in enumerate(discrepancies, 1):
            print(f"\n   {i}. {d.symbol}: {d.issue}")
            if d.local_value is not None and d.alpaca_value is not None:
                print(f"      Local:  {d.local_value:>12.6f}")
                print(f"      Alpaca: {d.alpaca_value:>12.6f}")
                print(f"      Diff:   {d.difference:>12.6f}")
            elif d.local_value is not None:
                print(f"      Local:  {d.local_value:>12.6f}")
                print("      Alpaca: <missing>")
            else:
                print("      Local:  <missing>")
                print(f"      Alpaca: {d.alpaca_value:>12.6f}")

        print("\n💡 Next Steps:")
        print("   1. Review discrepancies above")
        print("   2. Run: python scripts/reconcile_positions.py --fix")
        print("   3. Investigate why positions diverged")

        write_github_output(positions_match=False, discrepancy_count=len(discrepancies))
        print("\n" + "=" * 70)
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        write_github_output(positions_match=False, discrepancy_count=-1)
        sys.exit(1)
