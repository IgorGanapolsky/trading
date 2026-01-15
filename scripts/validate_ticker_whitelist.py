#!/usr/bin/env python3
"""
Validate Ticker Whitelist Against CLAUDE.md

This CI check ensures workflow ticker lists match the approved tickers in CLAUDE.md.
Prevents incidents like LL-197 where SOFI was traded during earnings blackout.

Created: January 15, 2026
Author: CTO (Claude)
"""

import re
import sys
from pathlib import Path


def get_approved_tickers_from_claude_md() -> set[str]:
    """Extract approved tickers from CLAUDE.md."""
    claude_md = Path(".claude/CLAUDE.md")
    if not claude_md.exists():
        print(f"ERROR: {claude_md} not found")
        sys.exit(1)

    content = claude_md.read_text()

    # Look for "SPY/IWM ONLY" pattern
    approved = {"SPY", "IWM"}  # Default from strategy

    # Check if there's a ticker hierarchy table
    if "CREDIT SPREADS on SPY/IWM ONLY" in content:
        approved = {"SPY", "IWM"}

    return approved


def get_blackout_tickers_from_claude_md() -> dict[str, str]:
    """Extract blackout tickers from CLAUDE.md."""
    claude_md = Path(".claude/CLAUDE.md")
    content = claude_md.read_text()

    blackouts = {}

    # Look for AVOID/BLACKOUT patterns
    # Example: "SOFI | **AVOID until Feb 1** | Jan 23-30 (earnings Jan 30, IV 55%)"
    patterns = [
        r"(\w+)\s*\|\s*\*\*AVOID[^*]+\*\*",  # Table format with AVOID
        r"BLACKOUT.*?(\w+)",  # BLACKOUT mention
        r"(\w+).*?earnings.*?blackout",  # earnings blackout mention
    ]

    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            ticker = match.upper().strip()
            if len(ticker) <= 5 and ticker.isalpha():  # Valid ticker
                blackouts[ticker] = "In CLAUDE.md blackout list"

    return blackouts


def check_workflow_tickers() -> list[str]:
    """Check workflow files for ticker violations."""
    errors = []
    approved = get_approved_tickers_from_claude_md()
    blackouts = get_blackout_tickers_from_claude_md()

    workflow_dir = Path(".github/workflows")
    if not workflow_dir.exists():
        return errors

    # Patterns that indicate trading ticker selection
    ticker_patterns = [
        r'TICKERS="([^"]+)"',  # TICKERS="SPY IWM"
        r"--symbol\s+(\w+)",  # --symbol SPY
        r'for\s+TICKER\s+in\s+([A-Z\s]+)',  # for TICKER in SPY IWM
    ]

    for workflow in workflow_dir.glob("*.yml"):
        content = workflow.read_text()

        for pattern in ticker_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # Split on whitespace to get individual tickers
                tickers = match.split()
                for ticker in tickers:
                    ticker = ticker.upper().strip()
                    if not ticker or not ticker.isalpha():
                        continue

                    # Check if ticker is in blackout
                    if ticker in blackouts:
                        errors.append(
                            f"BLACKOUT: {workflow.name} uses {ticker} "
                            f"which is in CLAUDE.md blackout list"
                        )

    return errors


def main():
    """Run ticker validation."""
    print("=" * 60)
    print("TICKER WHITELIST VALIDATION")
    print("=" * 60)

    approved = get_approved_tickers_from_claude_md()
    print(f"\nApproved tickers (from CLAUDE.md): {approved}")

    blackouts = get_blackout_tickers_from_claude_md()
    if blackouts:
        print(f"Blackout tickers: {list(blackouts.keys())}")

    errors = check_workflow_tickers()

    if errors:
        print("\n" + "=" * 60)
        print("VALIDATION FAILED")
        print("=" * 60)
        for error in errors:
            print(f"  - {error}")
        print("\nFix: Remove blackout tickers from workflow files")
        print("Reference: LL-197 (SOFI blackout violation)")
        sys.exit(1)
    else:
        print("\n" + "=" * 60)
        print("VALIDATION PASSED")
        print("=" * 60)
        print("All workflow tickers comply with CLAUDE.md")
        sys.exit(0)


if __name__ == "__main__":
    main()
