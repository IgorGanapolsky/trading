#!/usr/bin/env python3
"""Pi (pi.dev) deterministic CLI bridge for trading operations.

Provides structured JSON and plain-text outputs specifically formatted for Pi
agent sessions, prompt templates (/status, /dryrun, /exits, /scorecard), and
headless automation sweeps.

Usage:
  python scripts/pi_trading_bridge.py status
  python scripts/pi_trading_bridge.py dry-run
  python scripts/pi_trading_bridge.py manage-exits
  python scripts/pi_trading_bridge.py scorecard
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PYTHON_BIN = ROOT / ".venv" / "bin" / "python"
if not PYTHON_BIN.is_file():
    PYTHON_BIN = Path(sys.executable)


def run_subcommand(args: list[str]) -> tuple[int, str, str]:
    """Execute a local Python script in the repository venv."""
    cmd = [str(PYTHON_BIN)] + args
    res = subprocess.run(  # nosec B603
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return res.returncode, res.stdout, res.stderr


def get_status() -> dict[str, Any]:
    """Get system health and inventory status."""
    _, stdout_audit, _ = run_subcommand(["scripts/audit_open_inventory.py"])
    _, stdout_status, _ = run_subcommand(["scripts/spy_put_credit.py", "--status"])

    system_state_path = ROOT / "data" / "system_state.json"
    system_state: dict[str, Any] = {}
    if system_state_path.is_file():
        try:
            system_state = json.loads(system_state_path.read_text(encoding="utf-8"))
        except Exception:
            system_state = {}

    portfolio = system_state.get("portfolio", {})
    paper = system_state.get("paper_account", {})

    return {
        "status": "ok",
        "equity": portfolio.get("equity", paper.get("equity", 0.0)),
        "cash": portfolio.get("cash", paper.get("cash", 0.0)),
        "positions_count": len(system_state.get("positions", [])),
        "positions": system_state.get("positions", []),
        "inventory_audit": stdout_audit.strip(),
        "strategy_status": stdout_status.strip(),
    }


def get_dry_run() -> dict[str, Any]:
    """Run SPY put credit dry-run planning."""
    code, stdout, stderr = run_subcommand(["scripts/spy_put_credit.py", "--dry-run"])
    return {
        "exit_code": code,
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
        "regime_passed": code == 0,
    }


def manage_exits() -> dict[str, Any]:
    """Run exit management dry-run."""
    code, stdout, stderr = run_subcommand(
        ["scripts/spy_put_credit.py", "--manage-exits", "--dry-run"]
    )
    return {
        "exit_code": code,
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
    }


def get_scorecard() -> dict[str, Any]:
    """Get put-credit cohort scorecard."""
    _, stdout, _ = run_subcommand(["scripts/put_credit_cohort_scorecard.py", "--json"])
    try:
        return json.loads(stdout)
    except Exception:
        return {"raw_output": stdout.strip()}


def main() -> int:
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    parser = argparse.ArgumentParser(
        description="Pi Coding Agent Bridge for Trading Ops", parents=[common_parser]
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "status", help="Get system health and open inventory", parents=[common_parser]
    )
    subparsers.add_parser(
        "dry-run", help="Run SPY put credit opportunity planning", parents=[common_parser]
    )
    subparsers.add_parser(
        "manage-exits",
        help="Check and manage position profit targets / stops",
        parents=[common_parser],
    )
    subparsers.add_parser(
        "scorecard", help="Get statistical validation scorecard", parents=[common_parser]
    )

    args = parser.parse_args()

    if args.command == "status":
        data = get_status()
    elif args.command == "dry-run":
        data = get_dry_run()
    elif args.command == "manage-exits":
        data = manage_exits()
    elif args.command == "scorecard":
        data = get_scorecard()
    else:
        parser.print_help()
        return 1

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        if args.command == "status":
            print("=== PI TRADING BRIDGE: SYSTEM STATUS ===")
            print(f"Equity: ${data.get('equity', 0.0):,.2f} | Cash: ${data.get('cash', 0.0):,.2f}")
            print(f"Active Positions: {data.get('positions_count', 0)}")
            print("\n--- Strategy Status ---")
            print(data.get("strategy_status", ""))
        elif args.command == "dry-run":
            print("=== PI TRADING BRIDGE: DRY RUN PLAN ===")
            print(f"Regime Gate Passed: {data.get('regime_passed')}")
            print(data.get("stdout", ""))
        elif args.command == "manage-exits":
            print("=== PI TRADING BRIDGE: EXIT MANAGEMENT ===")
            print(data.get("stdout", ""))
        elif args.command == "scorecard":
            print("=== PI TRADING BRIDGE: COHORT SCORECARD ===")
            print(json.dumps(data, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
