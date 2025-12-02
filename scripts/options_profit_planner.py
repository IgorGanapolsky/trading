#!/usr/bin/env python3
"""
CLI wrapper around OptionsProfitPlanner.

Usage examples:

    # Analyze the most recent snapshot persisted under data/options_signals
    PYTHONPATH=src python3 scripts/options_profit_planner.py

    # Force a fresh scan (runs RuleOneOptionsStrategy → requires network/APIs)
    PYTHONPATH=src python3 scripts/options_profit_planner.py --scan-now

    # Customize target daily profit and export JSON summary
    PYTHONPATH=src python3 scripts/options_profit_planner.py --target-daily 15 \
        --output-json data/options_signals/custom_plan.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from src.analytics.options_profit_planner import OptionsProfitPlanner

logger = logging.getLogger("options_profit_planner")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def run_scan(paper: bool) -> dict[str, Any] | None:
    """Optionally generate fresh signals (requires yfinance + Alpaca creds)."""
    try:
        from src.strategies.rule_one_options import RuleOneOptionsStrategy
    except Exception as exc:  # pragma: no cover - only hit when deps missing
        logger.error("Unable to import RuleOneOptionsStrategy: %s", exc)
        return None

    try:
        strategy = RuleOneOptionsStrategy(paper=paper)
        snapshot = strategy.generate_daily_signals()
        snapshot["_source_path"] = "live_scan"
        logger.info(
            "Generated %d put / %d call opportunities via live scan",
            len(snapshot.get("puts", [])),
            len(snapshot.get("calls", [])),
        )
        return snapshot
    except Exception as exc:
        logger.warning("Live scan failed (likely due to missing network/API access): %s", exc)
        return None


def print_summary(summary: dict[str, Any]) -> None:
    """Pretty-print planner output."""
    print("\n=== Options Profit Planner ===")
    print(f"Target Daily Profit : ${summary['target_daily_profit']:.2f}")
    print(f"Run-Rate (Daily)    : ${summary['daily_run_rate']:.2f}")
    print(f"Run-Rate (Monthly)  : ${summary['monthly_run_rate']:.2f}")
    print(f"Gap to Target       : ${summary['gap_to_target']:.2f}")
    if summary.get("data_source"):
        print(f"Data Source         : {summary['data_source']}")

    if summary.get("signals_analyzed"):
        print(f"Signals Analyzed    : {summary['signals_analyzed']}")
    else:
        print("Signals Analyzed    : 0 (no qualifying opportunities)")

    print("\nNotes:")
    for note in summary.get("notes", []):
        print(f"- {note}")

    recommendation = summary.get("recommendation")
    if recommendation:
        print("\nRecommendation:")
        print(
            f"- {recommendation['suggested_action']} "
            f"(≈ ${recommendation['daily_premium_per_contract']:.2f}/contract/day)"
        )
    print()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Options Profit Planner")
    parser.add_argument(
        "--target-daily",
        type=float,
        default=10.0,
        help="Desired daily premium target (default: 10)",
    )
    parser.add_argument(
        "--trading-days",
        type=int,
        default=21,
        help="Trading days per month for run-rate calculations (default: 21)",
    )
    parser.add_argument(
        "--scan-now",
        action="store_true",
        help="Generate fresh signals before planning (requires network + API keys)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live (non-paper) mode when scanning for signals",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional path to write consolidated plan JSON",
    )

    args = parser.parse_args(argv)

    planner = OptionsProfitPlanner(
        target_daily_profit=args.target_daily,
        trading_days_per_month=args.trading_days,
    )

    snapshot = None
    if args.scan_now:
        snapshot = run_scan(paper=not args.live)

    if snapshot is None:
        snapshot = planner.load_latest_snapshot()

    summary = planner.build_summary_from_snapshot(snapshot)
    planner.persist_summary(summary)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        with args.output_json.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
        logger.info("Wrote summary to %s", args.output_json)

    print_summary(summary)


if __name__ == "__main__":
    main(sys.argv[1:])
