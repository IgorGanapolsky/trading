#!/usr/bin/env python3
"""Daily autonomous trading scheduler — ties together the income loop and
the put-credit cycle, then reports remittance progress.

Runs one step of each path on a schedule:
  1. mercury_income_loop.py — buy-and-hold DCA (SCHD) + dividend collection +
     profit remittance to bank. This is the non-day-trading path that avoids
     short-term capital gains tax penalties.
  2. autonomous_money_cycle.py — multi-day put-credit manage + bank transfer
     dry-run plans. Paper-only until live gate clears.

Default: paper/dry-run. Real money requires explicit --live flag AND gate
clearance. The scheduler never auto-enables live mode.

Cron example (weekday 11:00 AM ET):
  0 15 * * 1-5  .venv/bin/python scripts/run_autonomous_trading.py --json >> logs/autonomous_trading.log 2>&1

Exit codes:
  0 = cycle completed (paper or live-allowed)
  2 = live mode blocked by gate (fail-closed)
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_LOG_DIR = ROOT / "logs"
DEFAULT_STATE_PATH = ROOT / "data" / "mercury_income_loop_state.json"
DEFAULT_LEDGER_PATH = ROOT / "data" / "audit" / "mercury_broker_transfers.jsonl"


def _run(args: list[str], *, timeout: int = 180) -> dict[str, Any]:
    """Run a subprocess and capture its output (best-effort)."""
    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        proc = subprocess.run(  # nosec B603
            args,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            env=env,
        )
        return {
            "cmd": args,
            "rc": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-3000:],
            "stderr_tail": (proc.stderr or "")[-1000:],
        }
    except subprocess.TimeoutExpired:
        return {"cmd": args, "rc": 124, "stdout_tail": "", "stderr_tail": "timeout"}
    except Exception as exc:  # noqa: BLE001
        return {"cmd": args, "rc": 1, "stdout_tail": "", "stderr_tail": str(exc)}


def run_daily_cycle(
    *,
    dry_run: bool = True,
    paper_starting_balance: float = 0.0,
    bank_buffer_usd: float = 500.0,
    profit_return_threshold_usd: float = 50.0,
    tax_rate: float = 0.15,
    state_path: Path | None = None,
    ledger_path: Path | None = None,
    skip_put_credit: bool = False,
    skip_income_loop: bool = False,
) -> dict[str, Any]:
    """Run one step of the autonomous trading cycle.

    Returns a report dict with results from each step.
    """
    py = ROOT / ".venv" / "bin" / "python"
    python = str(py if py.is_file() else Path(sys.executable))
    ts = datetime.now(timezone.utc).isoformat()

    report: dict[str, Any] = {
        "schema_version": "autonomous-trading-scheduler/1",
        "ts": ts,
        "dry_run": dry_run,
        "non_day_trade": True,
        "steps": {},
    }

    # 1) Income loop (buy-and-hold DCA + dividend collection + profit remittance)
    if not skip_income_loop:
        income_args = [
            python,
            "scripts/mercury_income_loop.py",
            "--state-path", str(state_path or DEFAULT_STATE_PATH),
            "--ledger-path", str(ledger_path or DEFAULT_LEDGER_PATH),
            "--bank-buffer-usd", str(bank_buffer_usd),
            "--profit-return-threshold-usd", str(profit_return_threshold_usd),
            "--tax-rate", str(tax_rate),
        ]
        if not dry_run:
            income_args.append("--live")
        if paper_starting_balance > 0:
            income_args.extend(["--paper-starting-balance", str(paper_starting_balance)])
        income_args.append("--json")

        result = _run(income_args)
        report["steps"]["income_loop"] = {
            "rc": result["rc"],
            "stdout_tail": result["stdout_tail"][-1500:],
            "stderr_tail": result["stderr_tail"][-500:],
        }

    # 2) Put-credit cycle (multi-day holds, paper-only until gate clears)
    if not skip_put_credit:
        cycle_args = [
            python,
            "scripts/autonomous_money_cycle.py",
            *(["--dry-run"] if dry_run else []),
            "--json",
        ]
        result = _run(cycle_args)
        report["steps"]["put_credit_cycle"] = {
            "rc": result["rc"],
            "stdout_tail": result["stdout_tail"][-1500:],
            "stderr_tail": result["stderr_tail"][-500:],
        }

    # 3) Remittance status (ledger facts only)
    status_args = [
        python,
        "scripts/remittance_status.py",
        "--json",
    ]
    result = _run(status_args)
    report["steps"]["remittance_status"] = {
        "rc": result["rc"],
        "stdout_tail": result["stdout_tail"][-1500:],
        "stderr_tail": result["stderr_tail"][-500:],
    }

    # Parse remittance progress from the status output
    try:
        status_output = json.loads(result["stdout_tail"].strip().split("\n")[-1]
                                   if result["stdout_tail"].strip() else "{}")
        if isinstance(status_output, dict) and "progress" in status_output:
            report["remittance_progress"] = status_output["progress"]
    except (json.JSONDecodeError, IndexError, KeyError):
        pass

    # Save report
    log_dir = DEFAULT_LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    report_path = log_dir / f"autonomous_trading_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path)

    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Default: paper/dry-run mode. Use --execute for live (fail-closed if gate blocks).",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="Allow live paths (still fail-closed if gate blocks).",
    )
    p.add_argument("--paper-starting-balance", type=float, default=0.0)
    p.add_argument("--bank-buffer-usd", type=float, default=bank_buffer_usd if (bank_buffer_usd := 500.0) else 500.0)
    p.add_argument("--profit-return-threshold-usd", type=float, default=50.0)
    p.add_argument("--tax-rate", type=float, default=0.15)
    p.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    p.add_argument("--ledger-path", type=Path, default=DEFAULT_LEDGER_PATH)
    p.add_argument("--skip-put-credit", action="store_true")
    p.add_argument("--skip-income-loop", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    dry = not args.execute
    report = run_daily_cycle(
        dry_run=dry,
        paper_starting_balance=args.paper_starting_balance,
        bank_buffer_usd=args.bank_buffer_usd,
        profit_return_threshold_usd=args.profit_return_threshold_usd,
        tax_rate=args.tax_rate,
        state_path=args.state_path,
        ledger_path=args.ledger_path,
        skip_put_credit=args.skip_put_credit,
        skip_income_loop=args.skip_income_loop,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=== AUTONOMOUS TRADING SCHEDULER ===")
        print(f"dry_run={report['dry_run']} ts={report['ts']}")
        for step_name, step_result in report["steps"].items():
            print(f"  {step_name}: rc={step_result['rc']}")
        rp = report.get("remittance_progress", {})
        if rp:
            print(
                f"remittance: ${rp.get('remitted_to_bank_usd', 0)} / "
                f"${rp.get('target_usd', 0)} target_met={rp.get('target_met', False)}"
            )
        print(f"report: {report['report_path']}")

    if not dry and report["steps"].get("put_credit_cycle", {}).get("rc") == 2:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
