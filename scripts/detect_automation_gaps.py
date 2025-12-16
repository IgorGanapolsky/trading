#!/usr/bin/env python3
"""
Detect Automation Gaps - Prevent revenue leakage from manual processes.

This script identifies profit-generating activities that lack automation,
preventing situations like options trading being manual while generating
100x more profit than automated DCA.

Run: python3 scripts/detect_automation_gaps.py
Schedule: Weekly via cron or CI

Lesson Learned: ll_022_options_not_automated_dec12.md
"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Profit sources that MUST be automated
REQUIRED_AUTOMATIONS = {
    "equity_dca": {
        "workflow_pattern": r"autonomous_trader\.py|TradingOrchestrator",
        "workflow_file": ".github/workflows/daily-trading.yml",
        "staleness_key": "automation.last_successful_execution",
        "max_staleness_hours": 48,
        "description": "Daily equity DCA trading",
    },
    "options_theta": {
        "workflow_pattern": r"theta|options_profit_planner|execute_options_trade|wheel",
        "workflow_file": ".github/workflows/daily-trading.yml",
        "staleness_key": "options.last_theta_harvest",
        "max_staleness_hours": 48,
        "description": "Options theta harvesting (wheel strategy)",
    },
}


def check_workflow_coverage(workflow_file: str, pattern: str) -> bool:
    """Check if a workflow file contains the required automation pattern."""
    workflow_path = Path(workflow_file)
    if not workflow_path.exists():
        return False

    content = workflow_path.read_text()
    return bool(re.search(pattern, content, re.IGNORECASE))


def get_nested_value(data: dict, key_path: str) -> str | None:
    """Get a nested value from a dict using dot notation."""
    keys = key_path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value


def check_staleness(system_state: dict, staleness_key: str, max_hours: int) -> tuple[bool, str]:
    """Check if an automation is stale based on last execution timestamp."""
    timestamp_str = get_nested_value(system_state, staleness_key)

    if not timestamp_str:
        return True, f"No timestamp found at {staleness_key}"

    try:
        # Handle various timestamp formats
        if "T" in str(timestamp_str):
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            timestamp = timestamp.replace(tzinfo=None)
        else:
            timestamp = datetime.strptime(str(timestamp_str), "%Y-%m-%d %H:%M:%S")

        age = datetime.now() - timestamp
        if age > timedelta(hours=max_hours):
            return True, f"Last run {age.days}d {age.seconds // 3600}h ago (max: {max_hours}h)"
        return False, f"Last run {age.days}d {age.seconds // 3600}h ago (OK)"
    except Exception as e:
        return True, f"Cannot parse timestamp: {e}"


def main():
    print("=" * 60)
    print("AUTOMATION GAP DETECTION")
    print("=" * 60)
    print()

    # Load system state
    state_file = Path("data/system_state.json")
    if state_file.exists():
        with open(state_file) as f:
            system_state = json.load(f)
    else:
        system_state = {}
        print("WARNING: system_state.json not found")

    gaps_found = []

    for automation_name, config in REQUIRED_AUTOMATIONS.items():
        print(f"Checking: {automation_name}")
        print(f"  Description: {config['description']}")

        # Check workflow coverage
        has_coverage = check_workflow_coverage(config["workflow_file"], config["workflow_pattern"])

        if not has_coverage:
            gap = f"  [GAP] Not in workflow: {config['workflow_file']}"
            print(gap)
            gaps_found.append(
                {
                    "automation": automation_name,
                    "issue": "missing_workflow_coverage",
                    "detail": f"Pattern '{config['workflow_pattern']}' not found in {config['workflow_file']}",
                }
            )
        else:
            print("  [OK] Workflow coverage found")

        # Check staleness
        is_stale, staleness_msg = check_staleness(
            system_state, config["staleness_key"], config["max_staleness_hours"]
        )

        if is_stale:
            gap = f"  [STALE] {staleness_msg}"
            print(gap)
            gaps_found.append(
                {"automation": automation_name, "issue": "stale_execution", "detail": staleness_msg}
            )
        else:
            print(f"  [OK] {staleness_msg}")

        print()

    # Summary
    print("=" * 60)
    if gaps_found:
        print(f"GAPS FOUND: {len(gaps_found)}")
        print()
        for gap in gaps_found:
            print(f"  - {gap['automation']}: {gap['issue']}")
            print(f"    {gap['detail']}")
        print()
        print("ACTION REQUIRED: Fix automation gaps to prevent revenue leakage")
        sys.exit(1)
    else:
        print("ALL AUTOMATIONS VERIFIED")
        print("No gaps detected.")
        sys.exit(0)


if __name__ == "__main__":
    main()
