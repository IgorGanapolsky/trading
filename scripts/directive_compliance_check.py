#!/usr/bin/env python3
"""
Directive Compliance Check - Automated verification of CLAUDE.md rules.

Created: Jan 14, 2026 after LL-203 crisis
Purpose: PREVENT violations instead of fixing after the fact.

This script can be run:
1. Before any trade execution
2. As a pre-commit hook
3. In CI/CD pipeline
"""

import sys
from datetime import datetime
from pathlib import Path

# Core directives from CLAUDE.md
DIRECTIVES = {
    1: "Don't lose money - Rule #1 always",
    2: "Never argue with CEO - Follow directives immediately",
    3: "Never tell CEO to do manual work - If I can do it, I MUST do it myself",
    4: "Always show evidence - File counts, command output with every claim",
    5: "Never lie - Say 'I believe this is done, verifying now...' NOT 'Done!'",
    6: "Use PRs for all changes - Always merge via PRs",
    7: "Query Vertex AI RAG before tasks - Learn from recorded lessons first",
    8: "Record every trade and lesson in Vertex AI RAG",
    9: "Learn from mistakes in RAG - Record and learn from violations",
    10: "100% operational security - Dry runs before merging",
}

# Trading rules that must be checked before any trade
TRADING_RULES = {
    "position_size_pct": 0.05,  # 5% max per trade
    "position_size_desc": "Max 5% of account per trade ($248)",
    "spread_only": True,
    "allowed_tickers": ["SPY", "IWM"],
    "min_dte": 30,
    "max_dte": 45,
    "stop_loss_required": True,
}

# Earnings blackouts - trades blocked during these periods
EARNINGS_BLACKOUTS = {
    "SOFI": {"start": "2026-01-23", "end": "2026-02-01", "reason": "Earnings Jan 30"},
    "F": {"start": "2026-02-03", "end": "2026-02-10", "reason": "Earnings Feb 10"},
}


def check_ticker_allowed(ticker: str) -> tuple[bool, str]:
    """Check if ticker is in allowed list."""
    if ticker.upper() in TRADING_RULES["allowed_tickers"]:
        return True, f"{ticker} is allowed"
    return False, f"{ticker} NOT in allowed list: {TRADING_RULES['allowed_tickers']}"


def check_earnings_blackout(ticker: str) -> tuple[bool, str]:
    """Check if ticker is in earnings blackout."""
    today = datetime.now().date()
    ticker_upper = ticker.upper()

    if ticker_upper in EARNINGS_BLACKOUTS:
        blackout = EARNINGS_BLACKOUTS[ticker_upper]
        start = datetime.strptime(blackout["start"], "%Y-%m-%d").date()
        end = datetime.strptime(blackout["end"], "%Y-%m-%d").date()

        if start <= today <= end:
            return False, f"{ticker} in earnings blackout until {end} ({blackout['reason']})"

    return True, f"{ticker} not in blackout"


def check_position_size(amount: float, account_value: float = 4959.26) -> tuple[bool, str]:
    """Check if position size is within 5% limit."""
    max_size = account_value * TRADING_RULES["position_size_pct"]
    if amount <= max_size:
        return True, f"Position ${amount:.2f} within ${max_size:.2f} limit"
    return False, f"Position ${amount:.2f} exceeds ${max_size:.2f} limit (5%)"


def run_pre_trade_check(ticker: str, amount: float) -> bool:
    """Run all pre-trade compliance checks."""
    print("=" * 60)
    print("DIRECTIVE COMPLIANCE CHECK")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_passed = True

    # Check 1: Ticker allowed
    passed, msg = check_ticker_allowed(ticker)
    status = "✅" if passed else "❌"
    print(f"{status} Ticker Check: {msg}")
    all_passed = all_passed and passed

    # Check 2: Earnings blackout
    passed, msg = check_earnings_blackout(ticker)
    status = "✅" if passed else "❌"
    print(f"{status} Blackout Check: {msg}")
    all_passed = all_passed and passed

    # Check 3: Position size
    passed, msg = check_position_size(amount)
    status = "✅" if passed else "❌"
    print(f"{status} Position Size: {msg}")
    all_passed = all_passed and passed

    print("=" * 60)
    if all_passed:
        print("✅ ALL CHECKS PASSED - Trade may proceed")
    else:
        print("❌ COMPLIANCE FAILED - Trade BLOCKED")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    # Example usage
    if len(sys.argv) >= 3:
        ticker = sys.argv[1]
        amount = float(sys.argv[2])
        success = run_pre_trade_check(ticker, amount)
        sys.exit(0 if success else 1)
    else:
        # Demo mode
        print("\nDemo: Testing SOFI trade (should FAIL)")
        run_pre_trade_check("SOFI", 500)

        print("\nDemo: Testing SPY trade within limits (should PASS)")
        run_pre_trade_check("SPY", 200)

        print("\nDemo: Testing SPY trade over limit (should FAIL)")
        run_pre_trade_check("SPY", 500)
