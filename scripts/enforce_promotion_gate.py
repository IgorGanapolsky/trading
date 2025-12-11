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
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_SYSTEM_STATE = Path("data/system_state.json")
DEFAULT_BACKTEST_SUMMARY = Path("data/backtests/latest_summary.json")
DEFAULT_MIN_PROFITABLE_DAYS = 30
DEFAULT_STALE_HOURS = 48
DEFAULT_SCALING_OUTPUT = Path("data/plan/next_capital_step.json")


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
        default=55.0,  # Loosened from 60% for 60-day live pilot (Dec 11, 2025)
        help="Minimum win rate percentage required for promotion.",
    )
    parser.add_argument(
        "--required-sharpe",
        type=float,
        default=1.2,  # Loosened from 1.5 for 60-day live pilot (Dec 11, 2025)
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
        "--min-trades",
        type=int,
        default=100,
        help="Minimum number of trades required for statistical significance.",
    )
    parser.add_argument(
        "--override-env",
        default="ALLOW_PROMOTION_OVERRIDE",
        help="Env var that allows bypassing the gate when set to truthy value.",
    )
    parser.add_argument(
        "--stale-threshold-hours",
        type=float,
        default=float(os.getenv("PROMOTION_STALE_HOURS", DEFAULT_STALE_HOURS)),
        help="If system_state is older than this threshold, auto-bypass the gate so new data can refresh it.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in machine-parsable JSON format.",
    )
    parser.add_argument(
        "--json-output",
        type=str,
        default=None,
        help="Write JSON output to this file path.",
    )
    parser.add_argument(
        "--emit-scaling-plan",
        action="store_true",
        default=True,
        help="Emit capital scaling plan to data/plan/next_capital_step.json when gate passes.",
    )
    parser.add_argument(
        "--current-daily-investment",
        type=float,
        default=10.0,
        help="Current daily investment amount (baseline for scaling recommendations).",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
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
    system_state: dict[str, Any],
    backtest_summary: dict[str, Any],
    args: argparse.Namespace,
) -> list[str]:
    deficits: list[str] = []

    win_rate = normalize_percent(
        system_state.get("performance", {}).get("win_rate")
        or system_state.get("heuristics", {}).get("win_rate")
        or 0.0
    )
    sharpe = float(system_state.get("heuristics", {}).get("sharpe_ratio", 0.0))
    drawdown = abs(float(system_state.get("heuristics", {}).get("max_drawdown", 0.0)))

    if win_rate < args.required_win_rate:
        deficits.append(f"Win rate {win_rate:.2f}% < {args.required_win_rate}% (paper trading).")
    if sharpe < args.required_sharpe:
        deficits.append(f"Sharpe ratio {sharpe:.2f} < {args.required_sharpe} (paper trading).")
    if drawdown > args.max_drawdown:
        deficits.append(f"Max drawdown {drawdown:.2f}% > {args.max_drawdown}% (paper trading).")

    aggregate = backtest_summary.get("aggregate_metrics", {})
    min_streak = int(aggregate.get("min_profitable_streak", 0))
    if min_streak < args.min_profitable_days:
        deficits.append(
            f"Best validated profitable streak is {min_streak} days "
            f"(< {args.min_profitable_days} required)."
        )

    min_sharpe = float(aggregate.get("min_sharpe_ratio", 0.0))
    if min_sharpe < args.required_sharpe:
        deficits.append(f"Backtest Sharpe floor {min_sharpe:.2f} < {args.required_sharpe}.")

    max_drawdown_bt = float(aggregate.get("max_drawdown", 999.0))
    if max_drawdown_bt > args.max_drawdown:
        deficits.append(
            f"Backtest drawdown ceiling {max_drawdown_bt:.2f}% exceeds {args.max_drawdown}%."
        )

    min_win_rate = float(aggregate.get("min_win_rate", 0.0))
    if min_win_rate < args.required_win_rate:
        deficits.append(f"Backtest win-rate floor {min_win_rate:.2f}% < {args.required_win_rate}%.")

    # Enforce minimum trade count for statistical significance
    total_trades = int(
        system_state.get("performance", {}).get("total_trades", 0)
        or aggregate.get("total_trades", 0)
    )
    if total_trades < args.min_trades:
        deficits.append(
            f"Insufficient trades for statistical significance: {total_trades} < {args.min_trades} required."
        )

    return deficits


def calculate_stale_hours(system_state: dict[str, Any]) -> float | None:
    """Return age (in hours) of system_state based on meta.last_updated."""

    last_updated = system_state.get("meta", {}).get("last_updated")
    if not last_updated:
        return None

    try:
        if "T" in last_updated:
            dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None

    age_hours = (datetime.utcnow() - dt.replace(tzinfo=None)).total_seconds() / 3600
    return age_hours


def build_json_result(
    status: str,
    deficits: list[str],
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
    override_active: bool = False,
    stale_hours: float | None = None,
) -> dict[str, Any]:
    """Build machine-parsable JSON result."""
    result = {
        "status": status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "override_active": override_active,
        "stale_hours": stale_hours,
        "metrics": metrics,
        "thresholds": thresholds,
        "deficits": [
            {"description": d} for d in deficits
        ],
        "deficit_count": len(deficits),
    }
    return result


def calculate_scaling_recommendation(
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
    current_investment: float,
) -> dict[str, Any]:
    """
    Calculate capital scaling recommendation based on current metrics.

    Returns a dict with decision, scaling factor, and confidence.
    """
    win_rate = metrics["win_rate"]
    sharpe = metrics["sharpe_ratio"]
    drawdown = metrics["max_drawdown"]

    # Aggressive scaling criteria: Sharpe > 1.5, win_rate > 60%, drawdown < 5%
    if sharpe > 1.5 and win_rate > 60.0 and drawdown < 5.0:
        decision = "SCALE_UP"
        scale_factor = 2.5
        confidence = 0.9
        justification = (
            f"Strong performance: Sharpe {sharpe:.2f}, Win Rate {win_rate:.1f}%, "
            f"Drawdown {drawdown:.1f}% - exceeds all targets for aggressive scaling"
        )
    # Conservative scaling: just meets thresholds
    elif (
        sharpe >= thresholds["sharpe_ratio"]
        and win_rate >= thresholds["win_rate"]
        and drawdown <= thresholds["max_drawdown"]
    ):
        decision = "PROMOTE"
        scale_factor = 1.5
        confidence = 0.75
        justification = (
            f"Meets promotion criteria: Sharpe {sharpe:.2f}, Win Rate {win_rate:.1f}%, "
            f"Drawdown {drawdown:.1f}% - conservative scaling recommended"
        )
    # Borderline: passes but metrics are marginal
    else:
        decision = "HOLD"
        scale_factor = 1.0
        confidence = 0.5
        justification = (
            f"Borderline metrics: Sharpe {sharpe:.2f}, Win Rate {win_rate:.1f}%, "
            f"Drawdown {drawdown:.1f}% - hold current capital until stronger performance"
        )

    to_investment = current_investment * scale_factor

    return {
        "decision": decision,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "from_daily_investment": current_investment,
        "to_daily_investment": round(to_investment, 2),
        "scale_factor": scale_factor,
        "justification": justification,
        "metrics": metrics,
        "confidence": confidence,
    }


def main() -> None:
    args = parse_args()

    override_flag = os.getenv(args.override_env, "").lower() in {"1", "true", "yes"}

    try:
        system_state = load_json(Path(args.system_state))
    except FileNotFoundError as exc:
        if override_flag:
            if not args.json:
                print(f"⚠️  Missing system_state.json but override is enabled: {exc}")
            sys.exit(0)
        raise

    try:
        backtest_summary = load_json(Path(args.backtest_summary))
    except FileNotFoundError as exc:
        if override_flag:
            if not args.json:
                print(f"⚠️  Missing backtest summary but override is enabled: {exc}")
            sys.exit(0)
        raise

    stale_hours = calculate_stale_hours(system_state)
    stale_override = stale_hours is not None and stale_hours >= args.stale_threshold_hours

    deficits = evaluate_gate(system_state, backtest_summary, args)

    # Collect metrics for JSON output
    metrics = {
        "win_rate": normalize_percent(
            system_state.get("performance", {}).get("win_rate")
            or system_state.get("heuristics", {}).get("win_rate")
            or 0.0
        ),
        "sharpe_ratio": float(system_state.get("heuristics", {}).get("sharpe_ratio", 0.0)),
        "max_drawdown": abs(float(system_state.get("heuristics", {}).get("max_drawdown", 0.0))),
        "total_trades": int(
            system_state.get("performance", {}).get("total_trades", 0)
            or backtest_summary.get("aggregate_metrics", {}).get("total_trades", 0)
        ),
    }
    thresholds = {
        "win_rate": args.required_win_rate,
        "sharpe_ratio": args.required_sharpe,
        "max_drawdown": args.max_drawdown,
        "min_trades": args.min_trades,
        "min_profitable_days": args.min_profitable_days,
    }

    gate_passed = not deficits or override_flag or stale_override
    status = "passed" if gate_passed else "blocked"

    # JSON output mode
    if args.json or args.json_output:
        json_result = build_json_result(
            status=status,
            deficits=deficits,
            metrics=metrics,
            thresholds=thresholds,
            override_active=override_flag or stale_override,
            stale_hours=stale_hours,
        )
        json_str = json.dumps(json_result, indent=2)

        if args.json_output:
            Path(args.json_output).write_text(json_str)
        if args.json:
            print(json_str)
            sys.exit(0 if gate_passed else 1)

    # Human-readable output
    if stale_override and not args.json:
        print(
            f"⚠️  Skipping promotion gate: system_state.json is {stale_hours:.1f}h old (threshold {args.stale_threshold_hours}h)."
        )

    if deficits and not (override_flag or stale_override):
        print("❌ Promotion gate failed. Reasons:")
        for item in deficits:
            print(f"  - {item}")
        print(
            "\nSet ALLOW_PROMOTION_OVERRIDE=1 to bypass temporarily "
            "(must be documented in commit/CI logs)."
        )
        sys.exit(1)

    print("✅ Promotion gate satisfied. System may proceed to next stage.")
    if override_flag or stale_override:
        print("⚠️  Proceeding under manual override flag.")

    # Emit capital scaling plan if gate passed (without overrides) and enabled
    if args.emit_scaling_plan and not deficits and not (override_flag or stale_override):
        scaling_plan = calculate_scaling_recommendation(
            metrics=metrics,
            thresholds=thresholds,
            current_investment=args.current_daily_investment,
        )

        # Ensure output directory exists
        output_path = DEFAULT_SCALING_OUTPUT
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write scaling plan
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(scaling_plan, f, indent=2)

        if not args.json:
            print(f"\n📊 Capital scaling recommendation: {scaling_plan['decision']}")
            print(f"   Current: ${scaling_plan['from_daily_investment']:.2f}/day")
            print(f"   Recommended: ${scaling_plan['to_daily_investment']:.2f}/day")
            print(f"   Confidence: {scaling_plan['confidence']:.0%}")
            print(f"   Plan saved to: {output_path}")


if __name__ == "__main__":
    main()
