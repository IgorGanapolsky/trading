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
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import yaml

if TYPE_CHECKING:  # pragma: no cover - for static typing only
    from src.backtesting.backtest_results import BacktestResults


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = BASE_DIR / "config" / "backtest_scenarios.yaml"
BACKTEST_ROOT = BASE_DIR / "data" / "backtests"
SUMMARY_PATH = BACKTEST_ROOT / "latest_summary.json"

# Promotion guard thresholds (align with docs/r-and-d-phase.md)
PROMOTION_THRESHOLDS = {
    "win_rate": 60.0,
    "sharpe_ratio": 1.5,
    "max_drawdown": 10.0,
}


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

    engine = BacktestEngine(
        strategy=strategy,
        start_date=scenario["start_date"],
        end_date=scenario["end_date"],
        initial_capital=float(
            scenario.get("initial_capital", defaults.get("initial_capital", 100000.0))
        ),
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

    return {
        "scenario": scenario["name"],
        "label": scenario.get("label"),
        "start_date": results.start_date,
        "end_date": results.end_date,
        "trading_days": results.trading_days,
        "total_return_pct": round(results.total_return, 2),
        "annualized_return_pct": round(results.to_dict().get("annualized_return", 0.0), 2),
        "sharpe_ratio": round(results.sharpe_ratio, 3),
        "max_drawdown_pct": round(results.max_drawdown, 2),
        "win_rate_pct": round(results.win_rate, 2),
        "profitable_days": profitable_days,
        "longest_profitable_streak": longest_streak,
        "final_capital": round(results.final_capital, 2),
        "total_trades": results.total_trades,
        "status": status,
        "description": scenario.get("description"),
        "generated_at": datetime.utcnow().isoformat(),
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

    aggregate = {
        "generated_at": datetime.utcnow().isoformat(),
        "scenario_count": len(summaries),
        "scenarios": summaries,
        "aggregate_metrics": {
            "min_win_rate": min(item["win_rate_pct"] for item in summaries),
            "min_sharpe_ratio": min(item["sharpe_ratio"] for item in summaries),
            "max_drawdown": max(item["max_drawdown_pct"] for item in summaries),
            "min_profitable_streak": min(item["longest_profitable_streak"] for item in summaries),
            "passes": sum(1 for item in summaries if item["status"] == "pass"),
        },
    }
    return aggregate


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
        summary = run_backtest_for_scenario(scenario, defaults, scenario_dir)
        summaries.append(summary)

    aggregate = aggregate_summary(summaries)
    write_summary(aggregate, Path(args.summary))
    print(f"✅ Backtest matrix complete. Summary written to {args.summary}")


if __name__ == "__main__":
    main()
