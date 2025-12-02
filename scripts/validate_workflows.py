#!/usr/bin/env python3
"""
Workflow Validation Script

Tests the validation logic used in GitHub Actions workflows locally.
Run this before pushing changes to ensure validations work correctly.

Usage:
    python scripts/validate_workflows.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
WATCHLIST_FILE = BASE_DIR / "data" / "tier2_watchlist.json"
SYSTEM_STATE_FILE = BASE_DIR / "data" / "system_state.json"


def validate_watchlist():
    """Validate tier2_watchlist.json (same logic as GitHub Actions)"""
    print("=" * 60)
    print("🔍 Validating tier2_watchlist.json...")
    print("=" * 60)

    if not WATCHLIST_FILE.exists():
        print("❌ ERROR: tier2_watchlist.json not found!")
        return False

    try:
        with open(WATCHLIST_FILE) as f:
            data = json.load(f)

        # Check structure
        assert "meta" in data, "Missing meta section"
        assert "current_holdings" in data or "watchlist" in data, "Missing holdings/watchlist"

        # Check staleness (warn if > 7 days old)
        last_updated = data["meta"].get("last_updated", "")
        if last_updated:
            updated_date = (
                datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                if "T" in last_updated
                else datetime.strptime(last_updated, "%Y-%m-%d")
            )
            age_days = (datetime.now() - updated_date.replace(tzinfo=None)).days

            if age_days > 7:
                print(
                    f"⚠️  WARNING: Watchlist is {age_days} days old (last updated: {last_updated})"
                )
            else:
                print(f"✅ Watchlist age: {age_days} days (last updated: {last_updated})")

        # Count stocks
        holdings_count = len(data.get("current_holdings", []))
        watchlist_count = len(data.get("watchlist", []))
        total = holdings_count + watchlist_count

        print("✅ Valid watchlist JSON")
        print(f"   - Current holdings: {holdings_count}")
        print(f"   - Watchlist stocks: {watchlist_count}")
        print(f"   - Total tracked: {total}")

        # Warn if empty but allow execution
        if total == 0:
            print("⚠️  WARNING: Watchlist is empty (no stocks tracked)")
            print("   Trading will proceed with fallback strategy")

        return True

    except Exception as e:
        print(f"❌ Invalid watchlist JSON: {e}")
        return False


def validate_system_state():
    """Validate system_state.json (same logic as GitHub Actions)"""
    print("\n" + "=" * 60)
    print("🔍 Validating system_state.json...")
    print("=" * 60)

    if not SYSTEM_STATE_FILE.exists():
        print("⚠️  WARNING: system_state.json not found (will be created on first run)")
        return True  # Not a failure

    try:
        with open(SYSTEM_STATE_FILE) as f:
            data = json.load(f)

        # Check staleness
        last_updated = data.get("meta", {}).get("last_updated", "")
        if last_updated:
            updated_date = (
                datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                if "T" in last_updated
                else datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")
            )
            age_hours = (datetime.now() - updated_date.replace(tzinfo=None)).total_seconds() / 3600

            if age_hours > 48:
                print(f"⚠️  WARNING: system_state.json is {age_hours:.1f} hours old")
                print(f"   Last updated: {last_updated}")
            else:
                print(f"✅ System state current (updated {age_hours:.1f} hours ago)")

        print("✅ Valid system_state.json")
        return True

    except Exception as e:
        print(f"⚠️  WARNING: Could not validate system_state.json: {e}")
        print("   Trading will proceed (state will be regenerated)")
        return True  # Warning, not failure


def validate_workflows():
    """Validate all GitHub Actions workflows exist"""
    print("\n" + "=" * 60)
    print("🔍 Validating GitHub Actions workflows...")
    print("=" * 60)

    workflows_dir = BASE_DIR / ".github" / "workflows"
    required_workflows = ["youtube-analysis.yml", "daily-trading.yml"]

    all_exist = True
    for workflow in required_workflows:
        workflow_file = workflows_dir / workflow
        if workflow_file.exists():
            print(f"✅ {workflow} exists")
        else:
            print(f"❌ {workflow} NOT FOUND")
            all_exist = False

    return all_exist


def main():
    """Run all validations"""
    print("\n" + "=" * 70)
    print("🚀 WORKFLOW VALIDATION SCRIPT")
    print("=" * 70)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    results = {
        "watchlist": validate_watchlist(),
        "system_state": validate_system_state(),
        "workflows": validate_workflows(),
    }

    # Summary
    print("\n" + "=" * 70)
    print("📊 VALIDATION SUMMARY")
    print("=" * 70)

    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name.upper()}: {status}")

    print("=" * 70)

    # Exit code
    if all(results.values()):
        print("\n✅ All validations passed - ready for GitHub Actions!")
        return 0
    else:
        print("\n❌ Some validations failed - fix errors before deploying")
        return 1


if __name__ == "__main__":
    sys.exit(main())
