#!/usr/bin/env python3
"""Mercury Auto-Allocation & Sub-Account Router CLI.

Calculates and executes Mercury auto-transfer rules based on incoming business revenue,
reserving 20% for taxes, holding $500 operating buffer, and routing collateral to Alpaca.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.adapters.mercury_auto_allocator import MercuryAutoAllocator

logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Mercury Sub-Account Auto-Allocation CLI")
    parser.add_argument(
        "--revenue", type=float, default=0.0, help="Incoming business revenue (USD)"
    )
    parser.add_argument(
        "--checking-balance",
        type=float,
        default=0.0,
        help="Available Mercury checking balance (USD)",
    )
    parser.add_argument("--execute", action="store_true", help="Save allocation plan to state")
    args = parser.parse_args()

    allocator = MercuryAutoAllocator()
    plan = allocator.plan_allocation(
        incoming_revenue_usd=args.revenue, available_checking_usd=args.checking_balance
    )

    print("=== 🏦 MERCURY SUB-ACCOUNT AUTO-ALLOCATION PLAN ===")
    print(json.dumps(asdict(plan), indent=2))

    if args.execute:
        saved_path = allocator.save_allocation_state(plan)
        print(f"\n✅ Allocation plan state saved to {saved_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
