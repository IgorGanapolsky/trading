#!/usr/bin/env python3
"""
Auto-update docs/index.md with current data from system_state.json.

This prevents stale dashboard issues by automatically updating:
- Day number (calculated from Oct 29, 2025 start date)
- Current date
- Paper account balance
- P/L values
- Position counts

Run by: update-progress-dashboard.yml, ralph-mode-cto.yml
"""

import json
import re
from datetime import datetime
from pathlib import Path

# Project start date
PROJECT_START = datetime(2025, 10, 29)

# File paths
SYSTEM_STATE_PATH = Path("data/system_state.json")
DOCS_INDEX_PATH = Path("docs/index.md")


def calculate_day_number() -> int:
    """Calculate the current day number from project start."""
    today = datetime.now()
    delta = today - PROJECT_START
    return delta.days + 1


def load_system_state() -> dict:
    """Load current system state."""
    if not SYSTEM_STATE_PATH.exists():
        return {}
    with open(SYSTEM_STATE_PATH) as f:
        return json.load(f)


def format_date() -> str:
    """Format current date as 'Jan 21, 2026'."""
    return datetime.now().strftime("%b %d, %Y").replace(" 0", " ")


def calculate_total_pl(state: dict) -> str:
    """Calculate total unrealized P/L from positions."""
    positions = state.get("paper_account", {}).get("positions", [])
    total_pl = 0.0

    for pos in positions:
        pl_str = pos.get("unrealized_pl", "0")
        try:
            total_pl += float(pl_str)
        except (ValueError, TypeError):
            pass

    if total_pl < 0:
        return f"**-${abs(total_pl):.0f} (unrealized)**"
    else:
        return f"**+${total_pl:.0f} (unrealized)**"


def update_docs_index():
    """Update docs/index.md with current data."""
    if not DOCS_INDEX_PATH.exists():
        print(f"Error: {DOCS_INDEX_PATH} not found")
        return False

    state = load_system_state()
    if not state:
        print("Warning: Empty system state, using defaults")

    # Calculate values
    day_number = calculate_day_number()
    current_date = format_date()
    equity = state.get("portfolio", {}).get("equity", "5000")
    position_count = state.get("paper_account", {}).get("positions_count", 0)
    total_pl = calculate_total_pl(state)

    # Read current index
    content = DOCS_INDEX_PATH.read_text()
    original = content

    # Update day/date header: ## Current Status (Day XX - Mon DD, YYYY)
    content = re.sub(
        r"## Current Status \(Day \d+ - [A-Za-z]+ \d+, \d{4}\)",
        f"## Current Status (Day {day_number} - {current_date})",
        content
    )

    # Update Paper Account row
    content = re.sub(
        r"\| Paper Account \| \$[\d,.]+ \|",
        f"| Paper Account | ${float(equity):,.2f} |",
        content
    )

    # Update Total P/L row
    content = re.sub(
        r"\| Total P/L \| \*\*[+-]?\$\d+[^|]*\*\* \|",
        f"| Total P/L | {total_pl} |",
        content
    )

    # Update Open Positions row
    content = re.sub(
        r"\| Open Positions \| \d+[^|]* \|",
        f"| Open Positions | {position_count} |",
        content
    )

    # Check if anything changed
    if content == original:
        print("No changes needed to docs/index.md")
        return True

    # Write updated content
    DOCS_INDEX_PATH.write_text(content)
    print("Updated docs/index.md:")
    print(f"  - Day: {day_number}")
    print(f"  - Date: {current_date}")
    print(f"  - Equity: ${float(equity):,.2f}")
    print(f"  - Positions: {position_count}")
    print(f"  - P/L: {total_pl}")

    return True


if __name__ == "__main__":
    success = update_docs_index()
    exit(0 if success else 1)
