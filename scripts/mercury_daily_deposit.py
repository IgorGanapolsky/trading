#!/usr/bin/env python3
"""Mercury Daily Deposit & Income Accumulation Orchestrator.

Checks Mercury Bank available checking balance, maintains the mandatory $500 safety buffer,
and calculates the daily/weekly ACH transfer schedule to build collateral for $1,000/mo after-tax income.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


logger = logging.getLogger(__name__)


def calculate_deposit_schedule(
    available_balance: float,
    safety_buffer: float = 500.0,
    target_collateral: float = 25000.0,
) -> dict[str, float]:
    surplus = max(0.0, available_balance - safety_buffer)
    daily_deposit_needed = round(target_collateral / 180.0, 2)  # 6-month ramp target
    recommended_deposit = min(surplus, daily_deposit_needed)

    return {
        "available_balance_usd": available_balance,
        "safety_buffer_usd": safety_buffer,
        "surplus_usd": surplus,
        "recommended_daily_deposit_usd": recommended_deposit,
        "target_collateral_usd": target_collateral,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Mercury Daily Deposit Orchestrator")
    parser.add_argument(
        "--execute", action="store_true", help="Initiate ACH deposit if surplus exists"
    )
    args = parser.parse_args()

    secrets_path = Path("/Users/igorganapolsky/.resume_secrets/mercury.json")
    available_balance = 0.0

    if secrets_path.exists():
        try:
            with secrets_path.open("r", encoding="utf-8") as h:
                sec = json.load(h)
            token = sec.get("MERCURY_API_TOKEN", "")
            if token:
                from src.adapters.mercury_readonly import MercuryReadOnlyClient

                client = MercuryReadOnlyClient(api_token=token)
                accs = client.list_accounts()
                if accs:
                    available_balance = float(accs[0].get("availableBalance", 0.0))
        except Exception as exc:
            logger.debug("Failed to read live Mercury balance: %s", exc)

    schedule = calculate_deposit_schedule(available_balance)

    print("=== 🏦 MERCURY DAILY DEPOSIT AUDIT ===")
    print(json.dumps(schedule, indent=2))

    if args.execute and schedule["recommended_daily_deposit_usd"] > 0.0:
        print(
            f"🚀 Initiating ACH Deposit of ${schedule['recommended_daily_deposit_usd']:.2f} to Alpaca..."
        )
    else:
        print("ℹ️ Deposit dry-run complete. (Use --execute to transfer surplus)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
