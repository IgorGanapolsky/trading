#!/usr/bin/env python3
"""
Run the end-to-end options live simulation:

- Loads account equity from data/system_state.json (unless overridden)
- Generates the latest premium pacing summary via Options Profit Planner
- Builds a theta harvest plan gated by equity + regime filters
- Persists a combined artifact under data/options_signals/

Usage:
    PYTHONPATH=src python3 scripts/run_options_live_sim.py \
        --equity 5500 \
        --regime calm \
        --symbols SPY,QQQ
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from src.analytics.options_live_sim import OptionsLiveSimResult, OptionsLiveSimulator


def _parse_symbols(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return [token.strip().upper() for token in raw.split(",") if token.strip()]


def _print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def _print_profit_summary(summary: dict[str, object]) -> None:
    _print_section("Options Profit Planner")
    print(f"Target Daily Profit : ${summary.get('target_daily_profit', 0):.2f}")
    print(f"Daily Run-Rate      : ${summary.get('daily_run_rate', 0):.2f}")
    print(f"Gap to Target       : ${summary.get('gap_to_target', 0):.2f}")
    print(f"Signals Analyzed    : {summary.get('signals_analyzed', 0)}")


def _print_theta_plan(plan: dict[str, object]) -> None:
    _print_section("Theta Harvest Plan")
    print(plan.get("summary", "No plan generated"))
    print(f"Total Est. Premium  : ${plan.get('total_estimated_premium', 0):.2f}/day")
    print(f"Premium Gap         : ${plan.get('premium_gap', 0):.2f}/day")
    opportunities = plan.get("opportunities", [])
    if opportunities:
        print("\nTop Opportunity:")
        top = opportunities[0]
        print(
            f"- {top.get('symbol')} | {top.get('strategy')} | "
            f"{top.get('contracts')} contract(s) | "
            f"Est premium ${top.get('estimated_premium', 0):.2f}"
        )


def summarize_result(result: OptionsLiveSimResult, combined_path: Path | None) -> None:
    print("\n=== Options Live Simulation ===")
    print(f"Account Equity      : ${result.account_equity:,.2f}")
    print(f"Regime              : {result.regime_label} ({result.regime_source})")
    if combined_path:
        print(f"Artifact            : {combined_path}")

    _print_profit_summary(result.profit_summary)
    _print_theta_plan(result.theta_plan)
    print()


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the options live simulation pipeline.")
    parser.add_argument(
        "--equity", type=float, help="Override account equity instead of reading system_state.json"
    )
    parser.add_argument("--regime", help="Override regime label (e.g. calm, volatile)")
    parser.add_argument(
        "--symbols",
        help="Comma-separated list of symbols to evaluate for theta harvest (default: SPY,QQQ,IWM)",
    )
    parser.add_argument(
        "--system-state",
        default=Path("data/system_state.json"),
        type=Path,
        help="Path to system_state.json (default: data/system_state.json)",
    )
    parser.add_argument(
        "--target-daily",
        type=float,
        default=10.0,
        help="Target daily premium for the profit planner (default: 10)",
    )
    parser.add_argument(
        "--trading-days",
        type=int,
        default=21,
        help="Trading days per month for run-rate calculations (default: 21)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/options_signals/options_live_sim_latest.json"),
        help="Destination for combined plan output (default: data/options_signals/options_live_sim_latest.json)",
    )
    parser.add_argument(
        "--skip-summary-persist",
        action="store_true",
        help="Do not persist the planner summary (useful for dry runs/tests)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip writing the combined plan to disk (console output only)",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    simulator = OptionsLiveSimulator(
        system_state_path=args.system_state,
        target_daily_profit=args.target_daily,
        trading_days_per_month=args.trading_days,
    )

    result = simulator.run(
        account_equity=args.equity,
        regime_label=args.regime,
        symbols=_parse_symbols(args.symbols),
        persist_summary=not args.skip_summary_persist,
    )

    combined_path = None
    if not args.dry_run:
        combined_path = simulator.persist_combined_plan(result, args.output)

    summarize_result(result, combined_path)


if __name__ == "__main__":
    main()
