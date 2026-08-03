#!/usr/bin/env python3
"""$1000/mo after-tax remittance status — ledger facts only.

Never claims target met without confirmed broker→Mercury deposits.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from src.bank.live_gate import evaluate_live_bank_gate
    from src.bank.remittance import (
        MONTHLY_AFTER_TAX_TARGET_USD,
        compute_remittance_progress,
    )
    from src.bank.transfer_ledger import load_transfer_ledger

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    p.add_argument("--ledger-path", type=Path, default=None)
    p.add_argument("--month", default=None, help="YYYY-MM (default: current UTC month)")
    p.add_argument(
        "--realized-pnl",
        type=float,
        default=None,
        help="Optional realized pre-tax P/L for after-tax estimate (not a remittance claim)",
    )
    args = p.parse_args()

    progress = compute_remittance_progress(
        load_transfer_ledger(ledger_path=args.ledger_path),
        month_yyyy_mm=args.month,
        target_usd=MONTHLY_AFTER_TAX_TARGET_USD,
        realized_pre_tax_pnl_usd=args.realized_pnl,
    )
    gate = evaluate_live_bank_gate()
    payload = {
        "target_monthly_after_tax_usd": MONTHLY_AFTER_TAX_TARGET_USD,
        "progress": progress.as_dict(),
        "live_bank_gate": {
            "allowed": gate.allowed,
            "blockers": list(gate.blockers),
            "strategy_mode": gate.strategy_mode,
        },
        "honesty": (
            "target_met requires confirmed non-dry-run broker_to_mercury ledger rows; "
            "estimated_after_tax_profit is not bank remittance"
        ),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("=== REMITTANCE STATUS ($1000/mo after-tax target) ===")
        print(f"month: {progress.month_yyyy_mm}")
        print(f"remitted_to_bank (confirmed): ${progress.remitted_to_bank_usd:.2f}")
        print(f"in_flight (submitted): ${progress.in_flight_usd:.2f}")
        print(f"target: ${progress.target_usd:.2f}")
        print(f"confirmed_events: {progress.remittance_event_count}")
        print(f"target_met: {progress.target_met} claim_allowed: {progress.claim_allowed}")
        if progress.estimated_after_tax_profit_usd is not None:
            print(f"estimated_after_tax_profit: ${progress.estimated_after_tax_profit_usd:.2f}")
        print(progress.note)
        print(f"live_bank_gate.allowed: {gate.allowed}")
        if gate.blockers:
            for b in gate.blockers:
                print(f"  block: {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
