#!/usr/bin/env python3
"""Generate a profit-target report aligned with the $100/day North Star."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.analytics.profit_target_tracker import ProfitTargetTracker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an actionable plan for reaching the daily profit target."
    )
    parser.add_argument(
        "--state",
        default="data/system_state.json",
        help="Path to the latest system_state snapshot.",
    )
    parser.add_argument(
        "--target",
        type=float,
        default=100.0,
        help="Desired net income per day.",
    )
    parser.add_argument(
        "--output",
        default="reports/profit_target_report.json",
        help="Where to store the generated report.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tracker = ProfitTargetTracker(
        state_path=args.state,
        target_daily_profit=args.target,
    )
    plan = tracker.generate_plan()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tracker.write_report(output_path)

    print("=== Profit Target Report ===")
    print(f"Current daily profit : ${plan.current_daily_profit:,.2f}")
    print(f"Projected daily profit: ${plan.projected_daily_profit:,.2f}")
    print(f"Target daily profit   : ${plan.target_daily_profit:,.2f}")
    print(f"Target gap            : ${plan.target_gap:,.2f}")
    if plan.recommended_daily_budget:
        print(f"Recommended budget    : ${plan.recommended_daily_budget:,.2f}")
        if plan.scaling_factor:
            print(f"Scaling factor        : {plan.scaling_factor:,.2f}x")
    else:
        print("Recommended budget    : Collect more data before scaling capital.")
    print("")
    print("Action plan:")
    for action in plan.actions:
        print(f"- {action}")
    print("")
    print(f"Report written to {output_path}")


if __name__ == "__main__":
    main()
