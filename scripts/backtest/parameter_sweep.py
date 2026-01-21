#!/usr/bin/env python3
"""
Parameter Sweep for Bull Put Spread Strategy

Tests multiple parameter combinations to find optimal settings.
Runs during off-market hours to accelerate learning.

Usage:
    python scripts/backtest/parameter_sweep.py --days 60 --max-combos 50
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

# Import the backtester
sys.path.insert(0, str(Path(__file__).parent))
from bull_put_spread_backtester import BacktestConfig, BullPutSpreadBacktester

# Parameter grid to test - simplified for valid combinations
PARAMETER_GRID = {
    "short_put_delta_min": [-0.60, -0.50, -0.45],
    "short_put_delta_max": [-0.25, -0.20, -0.15],
    "long_put_delta_min": [-0.45, -0.40, -0.35],
    "long_put_delta_max": [-0.25, -0.20, -0.15],
    "spread_width_min": [2.0, 3.0],
    "spread_width_max": [4.0, 5.0],
    "target_profit_pct": [0.40, 0.50, 0.60],
    "delta_stop_loss_multiplier": [1.5, 2.0, 2.5],
}


def generate_valid_combinations(grid: dict) -> list[dict]:
    """Generate only valid parameter combinations."""
    combos = []

    keys = list(grid.keys())
    for vals in product(*grid.values()):
        params = dict(zip(keys, vals))

        # Validation: delta ranges must be valid (min <= max, all negative)
        if params["short_put_delta_min"] > params["short_put_delta_max"]:
            continue
        if params["long_put_delta_min"] > params["long_put_delta_max"]:
            continue

        # Validation: spread width must be valid
        if params["spread_width_min"] > params["spread_width_max"]:
            continue

        # Validation: long put should generally be further OTM
        # Long delta should be less negative (closer to 0) than short delta
        # But we allow some overlap for flexibility
        if params["long_put_delta_min"] < params["short_put_delta_min"] - 0.20:
            continue

        combos.append(params)

    return combos


def calculate_max_drawdown(pnls: list[float]) -> float:
    """Calculate maximum drawdown from P&L series."""
    if not pnls:
        return 0.0

    cumulative = np.cumsum(pnls)
    peak = np.maximum.accumulate(cumulative)
    drawdown = cumulative - peak
    return abs(min(drawdown)) if len(drawdown) > 0 else 0.0


def run_parameter_sweep(
    alpaca_key: str,
    alpaca_secret: str,
    start_date: date,
    end_date: date,
    max_combinations: int = 50,
) -> pd.DataFrame:
    """
    Test multiple parameter combinations and rank by performance.

    Returns DataFrame sorted by Sharpe ratio (risk-adjusted returns).
    """
    valid_combos = generate_valid_combinations(PARAMETER_GRID)
    print(f"📊 Generated {len(valid_combos)} valid parameter combinations")
    print(f"   Testing up to {max_combinations} combinations")

    if not valid_combos:
        print("⚠️ No valid combinations generated, using defaults")
        valid_combos = [BacktestConfig().to_dict()]

    results = []

    for i, params in enumerate(valid_combos[:max_combinations]):
        print(f"\n--- Testing combination {i + 1}/{min(len(valid_combos), max_combinations)} ---")

        try:
            # Create config from params
            config = BacktestConfig(**params)

            # Run backtest
            backtester = BullPutSpreadBacktester(alpaca_key, alpaca_secret, config)
            trade_results, summary = backtester.run(start_date, end_date, max_trades=500)

            if not trade_results:
                print("  ⚠️ No trades generated")
                continue

            pnls = [r.theoretical_pnl for r in trade_results]

            std_dev = np.std(pnls) if len(pnls) > 1 else 1.0
            sharpe = np.mean(pnls) / std_dev if std_dev > 0 else 0

            metrics = {
                "params": params,
                "total_pnl": sum(pnls),
                "win_rate": sum(1 for p in pnls if p > 0) / len(pnls),
                "avg_trade": np.mean(pnls),
                "max_win": max(pnls),
                "max_loss": min(pnls),
                "max_drawdown": calculate_max_drawdown(pnls),
                "std_dev": std_dev,
                "sharpe_ratio": sharpe,
                "trade_count": len(pnls),
                "profit_factor": abs(sum(p for p in pnls if p > 0) / sum(p for p in pnls if p < 0))
                if sum(p for p in pnls if p < 0) != 0
                else float("inf"),
            }

            print(
                f"  ✅ P&L: ${metrics['total_pnl']:.2f} | Win Rate: {metrics['win_rate'] * 100:.1f}% | Sharpe: {metrics['sharpe_ratio']:.2f}"
            )
            results.append(metrics)

        except Exception as e:
            print(f"  ❌ Failed: {e}")
            continue

    if not results:
        print("❌ No successful backtest runs")
        return pd.DataFrame()

    # Convert to DataFrame and sort by Sharpe ratio
    df = pd.DataFrame(results)
    df = df.sort_values("sharpe_ratio", ascending=False)

    return df


def main():
    parser = argparse.ArgumentParser(description="Parameter Sweep for Bull Put Spreads")
    parser.add_argument("--days", type=int, default=60, help="Days to backtest")
    parser.add_argument("--max-combos", type=int, default=50, help="Max combinations to test")
    parser.add_argument(
        "--output", type=str, default="data/backtests/parameter_sweeps", help="Output directory"
    )

    args = parser.parse_args()

    # Load API keys
    alpaca_key = os.environ.get("ALPACA_API_KEY")
    alpaca_secret = os.environ.get("ALPACA_SECRET_KEY")

    if not alpaca_key or not alpaca_secret:
        print("❌ ALPACA_API_KEY and ALPACA_SECRET_KEY required")
        sys.exit(1)

    # Determine date range
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=args.days)

    print("🚀 Starting parameter sweep")
    print(f"   Date range: {start_date} to {end_date}")
    print(f"   Max combinations: {args.max_combos}")

    # Run sweep
    results_df = run_parameter_sweep(
        alpaca_key, alpaca_secret, start_date, end_date, args.max_combos
    )

    if results_df.empty:
        print("❌ No results to save")
        sys.exit(1)

    # Save results
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save full results
    results_path = output_dir / f"sweep_results_{timestamp}.csv"
    results_df.to_csv(results_path, index=False)
    print(f"\n📁 Results saved to: {results_path}")

    # Save best parameters
    best_params = results_df.iloc[0]["params"]
    best_path = output_dir / f"best_params_{timestamp}.json"
    with open(best_path, "w") as f:
        json.dump(best_params, f, indent=2)
    print(f"📁 Best params saved to: {best_path}")

    # Print top 5 results
    print("\n" + "=" * 70)
    print("🏆 TOP 5 PARAMETER COMBINATIONS BY SHARPE RATIO")
    print("=" * 70)

    for idx, (i, row) in enumerate(results_df.head(5).iterrows()):
        print(
            f"\n#{idx + 1} Sharpe: {row['sharpe_ratio']:.2f} | P&L: ${row['total_pnl']:.2f} | Win Rate: {row['win_rate'] * 100:.1f}%"
        )
        params = row["params"]
        print(f"   Short Delta: [{params['short_put_delta_min']}, {params['short_put_delta_max']}]")
        print(f"   Long Delta: [{params['long_put_delta_min']}, {params['long_put_delta_max']}]")
        print(f"   Spread: ${params['spread_width_min']}-${params['spread_width_max']}")
        print(f"   Profit Target: {params['target_profit_pct'] * 100}%")

    print("\n" + "=" * 70)

    # Generate RAG lesson for best parameters
    best = results_df.iloc[0]
    lesson = {
        "id": f"param_sweep_{timestamp}",
        "type": "PARAMETER_OPTIMIZATION",
        "title": "Optimal Bull Put Spread Parameters Found",
        "content": f"""
## Parameter Optimization Results

**Sweep Date**: {datetime.now().date()}
**Period Tested**: {start_date} to {end_date}
**Combinations Tested**: {len(results_df)}

### Best Parameters Found (by Sharpe Ratio)

| Parameter | Value |
|-----------|-------|
| Short Delta Range | [{best_params["short_put_delta_min"]}, {best_params["short_put_delta_max"]}] |
| Long Delta Range | [{best_params["long_put_delta_min"]}, {best_params["long_put_delta_max"]}] |
| Spread Width | ${best_params["spread_width_min"]} - ${best_params["spread_width_max"]} |
| Profit Target | {best_params["target_profit_pct"] * 100}% |
| Stop Loss Multiplier | {best_params["delta_stop_loss_multiplier"]}x |

### Performance Metrics
- **Sharpe Ratio**: {best["sharpe_ratio"]:.2f}
- **Total P&L**: ${best["total_pnl"]:.2f}
- **Win Rate**: {best["win_rate"] * 100:.1f}%
- **Max Drawdown**: ${best["max_drawdown"]:.2f}
- **Trade Count**: {best["trade_count"]}

### Recommendation
These parameters showed the best risk-adjusted returns over the test period.
Consider using these as the baseline for live trading.
        """,
        "metadata": {
            "best_params": best_params,
            "sharpe": best["sharpe_ratio"],
            "total_pnl": best["total_pnl"],
            "win_rate": best["win_rate"],
        },
    }

    lesson_path = output_dir / f"sweep_lesson_{timestamp}.json"
    with open(lesson_path, "w") as f:
        json.dump(lesson, f, indent=2, default=str)
    print(f"📁 RAG lesson saved to: {lesson_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
