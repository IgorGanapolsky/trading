#!/usr/bin/env python3
"""CLI tool: Calculate Freedom Number, capital requirements, and timeline to North Star.

Examples:
  python scripts/calculate_freedom_number.py
  python scripts/calculate_freedom_number.py --capital 100000 --savings 4000 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.strategies.freedom_number_calculator import (  # noqa: E402
    FreedomBudget,
    FreedomNumberCalculator,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Calculate Freedom Number and North Star Timeline")
    p.add_argument(
        "--monthly-need", type=float, default=6000.0, help="Net monthly target after tax"
    )
    p.add_argument(
        "--capital", type=float, default=100000.0, help="Current starting capital in USD"
    )
    p.add_argument(
        "--savings", type=float, default=4000.0, help="Monthly business/consulting net savings"
    )
    p.add_argument(
        "--yield-pct",
        type=float,
        default=0.095,
        help="Blended 3-Bucket annual yield (e.g. 0.095 for 9.5%)",
    )
    p.add_argument(
        "--alpha-pct",
        type=float,
        default=0.120,
        help="Annual options trading alpha (e.g. 0.12 for 12%)",
    )
    p.add_argument("--json", action="store_true", help="Output JSON format")
    args = p.parse_args(argv)

    budget = FreedomBudget(
        base_living_expenses_usd=args.monthly_need * 0.75,
        healthcare_buffer_usd=args.monthly_need * 0.166,
        lifestyle_travel_buffer_usd=args.monthly_need * 0.084,
        tax_contingency_pct=0.18,
    )
    calc = FreedomNumberCalculator(budget=budget)
    proj = calc.compute_projection(
        current_capital_usd=args.capital,
        monthly_business_savings_usd=args.savings,
        annual_portfolio_yield_pct=args.yield_pct,
        annual_trading_alpha_pct=args.alpha_pct,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "target_capital_usd": proj.target_capital_usd,
                    "current_capital_usd": proj.current_capital_usd,
                    "months_to_deadline": proj.months_to_deadline,
                    "target_deadline_date": proj.target_deadline_date,
                    "projected_capital_at_deadline": proj.projected_capital_at_deadline,
                    "monthly_passive_income_at_deadline": proj.monthly_passive_income_at_deadline,
                    "shortfall_or_surplus_usd": proj.shortfall_or_surplus_usd,
                    "on_track_for_north_star": proj.on_track_for_north_star,
                    "months_to_freedom_achieved": proj.months_to_freedom_achieved,
                },
                indent=2,
            )
        )
        return 0

    print("=" * 60)
    print("🎯 NORTH STAR FREEDOM NUMBER & MILESTONE ROADMAP")
    print("=" * 60)
    print(f"• Target Monthly Net Income:   ${budget.total_net_monthly_need:,.2f}/month")
    print(f"• Target Capital Requirement:   ${proj.target_capital_usd:,.2f}")
    print(f"• Current Starting Capital:    ${proj.current_capital_usd:,.2f}")
    print(f"• Monthly Business Savings:     ${proj.monthly_business_savings_usd:,.2f}/month")
    print(
        f"• Combined Growth Rate:        {proj.annual_portfolio_yield_pct + proj.annual_trading_alpha_pct:.1%} (Yield: {proj.annual_portfolio_yield_pct:.1%} + Alpha: {proj.annual_trading_alpha_pct:.1%})"
    )
    print(
        f"• Target Deadline:             {proj.target_deadline_date} ({proj.months_to_deadline} months remaining)"
    )
    print("-" * 60)
    print(f"• Projected Capital at 2029:   ${proj.projected_capital_at_deadline:,.2f}")
    print(f"• Projected Monthly Income:    ${proj.monthly_passive_income_at_deadline:,.2f}/month")
    print(f"• Freedom Achieved In:         {proj.months_to_freedom_achieved} months")
    status = (
        "✅ ON TRACK TO REACH NORTH STAR"
        if proj.on_track_for_north_star
        else "⚠️ DEFICIT (Increase savings or alpha)"
    )
    print(f"• Status:                      {status}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
