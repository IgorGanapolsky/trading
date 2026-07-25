#!/usr/bin/env python3
"""Autonomous fund → trade → remit cycle (schedule-friendly).

Default: paper/dry-run only. Non–day-trading path:
  - primary: spy_put_credit multi-day holds (min 24h, 30–45 DTE)
  - optional: long-horizon buy-and-hold plan note (no PDT churn)

Live broker risk and real Mercury transfers only if live_bank gate allows
(currently refused until edge sample + kill switch clear).
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


def _run(args: list[str], *, timeout: int = 180) -> dict[str, Any]:
    proc = subprocess.run(  # nosec B603
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )
    return {
        "cmd": args,
        "rc": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-3000:],
        "stderr_tail": (proc.stderr or "")[-1000:],
    }


def run_cycle(
    *,
    dry_run: bool = True,
    fund_amount: float = 0.0,
    remit_amount: float = 0.0,
    skip_trade: bool = False,
) -> dict[str, Any]:
    from src.bank.live_gate import evaluate_live_bank_gate
    from src.bank.mercury_transfer import plan_fund_from_mercury, plan_remit_to_mercury
    from src.bank.remittance import compute_remittance_progress
    from src.bank.transfer_ledger import load_transfer_ledger
    from src.core.active_strategy import load_kill_state

    py = ROOT / ".venv" / "bin" / "python"
    python = str(py if py.is_file() else Path(sys.executable))
    ts = datetime.now(timezone.utc).isoformat()
    kill = load_kill_state()
    gate = evaluate_live_bank_gate()

    report: dict[str, Any] = {
        "schema_version": "autonomous-money-cycle/1",
        "ts": ts,
        "dry_run": dry_run,
        "strategy_mode": gate.strategy_mode,
        "non_day_trade": True,
        "active_family": kill.active_family,
        "live_gate": gate.as_dict(),
        "steps": {},
        "fund": None,
        "remit": None,
        "remittance_progress": None,
        "honesty": (
            "paper/dry-run default; live bank+trade refused until EDGE_CANDIDATE; "
            "does not claim daily profits or $1000/mo without ledger remittances"
        ),
    }

    # 1) Optional fund plan (Mercury → broker)
    if fund_amount and fund_amount > 0:
        fund = plan_fund_from_mercury(
            float(fund_amount),
            dry_run=dry_run,
            force_execute=not dry_run,
            reason="autonomous_cycle_fund",
        )
        report["fund"] = fund.as_dict()

    # 2) Trade path — paper put-credit manage / status (multi-day holds)
    if not skip_trade:
        steps = {
            "inventory": _run([python, "scripts/audit_open_inventory.py"]),
            "manage_put_credit": _run(
                [
                    python,
                    "scripts/spy_put_credit.py",
                    "--manage-exits",
                    *(["--dry-run"] if dry_run else []),
                ]
            ),
            "cohort": _run([python, "scripts/put_credit_cohort_scorecard.py", "--json"]),
            "status": _run([python, "scripts/spy_put_credit.py", "--status"]),
        }
        report["steps"] = {k: {"rc": v["rc"], "stdout_tail": v["stdout_tail"][-800:]} for k, v in steps.items()}

        # Live new risk only if gate allows (will refuse under current kill switch)
        if not dry_run and gate.live_trading_allowed:
            entry = _run([python, "scripts/spy_put_credit.py", "--execute-paper"])
            report["steps"]["live_or_paper_entry"] = {
                "rc": entry["rc"],
                "note": "execute-paper only; --live never auto-enabled here",
            }
        elif not dry_run and not gate.live_trading_allowed:
            report["steps"]["live_entry"] = {
                "rc": 2,
                "blocked": True,
                "blockers": list(gate.blockers),
            }

    # 3) Remit plan (broker → Mercury)
    if remit_amount and remit_amount > 0:
        if dry_run:
            remit = plan_remit_to_mercury(
                float(remit_amount), dry_run=True, reason="autonomous_cycle_remit"
            )
        else:
            remit = plan_remit_to_mercury(
                float(remit_amount),
                dry_run=False,
                force_execute=True,
                reason="autonomous_cycle_remit",
            )
        report["remit"] = remit.as_dict()

    # 4) Remittance progress (ledger facts only)
    progress = compute_remittance_progress(load_transfer_ledger())
    report["remittance_progress"] = progress.as_dict()

    out_dir = ROOT / "data" / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "autonomous_money_cycle_latest.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["report_path"] = str(out_path)
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Default: dry-run bank plans + paper-safe trade steps",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="Allow real bank/live paths (still fail-closed if gate blocks)",
    )
    p.add_argument("--fund", type=float, default=0.0, help="Plan fund amount Mercury→broker")
    p.add_argument("--remit", type=float, default=0.0, help="Plan remit amount broker→Mercury")
    p.add_argument("--skip-trade", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    dry = not args.execute
    report = run_cycle(
        dry_run=dry,
        fund_amount=args.fund,
        remit_amount=args.remit,
        skip_trade=args.skip_trade,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=== AUTONOMOUS MONEY CYCLE ===")
        print(f"dry_run={report['dry_run']} strategy_mode={report['strategy_mode']}")
        print(f"live_gate.allowed={report['live_gate']['allowed']}")
        if report["live_gate"]["blockers"]:
            print("blockers:")
            for b in report["live_gate"]["blockers"]:
                print(f"  - {b}")
        if report.get("fund"):
            print("fund:", report["fund"].get("message"))
        if report.get("remit"):
            print("remit:", report["remit"].get("message"))
        rp = report.get("remittance_progress") or {}
        print(
            f"remittance: ${rp.get('remitted_to_bank_usd')} / "
            f"${rp.get('target_usd')} target_met={rp.get('target_met')}"
        )
        print(rp.get("note"))
        print("report:", report.get("report_path"))
    # Exit 0 on successful dry-run cycle; 2 if execute mode fully blocked
    if not dry and not report["live_gate"]["allowed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
