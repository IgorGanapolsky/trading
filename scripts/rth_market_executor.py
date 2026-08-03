#!/usr/bin/env python3
"""Regular Trading Hours (RTH) Market Execution Orchestrator.

Executed every 30 minutes. Checks exchange calendar and RTH bounds (09:30 - 16:00 ET Mon-Fri).
During market hours, runs:
  1. sync_alpaca_state.py
  2. audit_open_inventory.py
  3. spy_put_credit.py --manage-exits
  4. mercury_income_loop.py
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.calendar_validation import is_trading_day

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")
LOG_PATH = ROOT / "data" / "audit" / "rth_execution_log.json"


def is_regular_trading_hours(now_et: datetime) -> bool:
    """Return True if now_et falls within 09:30 - 16:00 ET on a valid trading day."""
    if not is_trading_day(now_et):
        return False
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now_et <= market_close


def run_script(script_name: str, args: list[str] | None = None) -> dict[str, Any]:
    cmd = [sys.executable, str(ROOT / "scripts" / script_name)] + (args or [])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        return {
            "script": script_name,
            "exit_code": res.returncode,
            "stdout": res.stdout[:500],
            "stderr": res.stderr[:500],
        }
    except Exception as exc:
        return {"script": script_name, "exit_code": -1, "error": str(exc)}


def append_audit_log(entry: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logs = []
    if LOG_PATH.exists():
        try:
            with LOG_PATH.open("r", encoding="utf-8") as h:
                logs = json.load(h)
        except Exception:
            logs = []
    logs.append(entry)

    # Keep last 100 execution records
    with LOG_PATH.open("w", encoding="utf-8") as h:
        json.dump(logs[-100:], h, indent=2)


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    now_et = datetime.now(tz=ET)
    in_rth = is_regular_trading_hours(now_et)

    audit_entry = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "timestamp_et": now_et.isoformat(),
        "in_rth": in_rth,
        "actions": [],
    }

    if not in_rth:
        logger.info(
            "Outside Regular Trading Hours (%s ET). Skipping execution.",
            now_et.strftime("%Y-%m-%d %H:%M:%S"),
        )
        audit_entry["status"] = "SKIPPED_OUTSIDE_RTH"
        append_audit_log(audit_entry)
        print(json.dumps(audit_entry, indent=2))
        return 0

    logger.info("Executing Market Hours RTH Tasks (%s ET)...", now_et.strftime("%Y-%m-%d %H:%M:%S"))

    # Task 1: Sync Alpaca State
    audit_entry["actions"].append(run_script("sync_alpaca_state.py"))

    # Task 2: Audit Open Inventory
    audit_entry["actions"].append(run_script("audit_open_inventory.py"))

    # Task 3: Manage Options Exits
    audit_entry["actions"].append(run_script("spy_put_credit.py", ["--manage-exits"]))

    # Task 4: Mercury Income Loop
    audit_entry["actions"].append(run_script("mercury_income_loop.py", ["--mode", "paper"]))

    audit_entry["status"] = "EXECUTED_RTH_TASKS"
    append_audit_log(audit_entry)
    print(json.dumps(audit_entry, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
