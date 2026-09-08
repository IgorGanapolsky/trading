#!/usr/bin/env python3
"""CLI for put-credit entry challenge matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.risk.entry_challenge_matrix import evaluate_entry_challenges  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--paper", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--active-family", default="spy_put_credit")
    p.add_argument("--live-blocked", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--ic-entries-killed", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--inventory-clean", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--iv-rank-proxy", type=float, default=None)
    p.add_argument("--min-iv-rank", type=float, default=30.0)
    p.add_argument("--lot-size", type=int, default=1)
    p.add_argument("--open-put-credits", type=int, default=0)
    p.add_argument("--structures-today", type=int, default=0)
    args = p.parse_args(argv)
    snap = {
        "paper": args.paper,
        "trading_mode": "paper" if args.paper else "live",
        "active_family": args.active_family,
        "live_blocked": args.live_blocked,
        "ic_entries_killed": args.ic_entries_killed,
        "inventory_clean": args.inventory_clean,
        "iv_rank_proxy": args.iv_rank_proxy,
        "min_iv_rank": args.min_iv_rank,
        "lot_size": args.lot_size,
        "open_put_credits": args.open_put_credits,
        "structures_today": args.structures_today,
    }
    result = evaluate_entry_challenges(snap)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
