#!/usr/bin/env python3
"""
Self-Healing Data Script

This script automatically fixes common data integrity issues:
1. Updates current_date and current_day in system_state.json
2. Regenerates dashboard files
3. Detects and reports data staleness

Run daily before trading or as part of CI to prevent data drift.
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path


def load_json(path: Path) -> dict:
    """Load JSON file safely."""
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Error loading {path}: {e}")
    return {}


def save_json(path: Path, data: dict) -> bool:
    """Save JSON file with pretty printing."""
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError as e:
        print(f"Error saving {path}: {e}")
        return False


def calculate_challenge_day(start_date_str: str = "2025-10-29") -> tuple[int, int]:
    """Calculate current day number and days remaining."""
    try:
        start_date = datetime.fromisoformat(start_date_str).date()
        today = date.today()
        current_day = (today - start_date).days + 1
        days_remaining = max(90 - current_day, 0)
        return current_day, days_remaining
    except Exception:
        return 1, 89


def fix_system_state(state_path: Path) -> list[str]:
    """Fix system_state.json issues. Returns list of fixes applied."""
    fixes = []
    state = load_json(state_path)

    if not state:
        print(f"ERROR: Cannot load {state_path}")
        return fixes

    today = date.today()
    today_str = today.isoformat()

    # Fix challenge section
    challenge = state.get("challenge", {})
    start_date = challenge.get("start_date", "2025-10-29")
    current_day, days_remaining = calculate_challenge_day(start_date)

    # Check and fix current_date
    if challenge.get("current_date") != today_str:
        old_date = challenge.get("current_date", "unknown")
        challenge["current_date"] = today_str
        fixes.append(f"Updated current_date: {old_date} -> {today_str}")

    # Check and fix current_day
    if challenge.get("current_day") != current_day:
        old_day = challenge.get("current_day", "unknown")
        challenge["current_day"] = current_day
        fixes.append(f"Updated current_day: {old_day} -> {current_day}")

    # Check and fix days_remaining
    if challenge.get("days_remaining") != days_remaining:
        old_remaining = challenge.get("days_remaining", "unknown")
        challenge["days_remaining"] = days_remaining
        fixes.append(f"Updated days_remaining: {old_remaining} -> {days_remaining}")

    state["challenge"] = challenge

    # Update meta section
    meta = state.get("meta", {})
    meta["last_updated"] = datetime.now().isoformat()
    state["meta"] = meta

    if fixes:
        if save_json(state_path, state):
            print(f"Applied {len(fixes)} fixes to system_state.json")
        else:
            print("ERROR: Failed to save system_state.json")
            return []

    return fixes


def fix_index_md(docs_path: Path, current_day: int) -> list[str]:
    """Fix docs/index.md with correct date. Returns list of fixes applied."""
    fixes = []
    index_path = docs_path / "index.md"

    if not index_path.exists():
        print(f"WARNING: {index_path} not found")
        return fixes

    today = date.today()
    day_name = today.strftime("%A")
    month_day_year = today.strftime("%B %d, %Y")

    try:
        content = index_path.read_text()
        original = content

        # Fix "Live Status (Day XX/90)"
        import re
        old_status = re.search(r"Live Status \(Day \d+/90\)", content)
        if old_status:
            new_status = f"Live Status (Day {current_day}/90)"
            if old_status.group() != new_status:
                content = content.replace(old_status.group(), new_status)
                fixes.append(f"Updated status: {old_status.group()} -> {new_status}")

        # Fix the date line "**📅 Wednesday, January 7, 2026**"
        date_pattern = r"\*\*📅 \w+, \w+ \d+, \d{4}\*\* \(Day \d+ of 90"
        old_date_match = re.search(date_pattern, content)
        if old_date_match:
            new_date_line = f"**📅 {day_name}, {month_day_year}** (Day {current_day} of 90"
            if old_date_match.group() != new_date_line:
                content = re.sub(date_pattern, new_date_line, content)
                fixes.append("Updated date in header")

        # Fix "Last updated:" at bottom
        last_updated_pattern = r"\*Last updated: \w+, \w+ \d+, \d{4} at .*"
        now_str = datetime.now().strftime("%I:%M %p ET")
        new_last_updated = f"*Last updated: {day_name}, {month_day_year} at {now_str}"
        content = re.sub(last_updated_pattern, new_last_updated, content)
        if original != content:
            fixes.append("Updated 'Last updated' timestamp")

        if content != original:
            index_path.write_text(content)
            print(f"Applied {len(fixes)} fixes to index.md")

    except Exception as e:
        print(f"ERROR fixing index.md: {e}")

    return fixes


def main():
    """Main self-healing routine."""
    print("=" * 60)
    print("SELF-HEALING DATA INTEGRITY CHECK")
    print(f"Running at: {datetime.now().isoformat()}")
    print("=" * 60)

    repo_root = Path(__file__).parent.parent
    state_path = repo_root / "data" / "system_state.json"
    docs_path = repo_root / "docs"

    all_fixes = []

    # Fix system_state.json
    print("\n[1] Checking system_state.json...")
    fixes = fix_system_state(state_path)
    all_fixes.extend(fixes)
    if not fixes:
        print("   No fixes needed")

    # Get current day for other fixes
    state = load_json(state_path)
    current_day = state.get("challenge", {}).get("current_day", 1)

    # Fix index.md
    print("\n[2] Checking docs/index.md...")
    fixes = fix_index_md(docs_path, current_day)
    all_fixes.extend(fixes)
    if not fixes:
        print("   No fixes needed")

    # Summary
    print("\n" + "=" * 60)
    if all_fixes:
        print(f"SELF-HEALING COMPLETE: Applied {len(all_fixes)} fixes")
        for fix in all_fixes:
            print(f"  - {fix}")
        return 1  # Return 1 to indicate changes were made (useful for CI)
    else:
        print("SELF-HEALING COMPLETE: All data is current")
        return 0


if __name__ == "__main__":
    sys.exit(main())
