#!/usr/bin/env python3
"""
Run a matrix of historical backtests to validate promotion readiness.

The script loads scenario definitions from config/backtest_scenarios.yaml,
executes each scenario with a lightweight DCA momentum strategy, and writes
structured summaries under data/backtests/<strategy>/<scenario>/.

Outputs:
    - Per-scenario JSON + Markdown reports
    - Aggregate summary at data/backtests/latest_summary.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent

# Ensure repo root is importable when script executed via `python scripts/...`
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if TYPE_CHECKING:  # pragma: no cover - for static typing only
    from src.backtesting.backtest_results import BacktestResults

DEFAULT_CONFIG = BASE_DIR / "config" / "backtest_scenarios.yaml"
BACKTEST_ROOT = BASE_DIR / "data" / "backtests"
SUMMARY_PATH = BACKTEST_ROOT / "latest_summary.json"

# Promotion guard thresholds (align with docs/r-and-d-phase.md)
PROMOTION_THRESHOLDS = {
    "win_rate": 60.0,
    "sharpe_ratio": 1.5,
    "max_drawdown": 10.0,
}
FEE_RATE = float(os.getenv("BACKTEST_FEE_RATE", "0.0018"))

# Enhanced cost modeling parameters
SLIPPAGE_BASE_BPS = float(os.getenv("SLIPPAGE_BASE_BPS", "18"))  # 0.18% round-trip
SLIPPAGE_VOL_SCALE = float(os.getenv("SLIPPAGE_VOL_SCALE", "5"))  # Extra bps during high vol
SEC_FEE_RATE = float(os.getenv("SEC_FEE_RATE", "0.000008"))  # SEC transaction fee
BROKER_FEE_RATE = float(os.getenv("BROKER_FEE_RATE", "0.0005"))  # Broker fee estimate
TELEMETRY_DIR = BACKTEST_ROOT / "telemetry"


@dataclass
class MatrixStrategy:
    """Minimal strategy container required by BacktestEngine."""

    etf_universe: list[str]
    daily_allocation: float
    use_vca: bool = False
    vca_strategy: Any = None  # Not used but required by engine interface


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run configured backtest scenarios and persist structured summaries."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to backtest scenario YAML (default: config/backtest_scenarios.yaml).",
    )
    parser.add_argument(
        "--output-root",
        default=str(BACKTEST_ROOT),
        help="Directory to store scenario artifacts (default: data/backtests).",
    )
    parser.add_argument(
        "--summary",
        default=str(SUMMARY_PATH),
        help="Aggregate summary JSON path (default: data/backtests/latest_summary.json).",
    )
    parser.add_argument(
        "--max-scenarios",
        type=int,
        default=0,
        help="Optional cap on number of scenarios to execute (0 = all).",
    )
    parser.add_argument(
        "--use-hybrid-gates",
        action="store_true",
        help="Replay the full hybrid funnel (momentum → RL → LLM proxy → risk) inside the backtest engine.",
    )
    return parser.parse_args()


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Backtest config not found at {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if "scenarios" not in data:
        raise ValueError("Scenario config must define a top-level 'scenarios' list.")
    return data


def run_backtest_for_scenario(
    scenario: dict[str, Any],
    defaults: dict[str, Any],
    output_dir: Path,
    *,
    use_hybrid_gates: bool = False,
) -> dict[str, Any]:
    from src.backtesting.backtest_engine import (
        BacktestEngine,  # local import to avoid heavy deps during tests
    )

    strategy = MatrixStrategy(
        etf_universe=scenario.get("etf_universe", defaults.get("etf_universe", [])),
        daily_allocation=float(
            scenario.get("daily_allocation", defaults.get("daily_allocation", 10.0))
        ),
    )

    hybrid_options = {"max_trades_per_day": scenario.get("max_trades_per_day", 1)}
    engine = BacktestEngine(
        strategy=strategy,
        start_date=scenario["start_date"],
        end_date=scenario["end_date"],
        initial_capital=float(
            scenario.get("initial_capital", defaults.get("initial_capital", 100000.0))
        ),
        use_hybrid_gates=use_hybrid_gates,
        hybrid_options=hybrid_options,
    )
    results = engine.run()

    summary = summarize_results(results, scenario)
    save_artifacts(summary, results, output_dir)
    return summary


def summarize_results(results: BacktestResults, scenario: dict[str, Any]) -> dict[str, Any]:
    daily_returns = np.diff(results.equity_curve) / results.equity_curve[:-1]
    profitable_days = int(np.sum(daily_returns > 0))
    longest_streak = longest_positive_streak(daily_returns)

    status = evaluate_status(results, thresholds=PROMOTION_THRESHOLDS)
    annualized_return = results.to_dict().get("annualized_return", 0.0)

    # Determine scenario type for vol-scaled cost modeling
    scenario_name = scenario["name"].lower()
    if "high_vol" in scenario_name or "covid" in scenario_name:
        scenario_type = "high_vol"
    elif "live" in scenario_name:
        scenario_type = "live"
    else:
        scenario_type = "base"

    costs = compute_execution_costs(results, scenario_type=scenario_type)

    return {
        "scenario": scenario["name"],
        "label": scenario.get("label"),
        "start_date": results.start_date,
        "end_date": results.end_date,
        "trading_days": results.trading_days,
        "total_return_pct": round(results.total_return, 2),
        "annualized_return_pct": round(annualized_return, 2),
        "sharpe_ratio": round(results.sharpe_ratio, 3),
        "net_sharpe_ratio": costs["net_sharpe_ratio"],
        "max_drawdown_pct": round(results.max_drawdown, 2),
        "win_rate_pct": round(results.win_rate, 2),
        "profitable_days": profitable_days,
        "longest_profitable_streak": longest_streak,
        "final_capital": round(results.final_capital, 2),
        "final_capital_after_costs": round(results.final_capital - costs["total_execution_cost"], 2),
        "total_trades": results.total_trades,
        "status": status,
        "description": scenario.get("description"),
        "generated_at": datetime.utcnow().isoformat(),
        "execution_costs": costs,
        "cost_adjusted_return_pct": costs["cost_adjusted_total_return_pct"],
        "cost_adjusted_annualized_return_pct": costs["cost_adjusted_annualized_return_pct"],
        "hybrid_gates": scenario.get("hybrid_gates", False),
    }


def longest_positive_streak(daily_returns: np.ndarray) -> int:
    streak = max_streak = 0
    for positive in daily_returns > 0:
        if positive:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return int(max_streak)


def evaluate_status(results: BacktestResults, thresholds: dict[str, float]) -> str:
    if (
        results.win_rate >= thresholds["win_rate"]
        and results.sharpe_ratio >= thresholds["sharpe_ratio"]
        and results.max_drawdown <= thresholds["max_drawdown"]
    ):
        return "pass"
    return "needs_improvement"


def compute_execution_costs(
    results: BacktestResults,
    fee_rate: float = FEE_RATE,
    scenario_type: str = "base",
) -> dict[str, float]:
    """
    Enhanced cost modeling with vol-scaled slippage and SEC fees.

    For high_vol or live scenarios, applies additional slippage to reflect
    real-world execution quality degradation during volatile periods.
    """
    total_notional = sum(float(trade.get("amount", 0.0)) for trade in results.trades)
    trade_count = len(results.trades)

    # Base slippage calculation (0.18% round-trip)
    slippage_bps = SLIPPAGE_BASE_BPS
    if scenario_type in ("live", "high_vol", "high_vol_2022_q4"):
        slippage_bps += SLIPPAGE_VOL_SCALE  # Extra 5 bps during high vol

    slippage_rate = slippage_bps / 10_000.0
    slippage_cost = slippage_rate * total_notional

    # SEC fee (on sells only, approximate as half of trades)
    sec_cost = SEC_FEE_RATE * (total_notional / 2)

    # Broker fee
    broker_cost = BROKER_FEE_RATE * total_notional

    # Legacy fee_rate for backward compatibility
    fee_cost = total_notional * fee_rate

    # Total execution costs
    total_cost = slippage_cost + sec_cost + broker_cost
    capital = float(results.initial_capital or 1.0)
    cost_pct = (total_cost / capital) * 100

    cost_adjusted_total_return = results.total_return - cost_pct
    annualized_return = results.to_dict().get("annualized_return", 0.0)
    cost_adjusted_annualized = annualized_return - cost_pct

    # Calculate net Sharpe (cost-adjusted)
    raw_sharpe = results.sharpe_ratio
    cost_drag_factor = 1.0 - (cost_pct / max(results.total_return, 1.0))
    net_sharpe = raw_sharpe * max(0.0, cost_drag_factor)

    return {
        "fee_cost": round(fee_cost, 2),
        "slippage_cost": round(slippage_cost, 2),
        "sec_cost": round(sec_cost, 4),
        "broker_cost": round(broker_cost, 4),
        "total_execution_cost": round(total_cost, 2),
        "cost_pct_of_capital": round(cost_pct, 4),
        "cost_adjusted_total_return_pct": round(cost_adjusted_total_return, 2),
        "cost_adjusted_annualized_return_pct": round(cost_adjusted_annualized, 2),
        "net_sharpe_ratio": round(net_sharpe, 3),
        "trade_count": trade_count,
        "assumptions": {
            "fee_rate": fee_rate,
            "slippage_bps": slippage_bps,
            "sec_fee_rate": SEC_FEE_RATE,
            "broker_fee_rate": BROKER_FEE_RATE,
            "scenario_type": scenario_type,
            "slippage_model_enabled": True,
        },
    }


def save_artifacts(summary: dict[str, Any], results: BacktestResults, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "summary.json"
    md_path = output_dir / "report.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump({"summary": summary, "raw_results": results.to_dict()}, handle, indent=2)

    md_path.write_text(results.generate_report(), encoding="utf-8")


def aggregate_summary(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    if not summaries:
        raise ValueError("No scenario summaries were produced.")

    # Calculate aggregate cost metrics
    total_costs = sum(s["execution_costs"]["total_execution_cost"] for s in summaries)
    avg_net_sharpe = sum(s.get("net_sharpe_ratio", s["sharpe_ratio"]) for s in summaries) / len(summaries)
    avg_cost_adjusted_return = sum(s["cost_adjusted_annualized_return_pct"] for s in summaries) / len(summaries)

    aggregate = {
        "generated_at": datetime.utcnow().isoformat(),
        "scenario_count": len(summaries),
        "scenarios": summaries,
        "aggregate_metrics": {
            "min_win_rate": min(item["win_rate_pct"] for item in summaries),
            "min_sharpe_ratio": min(item["sharpe_ratio"] for item in summaries),
            "min_net_sharpe_ratio": min(item.get("net_sharpe_ratio", item["sharpe_ratio"]) for item in summaries),
            "avg_net_sharpe_ratio": round(avg_net_sharpe, 3),
            "max_drawdown": max(item["max_drawdown_pct"] for item in summaries),
            "min_profitable_streak": min(item["longest_profitable_streak"] for item in summaries),
            "passes": sum(1 for item in summaries if item["status"] == "pass"),
            "total_execution_costs": round(total_costs, 2),
            "avg_cost_adjusted_annualized_return": round(avg_cost_adjusted_return, 2),
        },
        "promotion_gate_status": "pass" if all(s["status"] == "pass" for s in summaries) else "needs_improvement",
    }
    return aggregate


def export_telemetry(summaries: list[dict[str, Any]], output_dir: Path) -> Path:
    """
    Export cost-adjusted results to telemetry JSON for dashboard consumption.

    This enables real-time monitoring of paper-to-live readiness with
    realistic cost assumptions.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    telemetry_path = output_dir / f"cost_adjusted_{timestamp}.json"

    telemetry_data = {
        "generated_at": datetime.utcnow().isoformat(),
        "summary_count": len(summaries),
        "records": [],
    }

    for summary in summaries:
        record = {
            "scenario": summary["scenario"],
            "label": summary.get("label"),
            "trading_days": summary["trading_days"],
            "gross_return_pct": summary["total_return_pct"],
            "net_return_pct": summary["cost_adjusted_return_pct"],
            "annualized_gross_pct": summary["annualized_return_pct"],
            "annualized_net_pct": summary["cost_adjusted_annualized_return_pct"],
            "sharpe_gross": summary["sharpe_ratio"],
            "sharpe_net": summary.get("net_sharpe_ratio", summary["sharpe_ratio"]),
            "max_drawdown_pct": summary["max_drawdown_pct"],
            "win_rate_pct": summary["win_rate_pct"],
            "total_trades": summary["total_trades"],
            "execution_costs": summary["execution_costs"],
            "status": summary["status"],
        }
        telemetry_data["records"].append(record)

    # Calculate aggregate metrics
    if summaries:
        telemetry_data["aggregate"] = {
            "avg_net_sharpe": round(
                sum(r["sharpe_net"] for r in telemetry_data["records"]) / len(summaries), 3
            ),
            "avg_net_annualized": round(
                sum(r["annualized_net_pct"] for r in telemetry_data["records"]) / len(summaries), 2
            ),
            "total_costs": round(
                sum(r["execution_costs"]["total_execution_cost"] for r in telemetry_data["records"]), 2
            ),
            "promotion_ready": all(s["status"] == "pass" for s in summaries),
        }

    with telemetry_path.open("w", encoding="utf-8") as handle:
        json.dump(telemetry_data, handle, indent=2)

    print(f"📊 Telemetry exported to {telemetry_path}")
    return telemetry_path


def write_summary(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)


def main() -> None:
    args = parse_args()
    config = load_config(Path(args.config))
    scenarios: list[dict[str, Any]] = config.get("scenarios", [])
    defaults: dict[str, Any] = config.get("defaults", {})

    if args.max_scenarios > 0:
        scenarios = scenarios[: args.max_scenarios]

    output_root = Path(args.output_root)
    summaries: list[dict[str, Any]] = []
    for scenario in scenarios:
        scenario_dir = output_root / "matrix_core_dca" / scenario["name"]
        scenario["hybrid_gates"] = args.use_hybrid_gates
        summary = run_backtest_for_scenario(
            scenario, defaults, scenario_dir, use_hybrid_gates=args.use_hybrid_gates
        )
        summaries.append(summary)

    aggregate = aggregate_summary(summaries)
    write_summary(aggregate, Path(args.summary))

    # Export telemetry for dashboard consumption
    export_telemetry(summaries, TELEMETRY_DIR)

    # Report promotion gate status
    gate_status = aggregate.get("promotion_gate_status", "unknown")
    if gate_status == "pass":
        print("🎯 PROMOTION GATE: PASS - All scenarios meet thresholds")
    else:
        print("⚠️  PROMOTION GATE: NEEDS IMPROVEMENT - Some scenarios below thresholds")

    print(f"✅ Backtest matrix complete. Summary written to {args.summary}")


if __name__ == "__main__":
    main()
