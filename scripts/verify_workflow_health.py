#!/usr/bin/env python3
"""Verify GitHub Actions workflow health and trigger re-enable if needed.

This script is designed to be run locally to check if critical workflows are enabled
and have been executing as expected. It can help diagnose automation gaps.

Usage:
    python scripts/verify_workflow_health.py

Returns exit code:
    0 - All workflows healthy
    1 - Issues detected (see output for details)
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def check_system_state_freshness(max_age_hours: int = 48) -> tuple[bool, str]:
    """Check if system_state.json has been updated recently.

    Args:
        max_age_hours: Maximum acceptable age in hours

    Returns:
        Tuple of (is_fresh, message)
    """
    state_file = Path("data/system_state.json")

    if not state_file.exists():
        return False, "system_state.json not found"

    try:
        with open(state_file) as f:
            state = json.load(f)

        last_updated = state.get("meta", {}).get("last_updated", "")
        if not last_updated:
            return False, "No last_updated timestamp in system_state.json"

        # Parse timestamp
        if "T" in last_updated:
            updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        else:
            updated_dt = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")

        # Make it timezone-naive for comparison
        if updated_dt.tzinfo:
            updated_dt = updated_dt.replace(tzinfo=None)

        age = datetime.now() - updated_dt
        age_hours = age.total_seconds() / 3600

        if age_hours > max_age_hours:
            return False, f"State is {age_hours:.1f} hours old (threshold: {max_age_hours}h)"

        return True, f"State updated {age_hours:.1f} hours ago"

    except Exception as e:
        return False, f"Error reading system_state.json: {e}"


def check_tier5_execution() -> tuple[bool, str]:

    Returns:
        Tuple of (has_executed, message)
    """
    state_file = Path("data/system_state.json")

    if not state_file.exists():
        return False, "system_state.json not found"

    try:
        with open(state_file) as f:
            state = json.load(f)

        tier5 = state.get("strategies", {}).get("tier5", {})
        trades_executed = tier5.get("trades_executed", 0)
        last_execution = tier5.get("last_execution")

        if trades_executed == 0:

        return True, f"Tier 5 has {trades_executed} trades, last: {last_execution}"

    except Exception as e:
        return False, f"Error checking Tier 5: {e}"


def check_automation_status() -> tuple[bool, str]:
    """Check automation section of system_state.json.

    Returns:
        Tuple of (is_healthy, message)
    """
    state_file = Path("data/system_state.json")

    if not state_file.exists():
        return False, "system_state.json not found"

    try:
        with open(state_file) as f:
            state = json.load(f)

        automation = state.get("automation", {})

        if not automation.get("github_actions_enabled"):
            return False, "GitHub Actions marked as disabled"

        last_attempt = automation.get("last_execution_attempt", "")
        failures = automation.get("failures", 0)

        # Check if last attempt was recent
        if last_attempt:
            try:
                if "T" in last_attempt:
                    attempt_dt = datetime.fromisoformat(last_attempt.replace("Z", "+00:00"))
                else:
                    attempt_dt = datetime.strptime(last_attempt, "%Y-%m-%d %H:%M:%S")

                if attempt_dt.tzinfo:
                    attempt_dt = attempt_dt.replace(tzinfo=None)

                days_since = (datetime.now() - attempt_dt).days

                if days_since > 7:
                    return False, f"Last execution attempt was {days_since} days ago"
            except Exception:
                pass

        return True, f"Automation enabled, {failures} failures recorded"

    except Exception as e:
        return False, f"Error checking automation: {e}"


def main():
    """Run all health checks and report status."""
    print("=" * 60)
    print("WORKFLOW HEALTH CHECK")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("-" * 60)

    all_healthy = True

    # Check 1: System state freshness
    print("\n1. System State Freshness")
    fresh, msg = check_system_state_freshness(max_age_hours=72)
    print(f"   {'✅' if fresh else '❌'} {msg}")
    if not fresh:
        all_healthy = False

    executed, msg = check_tier5_execution()
    print(f"   {'✅' if executed else '⚠️'} {msg}")
    if not executed:
        print("   → This may indicate workflow is disabled or misconfigured")

    # Check 3: Automation status
    print("\n3. Automation Status")
    healthy, msg = check_automation_status()
    print(f"   {'✅' if healthy else '❌'} {msg}")
    if not healthy:
        all_healthy = False

    # Summary
    print("\n" + "=" * 60)
    if all_healthy:
        print("✅ OVERALL: Workflows appear healthy")
    else:
        print("❌ OVERALL: Issues detected - investigate workflows")
        print("\nRecommended Actions:")
        print("1. Go to GitHub repo → Actions tab")
        print("2. Check if 'Daily Trading Execution' is enabled")
        print("4. If disabled, click 'Enable workflow' button")
        print("5. Manually trigger a workflow run to test")

    print("=" * 60)

    return 0 if all_healthy else 1


if __name__ == "__main__":
    sys.exit(main())
