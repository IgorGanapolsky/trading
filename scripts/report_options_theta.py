#!/usr/bin/env python3
"""
Generate reproducible artifacts for the options theta strategy:
- CSV of estimated daily premium and gap-to-target
- Markdown report with the latest plan summary
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from src.analytics.options_live_sim import OptionsLiveSimulator

CSV_FIELDS = [
    "date",
    "account_equity",
    "regime",
    "estimated_daily_premium",
    "premium_gap",
    "opportunity_count",
]


def write_csv_row(csv_path: Path, row: dict[str, object]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def render_report(
    report_path: Path, row: dict[str, object], opportunities: Iterable[dict[str, object]]
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Options Theta Strategy Report",
        "",
        f"**Generated**: {datetime.utcnow().isoformat()}Z",
        f"**Account Equity**: ${row['account_equity']:,.2f}",
        f"**Regime**: {row['regime']}",
        f"**Estimated Daily Premium**: ${row['estimated_daily_premium']:.2f}",
        f"**Gap to Target**: ${row['premium_gap']:.2f}",
        "",
        "## Opportunities",
    ]
    if opportunities:
        lines.append("| Symbol | Strategy | Contracts | Est Premium |")
        lines.append("|--------|----------|-----------|-------------|")
        for opp in opportunities:
            lines.append(
                f"| {opp.get('symbol', 'N/A')} | {opp.get('strategy', '-')}"
                f" | {opp.get('contracts', 0)} | ${opp.get('estimated_premium', 0):.2f} |"
            )
    else:
        lines.append("_No qualifying opportunities at this equity/IV level._")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate CSV + report for the options theta strategy."
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=Path("data/backtests/options_theta_daily_pl.csv"),
        help="Where to write the aggregated daily premium CSV.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("reports/options_theta_strategy.md"),
        help="Where to write the Markdown report.",
    )
    parser.add_argument(
        "--equity",
        type=float,
        help="Override account equity instead of reading system_state.json.",
    )
    parser.add_argument(
        "--regime",
        help="Override regime label.",
    )
    parser.add_argument(
        "--symbols",
        nargs="*",
        default=None,
        help="Symbols to evaluate (default: config list inside simulator).",
    )
    args = parser.parse_args(argv)

    simulator = OptionsLiveSimulator()
    result = simulator.run(
        account_equity=args.equity,
        regime_label=args.regime,
        symbols=args.symbols,
    )

    plan = result.theta_plan
    row = {
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "account_equity": result.account_equity,
        "regime": result.regime_label,
        "estimated_daily_premium": round(plan.get("total_estimated_premium", 0.0), 2),
        "premium_gap": round(plan.get("premium_gap", 0.0), 2),
        "opportunity_count": len(plan.get("opportunities", [])),
    }

    write_csv_row(args.csv_path, row)
    render_report(args.report_path, row, plan.get("opportunities", []))

    print(f"Wrote CSV row to {args.csv_path}")
    print(f"Wrote report to {args.report_path}")


if __name__ == "__main__":
    main()
