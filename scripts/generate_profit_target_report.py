#!/usr/bin/env python3
"""Generate reports/profit_target_report.json for dashboard and autonomous trader."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root is importable when run directly.
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics.profit_target_tracker import ProfitTargetTracker
from src.core.trading_constants import NORTH_STAR_DAILY_AFTER_TAX


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target-daily-profit",
        type=float,
        default=NORTH_STAR_DAILY_AFTER_TAX,
        help="Daily after-tax profit target (default: North Star daily target).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/profit_target_report.json"),
        help="Output JSON path.",
    )
    args = parser.parse_args()

    tracker = ProfitTargetTracker(target_daily_profit=args.target_daily_profit)
    plan = tracker.generate_plan()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")

    print(f"Saved profit target report: {args.output}")
    print(
        f"Projected ${plan.projected_daily_profit:.2f}/day vs target ${plan.target_daily_profit:.2f}/day "
        f"(gap ${plan.target_gap:.2f}/day)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
