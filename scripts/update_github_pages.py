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
) -> bool:
    """
    Update docs/index.md with current portfolio data.

    Returns True if file was modified, False if already up to date.
    """
    if not index_path.exists():
        raise FileNotFoundError(f"Index file not found: {index_path}")

    content = index_path.read_text()
    original_content = content

    # Update Daily Transparency Report table
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

    # Update "What's Actually Working" table - Options Theta row
    options_pattern = r"\| \*\*Options Theta\*\* \| \d+% \| [+\-]?\$[\d,]+ \| Primary Edge \|"
    options_replacement = f"| **Options Theta** | {int(win_rate)}% | +{format_currency(equity - 100000).replace('$', '$')} | Primary Edge |"
    content = re.sub(options_pattern, options_replacement, content)

    # Update Core ETFs row
    etf_pattern = r"\| Core ETFs \(SPY\) \| \d+% \| [+\-]?\$[\d,]+ \| Working \|"
    etf_replacement = f"| Core ETFs (SPY) | {int(win_rate)}% | +{format_currency(equity - 100000).replace('$', '$')} | Working |"
    content = re.sub(etf_pattern, etf_replacement, content)

    # Update description in front matter
    desc_pattern = r'description: "90-day experiment building an AI trading system\. \d+% overall win rate \(\+\$[\d,]+ profit\)\.'
    desc_replacement = f'description: "90-day experiment building an AI trading system. {int(win_rate)}% overall win rate (+{format_currency(equity - 100000)} profit).'
    content = re.sub(desc_pattern, desc_replacement, content)

    # Update lessons count in Latest Updates section
    lessons_link_pattern = r"- \[Lessons Learned\].*- \d+\+ documented failures"
    lessons_link_replacement = f'- [Lessons Learned]({{{{ "/lessons/" | relative_url }}}}) - {lessons_count}+ documented failures'
    content = re.sub(lessons_link_pattern, lessons_link_replacement, content)

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

    try:
        # Load current state
        state = load_system_state(state_path)

        # Extract values
        account = state.get("account", {})
        equity = account.get("current_equity", 100000.0)
        pl_pct = account.get("total_pl_pct", 0.0)

        performance = state.get("performance", {})
        win_rate = performance.get("win_rate", 50.0)

        challenge = state.get("challenge", {})
        day = challenge.get("current_day", 1)
        total_days = challenge.get("total_days", 90)

        # Count lessons
        lessons_count = count_lessons(lessons_dir)

        print("📊 Current Portfolio Data:")
        print(f"   Equity: {format_currency(equity)}")
        print(f"   P/L: {format_percentage(pl_pct)}")
        print(f"   Win Rate: {win_rate}%")
        print(f"   Day: {day}/{total_days}")
        print(f"   Lessons: {lessons_count}")
        print()

        # Update index.md
        updated = update_index_md(
            index_path=index_path,
            equity=equity,
            pl_pct=pl_pct,
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
