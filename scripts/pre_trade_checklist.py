#!/usr/bin/env python3
"""
Pre-Trade Checklist - Enforces CLAUDE.md rules before any trade.

This script MUST pass before any trade executes.
Violations = trade blocked.

Created: Jan 14, 2026 after SOFI loss (-$40.74)
Lesson: LL-196 - Rule #1 violations cost real money.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Allowed tickers - UPDATED Jan 19, 2026 (LL-244): SPY ONLY per CLAUDE.md
ALLOWED_TICKERS = ["SPY"]  # SPY ONLY - IWM removed per adversarial audit

# Earnings blackout periods (ticker: (start_date, end_date))
EARNINGS_BLACKOUTS = {
    "SOFI": ("2026-01-23", "2026-02-01"),
    "F": ("2026-02-03", "2026-02-10"),
    "AAPL": ("2026-01-25", "2026-02-01"),
    "MSFT": ("2026-01-25", "2026-02-01"),
}

# Risk limits
MAX_POSITION_PCT = 0.05  # 5% max per trade
MIN_DTE = 30
MAX_DTE = 45
MAX_OPEN_SPREADS = 1  # Position limit: 1 spread at a time per CLAUDE.md


def load_account_state() -> dict:
    """Load current account state."""
    state_path = Path(__file__).parent.parent / "data" / "system_state.json"
    if state_path.exists():
        with open(state_path) as f:
            return json.load(f)
    return {}


def check_ticker_allowed(ticker: str) -> tuple[bool, str]:
    """Check if ticker is in allowed list."""
    ticker = ticker.upper()
    if ticker in ALLOWED_TICKERS:
        return True, f"✅ {ticker} is allowed (SPY only phase)"
    return False, f"❌ {ticker} NOT ALLOWED. Only SPY until win rate proven."


def check_earnings_blackout(ticker: str) -> tuple[bool, str]:
    """Check if ticker is in earnings blackout period."""
    ticker = ticker.upper()
    if ticker not in EARNINGS_BLACKOUTS:
        return True, f"✅ {ticker} has no known earnings blackout"

    start_str, end_str = EARNINGS_BLACKOUTS[ticker]
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    today = datetime.now()

    if start <= today <= end:
        return False, f"❌ {ticker} in EARNINGS BLACKOUT ({start_str} to {end_str})"
    if today < start and (start - today).days <= 7:
        return False, f"❌ {ticker} approaching earnings ({start_str}). Too risky."
    return True, f"✅ {ticker} clear of earnings blackout"


def check_position_size(collateral: float, account_equity: float) -> tuple[bool, str]:
    """Check if position size is within 5% limit."""
    max_allowed = account_equity * MAX_POSITION_PCT
    if collateral <= max_allowed:
        return True, f"✅ Position ${collateral:.2f} within 5% limit (${max_allowed:.2f})"
    return False, f"❌ Position ${collateral:.2f} exceeds 5% limit (${max_allowed:.2f})"


def check_is_spread(has_long_leg: bool) -> tuple[bool, str]:
    """Check if trade is a spread (not naked)."""
    if has_long_leg:
        return True, "✅ Trade is a SPREAD (defined risk)"
    return False, "❌ NAKED POSITION - Must buy protective leg for spread"


def check_dte(days_to_expiry: int) -> tuple[bool, str]:
    """Check if DTE is in 30-45 range."""
    if MIN_DTE <= days_to_expiry <= MAX_DTE:
        return True, f"✅ DTE {days_to_expiry} in optimal range ({MIN_DTE}-{MAX_DTE})"
    return False, f"❌ DTE {days_to_expiry} outside range ({MIN_DTE}-{MAX_DTE})"


def count_open_spreads(state: dict) -> int:
    """
    Count number of open spreads from positions.

    A spread consists of a long and short option at different strikes.
    We count spreads by pairing long/short positions.
    """
    positions = state.get("paper_account", {}).get("positions", [])
    if not positions:
        return 0

    # Count long and short option positions
    longs = 0
    shorts = 0
    for pos in positions:
        qty = int(pos.get("qty", 0))
        symbol = pos.get("symbol", "")
        # Only count options (have P or C in symbol for puts/calls)
        if "P" in symbol or "C" in symbol:
            if qty > 0:
                longs += qty
            elif qty < 0:
                shorts += abs(qty)

    # A spread is one long + one short, so count pairs
    return min(longs, shorts)


def check_spread_limit(state: dict) -> tuple[bool, str]:
    """Check if number of open spreads is within limit."""
    current_spreads = count_open_spreads(state)
    if current_spreads < MAX_OPEN_SPREADS:
        return True, f"✅ Open spreads: {current_spreads}/{MAX_OPEN_SPREADS} (can open new spread)"
    elif current_spreads == MAX_OPEN_SPREADS:
        return False, f"❌ Position limit reached: {current_spreads}/{MAX_OPEN_SPREADS} spreads open. Close existing before opening new."
    else:
        return False, f"❌ OVER LIMIT: {current_spreads} spreads open (max {MAX_OPEN_SPREADS}). Must close {current_spreads - MAX_OPEN_SPREADS} spreads!"


def run_full_checklist(
    ticker: str,
    collateral: float,
    has_long_leg: bool,
    days_to_expiry: int,
) -> tuple[bool, list[str]]:
    """
    Run full pre-trade checklist.

    Returns:
        (all_passed, list of check results)
    """
    state = load_account_state()
    equity = state.get("paper_account", {}).get("equity", 5000)

    results = []
    all_passed = True

    # Check 1: Ticker allowed
    passed, msg = check_ticker_allowed(ticker)
    results.append(msg)
    if not passed:
        all_passed = False

    # Check 2: Earnings blackout
    passed, msg = check_earnings_blackout(ticker)
    results.append(msg)
    if not passed:
        all_passed = False

    # Check 3: Position size
    passed, msg = check_position_size(collateral, equity)
    results.append(msg)
    if not passed:
        all_passed = False

    # Check 4: Is spread (not naked)
    passed, msg = check_is_spread(has_long_leg)
    results.append(msg)
    if not passed:
        all_passed = False

    # Check 5: DTE range
    passed, msg = check_dte(days_to_expiry)
    results.append(msg)
    if not passed:
        all_passed = False

    # Check 6: Spread limit (max 1 spread at a time per CLAUDE.md)
    passed, msg = check_spread_limit(state)
    results.append(msg)
    if not passed:
        all_passed = False

    return all_passed, results


def main():
    """Run checklist with sample trade."""
    print("=" * 60)
    print("PRE-TRADE CHECKLIST - Rule #1 Enforcement")
    print("=" * 60)

    # Example: SPY credit spread
    ticker = "SPY"
    collateral = 248  # 5% of ~$5000
    has_long_leg = True  # It's a spread
    dte = 35  # 35 days to expiry

    passed, results = run_full_checklist(ticker, collateral, has_long_leg, dte)

    print(f"\nTrade: {ticker} credit spread")
    print(f"Collateral: ${collateral}")
    print(f"DTE: {dte}")
    print(f"Spread: {has_long_leg}")
    print("\nChecklist Results:")
    for r in results:
        print(f"  {r}")

    print("\n" + "=" * 60)
    if passed:
        print("✅ ALL CHECKS PASSED - Trade allowed")
    else:
        print("❌ CHECKS FAILED - Trade BLOCKED")
    print("=" * 60)

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
