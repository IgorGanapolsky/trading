#!/usr/bin/env python3
"""
Update Blog Positions - Sync paper trading positions to GitHub Pages blog.

This script reads positions from system_state.json and updates the blog
markdown files to display current paper trading positions.

Run after sync_alpaca_state.py to keep blog in sync with actual positions.
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SYSTEM_STATE = PROJECT_ROOT / "data" / "system_state.json"
INDEX_MD = PROJECT_ROOT / "docs" / "index.md"
DASHBOARD_MD = PROJECT_ROOT / "docs" / "progress_dashboard.md"


def load_positions() -> list[dict]:
    """Load positions from system_state.json."""
    if not SYSTEM_STATE.exists():
        print(f"❌ State file not found: {SYSTEM_STATE}")
        return []

    with open(SYSTEM_STATE) as f:
        state = json.load(f)

    return state.get("performance", {}).get("open_positions", [])


def load_paper_account() -> dict:
    """Load paper account summary from system_state.json."""
    if not SYSTEM_STATE.exists():
        return {}

    with open(SYSTEM_STATE) as f:
        state = json.load(f)

    return state.get("paper_account", {})


def generate_positions_table(positions: list[dict]) -> str:
    """Generate markdown table for positions."""
    if not positions:
        return "| *No open positions* | - | - | - | - |\n"

    lines = []
    for pos in sorted(positions, key=lambda x: abs(x.get("market_value", 0)), reverse=True):
        symbol = pos.get("symbol", "?")
        side = pos.get("side", "long").capitalize()
        entry = pos.get("entry_price", 0)
        current = pos.get("current_price", 0)
        pl = pos.get("unrealized_pl", 0)
        pl_pct = pos.get("unrealized_pl_pct", 0)

        # Format P/L with color indicator
        pl_sign = "+" if pl >= 0 else ""
        lines.append(
            f"| {symbol} | {side} | ${entry:,.2f} | ${current:,.2f} | {pl_sign}${pl:,.2f} ({pl_pct:+.1f}%) |"
        )

    return "\n".join(lines) + "\n"


def update_index_md(positions: list[dict], paper_account: dict) -> bool:
    """Update docs/index.md with paper trading positions."""
    if not INDEX_MD.exists():
        print(f"❌ Index file not found: {INDEX_MD}")
        return False

    content = INDEX_MD.read_text()

    # Generate new paper positions section
    positions_table = generate_positions_table(positions)
    positions_count = len(positions)
    total_value = sum(p.get("market_value", 0) for p in positions)
    total_pl = sum(p.get("unrealized_pl", 0) for p in positions)
    pl_sign = "+" if total_pl >= 0 else ""

    new_paper_section = f"""### Paper Trading (R&D)

| Metric | Value | Trend |
|--------|-------|-------|
| **Day** | 50/90 | R&D Phase |
| **Portfolio** | ${paper_account.get("current_equity", 100942.23):,.2f} | {paper_account.get("total_pl_pct", 0.94):+.2f}% |
| **Win Rate** | {paper_account.get("win_rate", 80):.0f}% | Proven |
| **Lessons** | 75+ | Growing |

#### Open Positions ({positions_count})

| Symbol | Type | Entry | Current | P/L |
|--------|------|-------|---------|-----|
{positions_table}
> **Total Position Value**: ${total_value:,.2f} | **Unrealized P/L**: {pl_sign}${total_pl:,.2f}

> **Strategy**: Backtest and analyze during off-hours. Apply proven strategies to real account."""

    # Replace the Paper Trading section
    pattern = r"### Paper Trading \(R&D\).*?(?=\n---|\n## |\Z)"
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, new_paper_section, content, flags=re.DOTALL)
    else:
        # Insert before "What's Working" section if pattern not found
        content = content.replace(
            "## What's Working", f"{new_paper_section}\n\n---\n\n## What's Working"
        )

    INDEX_MD.write_text(content)
    print(f"✅ Updated {INDEX_MD}")
    return True


def update_dashboard_md(positions: list[dict]) -> bool:
    """Update docs/progress_dashboard.md with paper trading positions."""
    if not DASHBOARD_MD.exists():
        print(f"❌ Dashboard file not found: {DASHBOARD_MD}")
        return False

    content = DASHBOARD_MD.read_text()

    # Generate positions section
    positions_count = len(positions)

    new_section = f"""## Current Positions

### Live Account

| Symbol | Type | Strike | Expiry | Entry | Current | P/L |
|--------|------|--------|--------|-------|---------|-----|
| *No positions yet* | - | - | - | - | - | - |

> Starting fresh with $20. First options trade coming when we reach minimum capital for defined-risk spreads.

### Paper Account ({positions_count} positions)

| Symbol | Type | Entry | Current | P/L |
|--------|------|-------|---------|-----|
{generate_positions_table(positions)}"""

    # Replace the Current Positions section
    pattern = r"## Current Positions.*?(?=\n---|\n## Recent)"
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, new_section, content, flags=re.DOTALL)

    DASHBOARD_MD.write_text(content)
    print(f"✅ Updated {DASHBOARD_MD}")
    return True


def main() -> int:
    """Main entry point."""
    print("=" * 60)
    print("📝 UPDATE BLOG POSITIONS")
    print("=" * 60)

    positions = load_positions()
    paper_account = load_paper_account()

    print(f"\n📊 Found {len(positions)} open positions")

    if positions:
        print("\n📈 Positions:")
        for p in positions[:5]:  # Show first 5
            symbol = p.get("symbol", "?")
            pl = p.get("unrealized_pl", 0)
            print(f"   {symbol}: ${pl:+,.2f}")
        if len(positions) > 5:
            print(f"   ... and {len(positions) - 5} more")

    success = True
    success &= update_index_md(positions, paper_account)
    success &= update_dashboard_md(positions)

    print("\n" + "=" * 60)
    if success:
        print("✅ Blog updated successfully")
    else:
        print("❌ Some updates failed")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
