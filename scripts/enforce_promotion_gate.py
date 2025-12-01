#!/usr/bin/env python3
"""
Promotion gate enforcement script.

Checks live paper-trading metrics plus the latest backtest matrix results and
halts execution if the system has not satisfied the R&D success criteria.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_SYSTEM_STATE = Path("data/system_state.json")
DEFAULT_BACKTEST_SUMMARY = Path("data/backtests/latest_summary.json")
DEFAULT_MIN_PROFITABLE_DAYS = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enforce R&D promotion gate.")
    parser.add_argument(
        "--system-state",
        default=str(DEFAULT_SYSTEM_STATE),
        help="Path to system_state.json (paper trading metrics).",
    )
    parser.add_argument(
        "--backtest-summary",
        default=str(DEFAULT_BACKTEST_SUMMARY),
        help="Path to aggregate backtest matrix summary JSON.",
    )
    parser.add_argument(
        "--required-win-rate",
        type=float,
        default=60.0,
        help="Minimum win rate percentage required for promotion.",
    )
    parser.add_argument(
        "--required-sharpe",
        type=float,
        default=1.5,
        help="Minimum Sharpe ratio required for promotion.",
    )
    parser.add_argument(
        "--max-drawdown",
        type=float,
        default=10.0,
        help="Maximum allowed drawdown percentage.",
    )
    parser.add_argument(
        "--min-profitable-days",
        type=int,
        default=DEFAULT_MIN_PROFITABLE_DAYS,
        help="Minimum consecutive profitable days (paper or backtests) required.",
    )
    parser.add_argument(
        "--override-env",
        default="ALLOW_PROMOTION_OVERRIDE",
        help="Env var that allows bypassing the gate when set to truthy value.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required metrics file missing: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_percent(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if numeric <= 1.0:
        return numeric * 100.0
    return numeric


def evaluate_gate(
    system_state: Dict[str, Any],
    backtest_summary: Dict[str, Any],
    args: argparse.Namespace,
) -> List[str]:
    deficits: List[str] = []

    win_rate = normalize_percent(
        system_state.get("performance", {}).get("win_rate")
        or system_state.get("heuristics", {}).get("win_rate")
        or 0.0
    )
    sharpe = float(system_state.get("heuristics", {}).get("sharpe_ratio", 0.0))
    drawdown = abs(float(system_state.get("heuristics", {}).get("max_drawdown", 0.0)))

    if win_rate < args.required_win_rate:
        deficits.append(
            f"Win rate {win_rate:.2f}% < {args.required_win_rate}% (paper trading)."
        )
    if sharpe < args.required_sharpe:
        deficits.append(
            f"Sharpe ratio {sharpe:.2f} < {args.required_sharpe} (paper trading)."
        )
    if drawdown > args.max_drawdown:
        deficits.append(
            f"Max drawdown {drawdown:.2f}% > {args.max_drawdown}% (paper trading)."
        )

    aggregate = backtest_summary.get("aggregate_metrics", {})
    min_streak = int(aggregate.get("min_profitable_streak", 0))
    if min_streak < args.min_profitable_days:
        deficits.append(
            f"Best validated profitable streak is {min_streak} days "
            f"(< {args.min_profitable_days} required)."
        )

    min_sharpe = float(aggregate.get("min_sharpe_ratio", 0.0))
    if min_sharpe < args.required_sharpe:
        deficits.append(
            f"Backtest Sharpe floor {min_sharpe:.2f} < {args.required_sharpe}."
        )

    max_drawdown_bt = float(aggregate.get("max_drawdown", 999.0))
    if max_drawdown_bt > args.max_drawdown:
        deficits.append(
            f"Backtest drawdown ceiling {max_drawdown_bt:.2f}% exceeds {args.max_drawdown}%."
        )

    min_win_rate = float(aggregate.get("min_win_rate", 0.0))
    if min_win_rate < args.required_win_rate:
        deficits.append(
            f"Backtest win-rate floor {min_win_rate:.2f}% < {args.required_win_rate}%."
        )

    return deficits


def main() -> None:
    args = parse_args()

    override_flag = os.getenv(args.override_env, "").lower() in {"1", "true", "yes"}

    try:
        system_state = load_json(Path(args.system_state))
    except FileNotFoundError as exc:
        if override_flag:
            print(f"⚠️  Missing system_state.json but override is enabled: {exc}")
            sys.exit(0)
        raise

    try:
        backtest_summary = load_json(Path(args.backtest_summary))
    except FileNotFoundError as exc:
        if override_flag:
            print(f"⚠️  Missing backtest summary but override is enabled: {exc}")
            sys.exit(0)
        raise

    deficits = evaluate_gate(system_state, backtest_summary, args)

    if deficits and not override_flag:
        print("❌ Promotion gate failed. Reasons:")
        for item in deficits:
            print(f"  - {item}")
        print(
            "\nSet ALLOW_PROMOTION_OVERRIDE=1 to bypass temporarily "
            "(must be documented in commit/CI logs)."
        )
        sys.exit(1)

    print("✅ Promotion gate satisfied. System may proceed to next stage.")
    if override_flag:
        print("⚠️  Proceeding under manual override flag.")


if __name__ == "__main__":
    main()
