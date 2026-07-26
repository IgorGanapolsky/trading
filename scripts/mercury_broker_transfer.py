#!/usr/bin/env python3
"""CLI: plan Mercury ↔ brokerage transfers (dry-run default)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from src.bank.mercury_transfer import plan_transfer

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--direction",
        choices=["fund", "remit", "mercury_to_broker", "broker_to_mercury"],
        required=True,
    )
    p.add_argument("--amount", type=float, required=True)
    p.add_argument(
        "--execute",
        action="store_true",
        help="Attempt real transfer (fail-closed unless gates + Mercury API ready)",
    )
    p.add_argument("--reason", default="")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    dry = not args.execute
    direction = args.direction
    if direction == "fund":
        direction = "mercury_to_broker"
    elif direction == "remit":
        direction = "broker_to_mercury"

    result = plan_transfer(
        direction=direction,
        amount_usd=args.amount,
        dry_run=dry,
        force_execute=bool(args.execute),
        reason=args.reason,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(result.message)
        print(json.dumps(result.record, indent=2))
    # dry-run ok → 0; blocked real attempt → 2; other failure → 1
    if result.blocked:
        return 2
    if result.ok:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
