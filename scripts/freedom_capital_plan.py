#!/usr/bin/env python3
"""Freedom Number + 3-bucket capital jobs + 30-day sprint CLI.

Process steal from income bootcamps — not stock picks.

Usage:
  .venv/bin/python scripts/freedom_capital_plan.py --monthly 6000 --liquid 100000
  .venv/bin/python scripts/freedom_capital_plan.py --from-system-state
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analytics.freedom_capital_plan import (  # noqa: E402
    DEFAULT_MONTHLY_AFTER_TAX,
    build_freedom_capital_report,
    compute_freedom_number,
)

SYSTEM_STATE = ROOT / "data" / "system_state.json"
DEFAULT_OUT = ROOT / "data" / "audit" / "freedom_capital_plan_latest.json"


def _paper_equity_from_state(path: Path) -> float | None:
    if not path.is_file():
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for key in ("paper_account", "portfolio", "account"):
        block = d.get(key)
        if isinstance(block, dict):
            for k in ("equity", "current_equity", "portfolio_value"):
                if block.get(k) is not None:
                    try:
                        return float(block[k])
                    except (TypeError, ValueError):
                        pass
    return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--monthly", type=float, default=DEFAULT_MONTHLY_AFTER_TAX)
    p.add_argument(
        "--liquid", type=float, default=None, help="Total liquid capital across ops+lab+field"
    )
    p.add_argument("--from-system-state", action="store_true")
    p.add_argument("--paper-equity", type=float, default=None)
    p.add_argument("--day", type=int, default=1, help="Day index in 30-day sprint (1-30)")
    p.add_argument("--edge-candidate", action="store_true")
    p.add_argument("--tax-reserve", type=float, default=0.30)
    p.add_argument("--yield", dest="yield_annual", type=float, default=0.08)
    p.add_argument("--ops-frac", type=float, default=0.40)
    p.add_argument("--lab-frac", type=float, default=0.35)
    p.add_argument("--field-frac", type=float, default=0.25)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--number-only", action="store_true")
    args = p.parse_args()

    paper = args.paper_equity
    if args.from_system_state:
        paper = _paper_equity_from_state(SYSTEM_STATE)
    liquid = args.liquid
    if liquid is None:
        liquid = float(paper) if paper is not None else 0.0

    if args.number_only:
        fn = compute_freedom_number(
            args.monthly,
            tax_reserve_rate=args.tax_reserve,
            assumed_gross_yield_annual=args.yield_annual,
        )
        print(json.dumps(fn.as_dict(), indent=2))
        return 0

    report = build_freedom_capital_report(
        monthly_after_tax=args.monthly,
        total_liquid=liquid,
        paper_equity=paper,
        live_edge_candidate=args.edge_candidate,
        day_index=args.day,
        tax_reserve_rate=args.tax_reserve,
        assumed_gross_yield_annual=args.yield_annual,
        ops_fraction=args.ops_frac,
        lab_fraction=args.lab_frac,
        field_fraction=args.field_frac,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\njson_out={args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
