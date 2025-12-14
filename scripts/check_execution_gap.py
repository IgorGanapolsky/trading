#!/usr/bin/env python3
"""
Execution Gap Detector

Detects when trading hasn't executed for too long.
Run this in CI or as a cron job to catch gaps early.

Exit codes:
    0: Healthy (recent execution)
    1: Warning (24-48 hours gap)
    2: Critical (48+ hours gap)
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


def check_execution_gap(state_file: Path = Path("data/system_state.json")) -> int:
    """Check for execution gaps and return appropriate exit code."""

    if not state_file.exists():
        print("CRITICAL: system_state.json not found!")
        return 2

    with open(state_file) as f:
        state = json.load(f)

    last_updated_str = state.get("meta", {}).get("last_updated", "")

    if not last_updated_str:
        print("CRITICAL: No last_updated timestamp in system state!")
        return 2

    # Parse timestamp
    try:
        # Handle various datetime formats
        for fmt in ["%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
            try:
                last_updated = datetime.fromisoformat(
                    last_updated_str.replace("Z", "").split("+")[0]
                )
                break
            except ValueError:
                continue
        else:
            print(f"CRITICAL: Could not parse timestamp: {last_updated_str}")
            return 2
    except Exception as e:
        print(f"CRITICAL: Error parsing timestamp: {e}")
        return 2

    now = datetime.now()
    gap = now - last_updated

    # Get additional stats
    exec_count = state.get("automation", {}).get("execution_count", 0)
    total_trades = state.get("performance", {}).get("total_trades", 0)

    print(f"Last Updated: {last_updated_str}")
    print(f"Gap: {gap}")
    print(f"Execution Count: {exec_count}")
    print(f"Total Trades: {total_trades}")
    print()

    # Determine status
    if gap > timedelta(hours=72):
        print("STATUS: CRITICAL - No execution in 72+ hours!")
        print("ACTION: Check GitHub Actions immediately")
        return 2
    elif gap > timedelta(hours=48):
        print("STATUS: WARNING - No execution in 48+ hours")
        print("ACTION: Verify workflows are running")
        return 1
    elif gap > timedelta(hours=24):
        print("STATUS: NOTICE - Gap > 24 hours (may be weekend)")
        return 0
    else:
        print("STATUS: HEALTHY - Recent execution detected")
        return 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Check for trading execution gaps")
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("data/system_state.json"),
        help="Path to system_state.json",
    )
    args = parser.parse_args()

    exit_code = check_execution_gap(args.state_file)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
