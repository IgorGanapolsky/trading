#!/usr/bin/env python3
"""CLI: Ralph Loop 24/7 & GSD (Get Shit Done) Autonomous Trading Engine.

Commands:
  --doctor                          Health check Ralph-GSD 24/7 engine
  --tick                            Execute a single autonomous GSD cycle
  --sense                           Inspect market regime and capacity headroom
  --loop [--max-ticks N] [--sleep]  Run continuous 24/7 autonomous loop
  --json                            Format output as JSON
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ops.ralph_gsd_trading_runner import RalphGSDTradingRunner  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ralph Loop 24/7 & GSD Autonomous Trading Engine")
    parser.add_argument("--doctor", action="store_true", help="Health check Ralph-GSD engine")
    parser.add_argument("--tick", action="store_true", help="Execute single GSD trading tick")
    parser.add_argument(
        "--sense", action="store_true", help="Inspect market regime and inventory capacity"
    )
    parser.add_argument("--loop", action="store_true", help="Run continuous 24/7 autonomous loop")
    parser.add_argument(
        "--max-ticks", type=int, default=5, help="Max iterations for continuous loop"
    )
    parser.add_argument(
        "--sleep-seconds", type=float, default=1.0, help="Seconds between loop ticks"
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args(argv)

    runner = RalphGSDTradingRunner(ROOT)

    if args.doctor:
        sense = runner.sense_pipeline_state()
        plan = runner.decide_gsd_action(sense)
        state_ok = runner.state_file.parent.is_dir()
        audit_ok = runner.audit_dir.is_dir()
        ok = state_ok and audit_ok and sense["max_capacity"] == 5

        report = {
            "ok": ok,
            "status": "PASS" if ok else "FAIL",
            "framework": "ralph+gsd-24-7",
            "max_capacity_slots": sense["max_capacity"],
            "capacity_headroom": sense["capacity_headroom"],
            "regime_allowed": sense["regime_allowed"],
            "next_decided_action": plan.action_type.value,
            "state_file_ready": state_ok,
            "audit_dir_ready": audit_ok,
        }
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"=== Ralph Loop 24/7 & GSD Doctor: {report['status']} ===")
            print(
                f"  Capacity: {sense['capacity_used']}/{sense['max_capacity']} (Headroom: {sense['capacity_headroom']})"
            )
            print(
                f"  Market Regime Allowed: {sense['regime_allowed']} (VIX: {sense['vix']}, IVR: {sense['iv_rank']})"
            )
            print(f"  Next Decided Action: {plan.action_type.value.upper()}")
            print(f"  Rationale: {plan.rationale}")
        return 0 if ok else 1

    if args.sense:
        sense = runner.sense_pipeline_state()
        plan = runner.decide_gsd_action(sense)
        out = {"sense": sense, "decide": plan.to_dict()}
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print("=== Ralph SENSE & DECIDE Matrix ===")
            print(
                f"Market Snapshot: VIX {sense['vix']} | IV Rank {sense['iv_rank']}% | SPY > 200DMA: {sense['spy_above_200dma']}"
            )
            print(f"Capacity: {sense['capacity_used']} / {sense['max_capacity']} slots occupied")
            print(f"Decided Action: {plan.action_type.value.upper()} -> {plan.rationale}")
        return 0

    if args.tick:
        receipt = runner.execute_gsd_tick()
        if args.json:
            print(json.dumps(receipt.to_dict(), indent=2))
        else:
            print(f"=== Ralph GSD Tick Complete: {receipt.tick_id} ===")
            print(
                f"Action: {receipt.action_type.upper()} | Realized PnL: ${receipt.realized_pnl:.2f} | Closed: {receipt.closed_n}/30"
            )
            print(f"Receipt Hash: {receipt.receipt_hash} ({receipt.duration_ms} ms)")
            print(f"Rationale: {receipt.details.get('rationale')}")
        return 0

    if args.loop:
        print(
            f"=== Starting Ralph Loop 24/7 ({args.max_ticks} ticks, {args.sleep_seconds}s interval) ==="
        )
        for i in range(1, args.max_ticks + 1):
            receipt = runner.execute_gsd_tick()
            print(
                f"Tick {i}/{args.max_ticks}: [{receipt.action_type.upper()}] PnL: ${receipt.realized_pnl:.2f} | Hash: {receipt.receipt_hash} ({receipt.duration_ms} ms)"
            )
            if i < args.max_ticks:
                time.sleep(args.sleep_seconds)
        print("=== Ralph 24/7 Loop Cycle Completed ===")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
