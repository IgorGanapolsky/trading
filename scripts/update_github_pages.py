#!/usr/bin/env python3
"""
Auto-update GitHub Pages with current portfolio data.

PREVENTION: Ensures docs/index.md always reflects current system_state.json
This prevents stale data from being displayed on the public website.

Created: Jan 3, 2026 - After discovering GitHub Pages showed Dec 29 data on Jan 3.
"""

import json
import re
import sys
from pathlib import Path


def load_system_state(state_path: Path) -> dict:
    """Load system state from JSON file."""
    if not state_path.exists():
        raise FileNotFoundError(f"System state not found: {state_path}")

    with open(state_path) as f:
        return json.load(f)


def count_lessons(lessons_dir: Path) -> int:
    """Count lesson files in docs/_lessons."""
    if not lessons_dir.exists():
        return 0
    return len(list(lessons_dir.glob("*.md")))


def format_currency(value: float) -> str:
    """Format value as currency with commas."""
    return f"${value:,.2f}"


def format_percentage(value: float) -> str:
    """Format value as percentage."""
    return f"+{value:.2f}%" if value >= 0 else f"{value:.2f}%"


def update_index_md(
    index_path: Path,
    equity: float,
    pl_pct: float,
    win_rate: float,
    lessons_count: int,
    day: int,
    total_days: int,
    total_pl: float | None = None,
    positions_count: int = 0,
) -> bool:
    """
    Update docs/index.md with current portfolio data.

    Returns True if file was modified, False if already up to date.

    FIX Jan 19, 2026: Updated to match current simple index.md format.
    """
    if not index_path.exists():
        raise FileNotFoundError(f"Index file not found: {index_path}")

    content = index_path.read_text()
    original_content = content

    # Get current date for display
    from datetime import datetime
    today = datetime.now()
    date_str = today.strftime("%b %d, %Y")  # e.g., "Jan 19, 2026"

    # Update "Current Status" header with day number
    # Pattern: ## Current Status (Day XX - Mon DD, YYYY)
    status_pattern = r"## Current Status \(Day \d+ - [A-Za-z]+ \d+, \d+\)"
    status_replacement = f"## Current Status (Day {day} - {date_str})"
    content = re.sub(status_pattern, status_replacement, content)

    # =========================================================================
    # NEW FORMAT (simple tables - current index.md)
    # =========================================================================

    # Update Paper Account row
    # Pattern: | Paper Account | $X,XXX.XX |
    account_pattern = r"\| Paper Account \| \$[\d,]+\.?\d* \|"
    account_replacement = f"| Paper Account | {format_currency(equity)} |"
    content = re.sub(account_pattern, account_replacement, content)

    # Update Total P/L row (if total_pl is provided)
    # Pattern: | Total P/L | **+$X.XX (+X.XX%)** | or | Total P/L | **-$X.XX (-X.XX%)** |
    if total_pl is not None:
        pl_sign = "+" if total_pl >= 0 else ""
        pl_pattern = r"\| Total P/L \| \*\*[+\-]?\$[\d,]+\.?\d* \([+\-]?[\d.]+%\)\*\* \|"
        pl_replacement = f"| Total P/L | **{pl_sign}{format_currency(total_pl)} ({format_percentage(pl_pct)})** |"
        content = re.sub(pl_pattern, pl_replacement, content)

    # Update Open Positions row
    # Pattern: | Open Positions | X ... |
    if positions_count > 0:
        pos_pattern = r"\| Open Positions \| \d+ .*\|"
        spread_count = positions_count // 2  # Approximate spread count
        pos_replacement = f"| Open Positions | {positions_count} ({spread_count} SPY put spreads) |"
        content = re.sub(pos_pattern, pos_replacement, content)

    # =========================================================================
    # OLD FORMAT (Daily Transparency Report tables - for backwards compatibility)
    # =========================================================================

    # Pattern: | **Portfolio** | $XXX,XXX.XX | +X.XX% |
    portfolio_pattern = r"\| \*\*Portfolio\*\* \| \$[\d,]+\.\d+ \| [+\-]?\d+\.\d+% \|"
    portfolio_replacement = (
        f"| **Portfolio** | {format_currency(equity)} | {format_percentage(pl_pct)} |"
    )
    content = re.sub(portfolio_pattern, portfolio_replacement, content)

    # Pattern: | **Win Rate** | XX% | ... |
    win_rate_pattern = r"\| \*\*Win Rate\*\* \| \d+% \| \w+ \|"
    win_rate_replacement = (
        f"| **Win Rate** | {int(win_rate)}% | {'Improved' if win_rate >= 60 else 'Stable'} |"
    )
    content = re.sub(win_rate_pattern, win_rate_replacement, content)

    # Pattern: | **Lessons** | XX+ | Growing |
    lessons_pattern = r"\| \*\*Lessons\*\* \| \d+\+ \| Growing \|"
    lessons_replacement = f"| **Lessons** | {lessons_count}+ | Growing |"
    content = re.sub(lessons_pattern, lessons_replacement, content)

    # Pattern: | **Day** | XX/90 | R&D Phase |
    day_pattern = r"\| \*\*Day\*\* \| \d+/\d+ \| R&D Phase \|"
    day_replacement = f"| **Day** | {day}/{total_days} | R&D Phase |"
    content = re.sub(day_pattern, day_replacement, content)

    if content == original_content:
        return False

    index_path.write_text(content)
    return True


def main() -> int:
    """Main entry point."""
    # Paths
    repo_root = Path(__file__).parent.parent
    state_path = repo_root / "data" / "system_state.json"
    index_path = repo_root / "docs" / "index.md"
    lessons_dir = repo_root / "docs" / "_lessons"
    rag_lessons_dir = repo_root / "rag_knowledge" / "lessons_learned"

    try:
        # Load current state
        state = load_system_state(state_path)

        # Extract values - FIX Jan 19, 2026: Use correct JSON paths
        # The system_state.json uses paper_account, not account
        paper_account = state.get("paper_account", {})
        portfolio = state.get("portfolio", {})

        # Try paper_account first (current structure), fall back to account (old structure)
        equity = paper_account.get("equity") or portfolio.get("equity", 5000.0)
        pl_pct = paper_account.get("total_pl_pct", 0.0)
        positions_count = paper_account.get("positions_count", 0)
        win_rate = paper_account.get("win_rate", 0)

        # Calculate day number (Oct 28, 2025 = Day 1)
        from datetime import datetime, timezone
        start_date = datetime(2025, 10, 28, tzinfo=timezone.utc)
        today = datetime.now(timezone.utc)
        day = (today - start_date).days + 1
        total_days = 90

        # Count lessons - check both docs/_lessons and rag_knowledge
        lessons_count = count_lessons(lessons_dir)
        if lessons_count == 0:
            lessons_count = count_lessons(rag_lessons_dir)

        # Get total P/L in dollars
        total_pl = paper_account.get("total_pl", 0.0)

        print("📊 Current Portfolio Data:")
        print(f"   Equity: {format_currency(equity)}")
        print(f"   Total P/L: {format_currency(total_pl)} ({format_percentage(pl_pct)})")
        print(f"   Positions: {positions_count}")
        print(f"   Win Rate: {win_rate}%")
        print(f"   Day: {day}/{total_days}")
        print(f"   Lessons: {lessons_count}")
        print()

        # Update index.md
        updated = update_index_md(
            index_path=index_path,
            equity=equity,
            pl_pct=pl_pct,
            total_pl=total_pl,
            positions_count=positions_count,
            win_rate=win_rate,
            lessons_count=lessons_count,
            day=day,
            total_days=total_days,
        )

        if updated:
            print("✅ docs/index.md updated with current data")
        else:
            print("ℹ️ docs/index.md already up to date")

        return 0

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
