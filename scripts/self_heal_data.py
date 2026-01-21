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


def check_stale_data(state_path: Path, max_staleness_hours: float = 4.0) -> tuple[bool, list[str]]:
    """
    Check if critical data files are stale.

    Returns (is_stale, warnings)
    """
    warnings = []
    is_stale = False
    now = datetime.now()

    # Check system_state.json staleness
    state = load_json(state_path)
    last_updated = state.get("meta", {}).get("last_updated")

    if last_updated:
        try:
            # Handle ISO format with optional timezone
            if last_updated.endswith("Z"):
                last_updated = last_updated[:-1]
            updated_dt = datetime.fromisoformat(last_updated)
            hours_old = (now - updated_dt).total_seconds() / 3600

            if hours_old > max_staleness_hours:
                is_stale = True
                warnings.append(
                    f"system_state.json is {hours_old:.1f} hours old (max: {max_staleness_hours}h)"
                )
            else:
                print(
                    f"   ✅ State freshness OK: {hours_old:.1f} hours old (max: {max_staleness_hours}h)"
                )
        except Exception as e:
            warnings.append(f"Could not parse last_updated timestamp: {e}")
    else:
        warnings.append("system_state.json has no last_updated timestamp")
        is_stale = True

    # Check performance_log.json staleness
    perf_path = state_path.parent / "performance_log.json"
    if perf_path.exists():
        try:
            with open(perf_path) as f:
                perf_data = json.load(f)

            # Handle both formats: raw list or wrapped in object
            if isinstance(perf_data, list):
                entries = perf_data
            else:
                entries = perf_data.get("entries", [])

            if entries:
                latest_entry = max(entries, key=lambda x: x.get("date", ""))
                latest_date_str = latest_entry.get("date", "")

                if latest_date_str:
                    # Check if we have an entry for today (or yesterday if before market open)
                    # If market is open today and we don't have today's entry, that's OK
                    # But if latest entry is more than 2 days old, warn
                    try:
                        latest_date = datetime.fromisoformat(latest_date_str).date()
                        days_old = (date.today() - latest_date).days

                        if days_old > 2:
                            warnings.append(
                                f"performance_log.json last entry is {days_old} days old"
                            )
                    except Exception:
                        pass
        except Exception as e:
            warnings.append(f"Could not check performance_log.json: {e}")

    return is_stale, warnings


def notify_stale_data(warnings: list[str]) -> None:
    """Notify CEO about stale data if notification is configured."""
    try:
        # Import notification script
        import importlib.util

        notify_path = Path(__file__).parent / "notify_ceo.py"
        if notify_path.exists():
            spec = importlib.util.spec_from_file_location("notify_ceo", notify_path)
            notify_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(notify_module)

            message = f"""⚠️ **STALE DATA DETECTED**

The trading system has detected stale data files that may affect trading decisions.

**Issues found:**
{"".join(f"• {w}" + chr(10) for w in warnings)}

**Action required:**
1. Check if trading workflow is running
2. Verify API connectivity
3. Check for recent merge conflicts

**Impact:** Trading decisions may be based on outdated information."""

            notify_module.notify_ceo(message, alert_type="warning")
        else:
            print("   ⚠️  notify_ceo.py not found - cannot send notification")
    except Exception as e:
        print(f"   ⚠️  Could not send stale data notification: {e}")


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
    stale_warnings = []

    # Check for stale data FIRST
    print("\n[0] Checking data freshness...")
    is_stale, warnings = check_stale_data(state_path, max_staleness_hours=4.0)
    if warnings:
        for w in warnings:
            print(f"   ⚠️  {w}")
        stale_warnings.extend(warnings)

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

    if stale_warnings:
        print(f"\n⚠️  STALE DATA WARNINGS: {len(stale_warnings)} issues")
        for warning in stale_warnings:
            print(f"  - {warning}")

        # Notify CEO if data is critically stale
        if is_stale:
            print("\n🔔 Notifying CEO about stale data...")
            notify_stale_data(stale_warnings)

    if not all_fixes and not stale_warnings:
        print("SELF-HEALING COMPLETE: All data is current and fresh")
        return 0

    return 1 if all_fixes else 0  # Return 1 to indicate changes were made (useful for CI)


if __name__ == "__main__":
    sys.exit(main())
