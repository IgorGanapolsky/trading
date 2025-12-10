#!/usr/bin/env python3
"""
Per-Gate Ablation Framework for Trading System.

This script systematically enables/disables individual gates in the trading funnel
to measure each gate's contribution to overall performance (Sharpe, win rate, DD).

Usage:
    python scripts/run_backtest_ablation.py --scenarios bull_run_2024,inflation_shock_2022
    python scripts/run_backtest_ablation.py --all-scenarios --output-csv data/ablation_results.csv

Gate Configurations:
    A: Momentum only (baseline)
    B: Momentum + Risk rules
    C: Momentum + Risk + RL filter
    D: Momentum + Risk + RL + LLM sentiment
    E: Full funnel (all gates enabled)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.backtesting.backtest_engine import BacktestEngine

DEFAULT_CONFIG = BASE_DIR / "config" / "backtest_scenarios.yaml"
ABLATION_OUTPUT_DIR = BASE_DIR / "data" / "ablation"


@dataclass
class AblationConfig:
    """Configuration for a single ablation experiment."""

    name: str
    description: str
    gates_enabled: dict[str, bool] = field(default_factory=dict)

    # Environment variable overrides to apply
    env_overrides: dict[str, str] = field(default_factory=dict)


# Define ablation configurations (gates to enable/disable)
ABLATION_CONFIGS: list[AblationConfig] = [
    AblationConfig(
        name="A_momentum_only",
        description="Baseline: Momentum filter only (no RL, no LLM, no introspection)",
        gates_enabled={
            "momentum": True,
            "rl": False,
            "llm_sentiment": False,
            "introspection": False,
            "mental_coach": False,
        },
        env_overrides={
            "RL_CONFIDENCE_THRESHOLD": "0.0",
            "LLM_NEGATIVE_SENTIMENT_THRESHOLD": "-1.0",
            "ENABLE_INTROSPECTION": "false",
            "ENABLE_MENTAL_COACHING": "false",
            "ENABLE_ASYNC_ANALYST": "false",
        },
    ),
    AblationConfig(
        name="B_momentum_risk",
        description="Momentum + static risk rules (position sizing, stop losses)",
        gates_enabled={
            "momentum": True,
            "rl": False,
            "llm_sentiment": False,
            "introspection": False,
            "mental_coach": False,
        },
        env_overrides={
            "RL_CONFIDENCE_THRESHOLD": "0.0",
            "LLM_NEGATIVE_SENTIMENT_THRESHOLD": "-1.0",
            "ENABLE_INTROSPECTION": "false",
            "ENABLE_MENTAL_COACHING": "false",
            "ENABLE_ASYNC_ANALYST": "false",
            # Risk gates stay enabled via default
        },
    ),
    AblationConfig(
        name="C_momentum_risk_rl",
        description="Momentum + Risk + RL filter (ML confidence gating)",
        gates_enabled={
            "momentum": True,
            "rl": True,
            "llm_sentiment": False,
            "introspection": False,
            "mental_coach": False,
        },
        env_overrides={
            "RL_CONFIDENCE_THRESHOLD": "0.45",
            "LLM_NEGATIVE_SENTIMENT_THRESHOLD": "-1.0",
            "ENABLE_INTROSPECTION": "false",
            "ENABLE_MENTAL_COACHING": "false",
            "ENABLE_ASYNC_ANALYST": "false",
        },
    ),
    AblationConfig(
        name="D_momentum_risk_rl_llm",
        description="Momentum + Risk + RL + LLM sentiment (no introspection)",
        gates_enabled={
            "momentum": True,
            "rl": True,
            "llm_sentiment": True,
            "introspection": False,
            "mental_coach": False,
        },
        env_overrides={
            "RL_CONFIDENCE_THRESHOLD": "0.45",
            "LLM_NEGATIVE_SENTIMENT_THRESHOLD": "-0.2",
            "ENABLE_INTROSPECTION": "false",
            "ENABLE_MENTAL_COACHING": "false",
            "ENABLE_ASYNC_ANALYST": "true",
        },
    ),
    AblationConfig(
        name="E_full_funnel",
        description="Full funnel: All gates enabled (momentum + RL + LLM + introspection + coach)",
        gates_enabled={
            "momentum": True,
            "rl": True,
            "llm_sentiment": True,
            "introspection": True,
            "mental_coach": True,
        },
        env_overrides={
            "RL_CONFIDENCE_THRESHOLD": "0.45",
            "LLM_NEGATIVE_SENTIMENT_THRESHOLD": "-0.2",
            "ENABLE_INTROSPECTION": "true",
            "ENABLE_MENTAL_COACHING": "true",
            "ENABLE_ASYNC_ANALYST": "true",
        },
    ),
]


@dataclass
class AblationResult:
    """Results from a single ablation run."""

    config_name: str
    scenario_name: str
    sharpe_ratio: float
    win_rate: float
    max_drawdown: float
    total_return: float
    total_trades: int
    avg_daily_pnl: float
    profitable_days: int
    gates_enabled: dict[str, bool]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


def load_scenarios(config_path: Path) -> list[dict[str, Any]]:
    """Load scenario definitions from YAML config."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("scenarios", [])


def apply_env_overrides(overrides: dict[str, str]) -> dict[str, str | None]:
    """Apply environment variable overrides and return previous values."""
    previous = {}
    for key, value in overrides.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    return previous


def restore_env(previous: dict[str, str | None]) -> None:
    """Restore environment variables to previous values."""
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def run_ablation_backtest(
    scenario: dict[str, Any],
    ablation_config: AblationConfig,
    defaults: dict[str, Any],
) -> AblationResult:
    """Run a single ablation backtest and return results."""

    # Apply environment overrides
    previous_env = apply_env_overrides(ablation_config.env_overrides)

    try:
        # Extract scenario parameters
        start_date = scenario.get("start_date", "2024-01-02")
        end_date = scenario.get("end_date", "2024-03-29")
        etf_universe = scenario.get("etf_universe", defaults.get("etf_universe", ["SPY", "QQQ"]))
        initial_capital = scenario.get("initial_capital", defaults.get("initial_capital", 100000))
        daily_allocation = scenario.get("daily_allocation", defaults.get("daily_allocation", 10.0))

        # Create and run backtest engine
        engine = BacktestEngine(
            initial_capital=initial_capital,
            start_date=start_date,
            end_date=end_date,
        )

        # Run with simplified strategy (no VCA for ablation)
        results = engine.run_strategy(
            etf_universe=etf_universe,
            daily_allocation=daily_allocation,
            use_vca=False,
        )

        # Calculate metrics
        daily_pnl = results.daily_pnl if hasattr(results, "daily_pnl") else []
        avg_daily_pnl = sum(daily_pnl) / len(daily_pnl) if daily_pnl else 0.0
        profitable_days = sum(1 for p in daily_pnl if p > 0) if daily_pnl else 0

        return AblationResult(
            config_name=ablation_config.name,
            scenario_name=scenario.get("name", "unknown"),
            sharpe_ratio=results.sharpe_ratio,
            win_rate=results.win_rate,
            max_drawdown=results.max_drawdown,
            total_return=results.total_return,
            total_trades=results.total_trades,
            avg_daily_pnl=avg_daily_pnl,
            profitable_days=profitable_days,
            gates_enabled=ablation_config.gates_enabled,
        )

    finally:
        # Restore environment
        restore_env(previous_env)


def run_ablation_matrix(
    scenarios: list[dict[str, Any]],
    configs: list[AblationConfig],
    defaults: dict[str, Any],
) -> list[AblationResult]:
    """Run full ablation matrix across scenarios and configurations."""
    results: list[AblationResult] = []

    total_runs = len(scenarios) * len(configs)
    current_run = 0

    for scenario in scenarios:
        scenario_name = scenario.get("name", "unknown")

        for config in configs:
            current_run += 1
            print(f"[{current_run}/{total_runs}] Running {config.name} on {scenario_name}...")

            try:
                result = run_ablation_backtest(scenario, config, defaults)
                results.append(result)
                print(
                    f"  → Sharpe: {result.sharpe_ratio:.2f}, Win Rate: {result.win_rate:.1f}%, DD: {result.max_drawdown:.1f}%"
                )
            except Exception as e:
                print(f"  → ERROR: {e}")
                # Record failure
                results.append(
                    AblationResult(
                        config_name=config.name,
                        scenario_name=scenario_name,
                        sharpe_ratio=float("nan"),
                        win_rate=0.0,
                        max_drawdown=100.0,
                        total_return=0.0,
                        total_trades=0,
                        avg_daily_pnl=0.0,
                        profitable_days=0,
                        gates_enabled=config.gates_enabled,
                    )
                )

    return results


def generate_ablation_report(results: list[AblationResult], output_dir: Path) -> None:
    """Generate comprehensive ablation report."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write CSV
    csv_path = output_dir / "ablation_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Config",
                "Scenario",
                "Sharpe",
                "Win Rate (%)",
                "Max DD (%)",
                "Total Return (%)",
                "Trades",
                "Avg Daily PnL",
                "Profitable Days",
                "Momentum",
                "RL",
                "LLM",
                "Introspection",
                "Coach",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r.config_name,
                    r.scenario_name,
                    f"{r.sharpe_ratio:.2f}",
                    f"{r.win_rate:.1f}",
                    f"{r.max_drawdown:.1f}",
                    f"{r.total_return:.2f}",
                    r.total_trades,
                    f"{r.avg_daily_pnl:.2f}",
                    r.profitable_days,
                    r.gates_enabled.get("momentum", True),
                    r.gates_enabled.get("rl", False),
                    r.gates_enabled.get("llm_sentiment", False),
                    r.gates_enabled.get("introspection", False),
                    r.gates_enabled.get("mental_coach", False),
                ]
            )

    # Write JSON
    json_path = output_dir / "ablation_results.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(
            [
                {
                    "config_name": r.config_name,
                    "scenario_name": r.scenario_name,
                    "sharpe_ratio": r.sharpe_ratio,
                    "win_rate": r.win_rate,
                    "max_drawdown": r.max_drawdown,
                    "total_return": r.total_return,
                    "total_trades": r.total_trades,
                    "avg_daily_pnl": r.avg_daily_pnl,
                    "profitable_days": r.profitable_days,
                    "gates_enabled": r.gates_enabled,
                    "timestamp": r.timestamp,
                }
                for r in results
            ],
            f,
            indent=2,
        )

    # Generate summary by config (aggregated across scenarios)
    summary: dict[str, dict[str, float]] = {}
    for r in results:
        if r.config_name not in summary:
            summary[r.config_name] = {
                "count": 0,
                "sharpe_sum": 0.0,
                "sharpe_min": float("inf"),
                "win_rate_sum": 0.0,
                "win_rate_min": float("inf"),
                "max_dd": 0.0,
            }
        s = summary[r.config_name]
        if r.sharpe_ratio == r.sharpe_ratio:  # not NaN
            s["count"] += 1
            s["sharpe_sum"] += r.sharpe_ratio
            s["sharpe_min"] = min(s["sharpe_min"], r.sharpe_ratio)
            s["win_rate_sum"] += r.win_rate
            s["win_rate_min"] = min(s["win_rate_min"], r.win_rate)
            s["max_dd"] = max(s["max_dd"], r.max_drawdown)

    # Write markdown summary
    md_path = output_dir / "ablation_summary.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("# Ablation Test Results\n\n")
        f.write(f"Generated: {datetime.utcnow().isoformat()}\n\n")
        f.write("## Summary by Configuration\n\n")
        f.write("| Config | Avg Sharpe | Min Sharpe | Avg Win Rate | Min Win Rate | Max DD |\n")
        f.write("|--------|------------|------------|--------------|--------------|--------|\n")

        for config_name, s in sorted(summary.items()):
            if s["count"] > 0:
                avg_sharpe = s["sharpe_sum"] / s["count"]
                avg_wr = s["win_rate_sum"] / s["count"]
                f.write(
                    f"| {config_name} | {avg_sharpe:.2f} | {s['sharpe_min']:.2f} | {avg_wr:.1f}% | {s['win_rate_min']:.1f}% | {s['max_dd']:.1f}% |\n"
                )

        f.write("\n## Gate Value Analysis\n\n")
        f.write("Compare adjacent configurations to see each gate's contribution:\n\n")
        f.write("- **A→B**: Risk rules contribution\n")
        f.write("- **B→C**: RL filter contribution\n")
        f.write("- **C→D**: LLM sentiment contribution\n")
        f.write("- **D→E**: Introspection + Mental Coach contribution\n")

        f.write("\n## Detailed Results\n\n")
        f.write("| Config | Scenario | Sharpe | Win Rate | Max DD | Trades |\n")
        f.write("|--------|----------|--------|----------|--------|--------|\n")
        for r in results:
            sharpe_str = f"{r.sharpe_ratio:.2f}" if r.sharpe_ratio == r.sharpe_ratio else "N/A"
            f.write(
                f"| {r.config_name} | {r.scenario_name} | {sharpe_str} | {r.win_rate:.1f}% | {r.max_drawdown:.1f}% | {r.total_trades} |\n"
            )

    print("\n✅ Ablation report generated:")
    print(f"   - CSV: {csv_path}")
    print(f"   - JSON: {json_path}")
    print(f"   - Summary: {md_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run per-gate ablation backtests")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to backtest scenarios YAML",
    )
    parser.add_argument(
        "--scenarios",
        type=str,
        default="",
        help="Comma-separated list of scenario names to run (default: all)",
    )
    parser.add_argument(
        "--all-scenarios",
        action="store_true",
        help="Run all scenarios from config",
    )
    parser.add_argument(
        "--configs",
        type=str,
        default="",
        help="Comma-separated list of ablation configs to run (A,B,C,D,E)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ABLATION_OUTPUT_DIR),
        help="Directory for ablation results",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Load scenarios
    config_path = Path(args.config)
    config_data = {}
    with config_path.open("r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}

    defaults = config_data.get("defaults", {})
    all_scenarios = config_data.get("scenarios", [])

    # Filter scenarios
    if args.scenarios:
        scenario_names = [s.strip() for s in args.scenarios.split(",")]
        scenarios = [s for s in all_scenarios if s.get("name") in scenario_names]
    elif args.all_scenarios:
        scenarios = all_scenarios
    else:
        # Default: run key regime scenarios
        key_scenarios = [
            "bull_run_2024",
            "inflation_shock_2022",
            "covid_whiplash_2020",
            "high_vol_2022_q4",
        ]
        scenarios = [s for s in all_scenarios if s.get("name") in key_scenarios]

    if not scenarios:
        print("❌ No scenarios selected. Use --scenarios or --all-scenarios")
        sys.exit(1)

    # Filter configs
    configs = ABLATION_CONFIGS
    if args.configs:
        config_keys = [c.strip().upper() for c in args.configs.split(",")]
        configs = [c for c in ABLATION_CONFIGS if c.name.split("_")[0] in config_keys]

    print("🔬 Running ablation matrix:")
    print(f"   Scenarios: {[s.get('name') for s in scenarios]}")
    print(f"   Configs: {[c.name for c in configs]}")
    print(f"   Total runs: {len(scenarios) * len(configs)}")
    print()

    # Run ablation matrix
    results = run_ablation_matrix(scenarios, configs, defaults)

    # Generate report
    output_dir = Path(args.output_dir)
    generate_ablation_report(results, output_dir)


if __name__ == "__main__":
    main()
