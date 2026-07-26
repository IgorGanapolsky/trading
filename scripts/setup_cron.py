#!/usr/bin/env python3
"""Install or remove the autonomous trading scheduler as a cron job.

Usage:
  python3 scripts/setup_cron.py install    # Add cron job
  python3 scripts/setup_cron.py remove     # Remove cron job
  python3 scripts/setup_cron.py status       # Check if cron job is installed

The cron job runs the autonomous trading scheduler daily on weekdays at 11:00 AM ET
(15:00 UTC), logging output to logs/autonomous_trading.log.

Default: paper/dry-run mode. To enable live mode, edit the cron entry to add --execute.
"""

from __future__ import annotations

import argparse
import subprocess  # nosec B404
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_BIN = str(ROOT / ".venv" / "bin" / "python")
if not Path(PYTHON_BIN).is_file():
    PYTHON_BIN = sys.executable

SCRIPT = str(ROOT / "scripts" / "run_autonomous_trading.py")
LOG_FILE = str(ROOT / "logs" / "autonomous_trading.log")

# Weekday 11:00 AM ET = 15:00 UTC
CRON_SCHEDULE = "0 15 * * 1-5"
CRON_ENTRY = f"{CRON_SCHEDULE} {PYTHON_BIN} {SCRIPT} --json >> {LOG_FILE} 2>&1"
CRON_MARKER = "# autonomous-trading-scheduler"


def _get_current_crontab() -> str:
    try:
        result = subprocess.run(  # nosec
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout if result.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _set_crontab(content: str) -> bool:
    try:
        proc = subprocess.run(  # nosec
            ["crontab", "-"],
            input=content,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def install_cron() -> bool:
    current = _get_current_crontab()
    lines = [line for line in current.splitlines() if CRON_MARKER not in line]
    lines.append(f"{CRON_ENTRY} {CRON_MARKER}")
    new_content = "\n".join(lines) + "\n"
    return _set_crontab(new_content)


def remove_cron() -> bool:
    current = _get_current_crontab()
    lines = [line for line in current.splitlines() if CRON_MARKER not in line]
    new_content = "\n".join(lines)
    if new_content:
        new_content += "\n"
    return _set_crontab(new_content)


def status_cron() -> bool:
    current = _get_current_crontab()
    return CRON_MARKER in current


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["install", "remove", "status"])
    args = p.parse_args()

    if args.action == "install":
        if install_cron():
            print(f"Cron job installed: {CRON_ENTRY}")
            print(f"Logs: {LOG_FILE}")
            print("Default: paper/dry-run mode. Edit the cron entry to add --execute for live mode.")
            return 0
        else:
            print("Failed to install cron job. Is crontab available?")
            return 1
    elif args.action == "remove":
        if remove_cron():
            print("Cron job removed.")
            return 0
        else:
            print("Failed to remove cron job.")
            return 1
    elif args.action == "status":
        if status_cron():
            print("Cron job is installed:")
            current = _get_current_crontab()
            for line in current.splitlines():
                if CRON_MARKER in line:
                    print(f"  {line}")
            return 0
        else:
            print("Cron job is NOT installed.")
            return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
