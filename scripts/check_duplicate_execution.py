#!/usr/bin/env python3
"""
Check if trading has already been executed today.

This script checks the system_state.json file to determine if trading
has already been executed today. It writes the result to GitHub Actions
output file for conditional workflow execution.

Exit codes:
    0: Success (skip=true or skip=false determined)
    1: Error reading or parsing system_state.json
"""

import json
import os
import sys
from datetime import datetime, timezone


def main():
    state_path = "data/system_state.json"
    skip = False
    reason = ""

    today = datetime.now(timezone.utc).date()
    force_trade = os.getenv("FORCE_TRADE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "force",
    }

    if os.path.exists(state_path):
        try:
            with open(state_path, encoding="utf-8") as f:
                data = json.load(f)

            # CRITICAL: Check last_trade_date, NOT last_updated
            # last_updated changes whenever ANY workflow touches the file
            # last_trade_date only changes when actual trades execute
            last_trade = data.get("trades", {}).get("last_trade_date")
            if last_trade:
                try:
                    # Support both ISO and "YYYY-MM-DD" formats
                    if "T" in last_trade:
                        last_dt = datetime.fromisoformat(last_trade.replace("Z", "+00:00"))
                    else:
                        last_dt = datetime.strptime(last_trade, "%Y-%m-%d")

                    if last_dt.date() == today:
                        skip = True
                        reason = f"Trading already executed today at {last_dt.isoformat()}"
                    else:
                        reason = (
                            f"Last trade was {last_dt.date()}, proceeding with today's trade"
                        )
                except ValueError as e:
                    reason = f"Could not parse last_trade_date timestamp: {e}"
            else:
                reason = "No last_trade_date recorded - first trade or data reset"
        except json.JSONDecodeError as e:
            print(f"❌ Error: Invalid JSON in system_state.json: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"❌ Error: Unable to inspect system_state.json: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        reason = "system_state.json not found (first run)"

    if force_trade and skip:
        skip = False
        reason = "Forced execution requested via FORCE_TRADE flag"
    elif not skip and not reason:
        reason = "No previous execution recorded for today"

    # Write to GitHub Actions output file
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        try:
            with open(output_path, "a", encoding="utf-8") as fh:
                fh.write(f"skip={'true' if skip else 'false'}\n")
                if reason:
                    # Escape newlines and special characters for GitHub Actions
                    safe_reason = reason.replace("\n", " ").replace("\r", "")
                    fh.write(f"skip_reason={safe_reason}\n")
        except Exception as e:
            print(f"❌ Error: Could not write to GITHUB_OUTPUT: {e}", file=sys.stderr)
            sys.exit(1)

    # Print result for workflow logs
    print(f"skip={'true' if skip else 'false'}")
    if reason:
        if skip:
            print(f"⚠️  {reason}")
        else:
            print(f"✅ {reason}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
