#!/usr/bin/env python3
"""Fallback script to add performance log entry when Alpaca sync fails."""

import json
from datetime import datetime
from pathlib import Path


def main():
    perf_file = Path("data/performance_log.json")
    state_file = Path("data/system_state.json")

    if perf_file.exists():
        with open(perf_file) as f:
            perf_data = json.load(f)
    else:
        perf_data = []

    today = datetime.now().strftime("%Y-%m-%d")
    if any(p.get("date") == today for p in perf_data):
        print(f"Entry for {today} already exists")
        return

    equity = 5000.0
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)
            equity = state.get("paper_account", {}).get("equity", 5000.0)

    new_entry = {
        "date": today,
        "equity": equity,
        "daily_pl": 0.0,
        "total_pl": equity - 5000.0,
        "note": "Fallback entry - Alpaca sync unavailable",
    }
    perf_data.append(new_entry)

    with open(perf_file, "w") as f:
        json.dump(perf_data, f, indent=2)
    print(f"Added fallback entry for {today}")


if __name__ == "__main__":
    main()
