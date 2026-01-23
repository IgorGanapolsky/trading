#!/usr/bin/env python3
"""
Backtest Strategy Comparison Tool

Compares iron condor vs bull put spread backtest results to help
make data-driven strategy decisions.

Usage:
    python scripts/backtest/compare_strategies.py
    python scripts/backtest/compare_strategies.py --output data/backtests/comparison.json
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


def load_backtest_results(backtest_dir: Path) -> dict:
    """Load all backtest results from directory."""
    results = {
        "iron_condor": [],
        "bull_put_spread": [],
    }

    for file in backtest_dir.glob("*.json"):
        if "summary" not in file.name:
            continue

        try:
            data = json.loads(file.read_text())

            # Determine strategy type
            if "iron_condor" in file.name:
                results["iron_condor"].append(data)
            elif "backtest_summary" in file.name:
                results["bull_put_spread"].append(data)
        except (json.JSONDecodeError, KeyError):
            continue

    return results


def calculate_aggregate_metrics(backtest_list: list[dict]) -> Optional[dict]:
    """Calculate aggregate metrics from multiple backtests."""
    if not backtest_list:
        return None

    total_trades = sum(b.get("total_trades", 0) for b in backtest_list)
    total_pnl = sum(b.get("total_pnl", 0) for b in backtest_list)

    # Weighted win rate
    weighted_wins = sum(
        b.get("win_rate", 0) * b.get("total_trades", 0) for b in backtest_list
    )
    avg_win_rate = weighted_wins / total_trades if total_trades > 0 else 0

    # Average metrics
    sharpe_ratios = [b.get("sharpe_ratio", 0) for b in backtest_list if b.get("sharpe_ratio")]
    profit_factors = [b.get("profit_factor", 0) for b in backtest_list if b.get("profit_factor")]
    max_drawdowns = [b.get("max_drawdown", 0) for b in backtest_list if b.get("max_drawdown")]

    return {
        "backtest_count": len(backtest_list),
        "total_trades": total_trades,
        "total_pnl": total_pnl,
        "avg_win_rate": avg_win_rate,
        "avg_sharpe": sum(sharpe_ratios) / len(sharpe_ratios) if sharpe_ratios else 0,
        "avg_profit_factor": sum(profit_factors) / len(profit_factors) if profit_factors else 0,
        "avg_max_drawdown": sum(max_drawdowns) / len(max_drawdowns) if max_drawdowns else 0,
        "avg_pnl_per_trade": total_pnl / total_trades if total_trades > 0 else 0,
    }


def compare_strategies(backtest_dir: Path) -> dict:
    """Compare iron condor vs bull put spread strategies."""
    results = load_backtest_results(backtest_dir)

    iron_condor = calculate_aggregate_metrics(results["iron_condor"])
    bull_put = calculate_aggregate_metrics(results["bull_put_spread"])

    comparison = {
        "generated_at": datetime.now().isoformat(),
        "iron_condor": iron_condor,
        "bull_put_spread": bull_put,
        "recommendation": None,
        "reasoning": [],
    }

    # Generate recommendation
    if iron_condor and bull_put:
        ic_score = 0
        bp_score = 0
        reasoning = []

        # Win rate comparison (weight: 3)
        if iron_condor["avg_win_rate"] > bull_put["avg_win_rate"]:
            ic_score += 3
            reasoning.append(
                f"Iron condor has higher win rate ({iron_condor['avg_win_rate']*100:.1f}% vs {bull_put['avg_win_rate']*100:.1f}%)"
            )
        else:
            bp_score += 3
            reasoning.append(
                f"Bull put spread has higher win rate ({bull_put['avg_win_rate']*100:.1f}% vs {iron_condor['avg_win_rate']*100:.1f}%)"
            )

        # Sharpe ratio comparison (weight: 2)
        if iron_condor["avg_sharpe"] > bull_put["avg_sharpe"]:
            ic_score += 2
            reasoning.append(
                f"Iron condor has better risk-adjusted returns (Sharpe {iron_condor['avg_sharpe']:.2f} vs {bull_put['avg_sharpe']:.2f})"
            )
        else:
            bp_score += 2
            reasoning.append(
                f"Bull put spread has better risk-adjusted returns (Sharpe {bull_put['avg_sharpe']:.2f} vs {iron_condor['avg_sharpe']:.2f})"
            )

        # Profit factor comparison (weight: 2)
        if iron_condor["avg_profit_factor"] > bull_put["avg_profit_factor"]:
            ic_score += 2
            reasoning.append(
                f"Iron condor has better profit factor ({iron_condor['avg_profit_factor']:.2f} vs {bull_put['avg_profit_factor']:.2f})"
            )
        else:
            bp_score += 2
            reasoning.append(
                f"Bull put spread has better profit factor ({bull_put['avg_profit_factor']:.2f} vs {iron_condor['avg_profit_factor']:.2f})"
            )

        # Max drawdown comparison (weight: 1, lower is better)
        if iron_condor["avg_max_drawdown"] < bull_put["avg_max_drawdown"]:
            ic_score += 1
            reasoning.append(
                f"Iron condor has lower max drawdown ({iron_condor['avg_max_drawdown']*100:.1f}% vs {bull_put['avg_max_drawdown']*100:.1f}%)"
            )
        else:
            bp_score += 1
            reasoning.append(
                f"Bull put spread has lower max drawdown ({bull_put['avg_max_drawdown']*100:.1f}% vs {iron_condor['avg_max_drawdown']*100:.1f}%)"
            )

        comparison["reasoning"] = reasoning
        comparison["scores"] = {"iron_condor": ic_score, "bull_put_spread": bp_score}

        if ic_score > bp_score:
            comparison["recommendation"] = "IRON_CONDOR"
            comparison["confidence"] = ic_score / (ic_score + bp_score)
        elif bp_score > ic_score:
            comparison["recommendation"] = "BULL_PUT_SPREAD"
            comparison["confidence"] = bp_score / (ic_score + bp_score)
        else:
            comparison["recommendation"] = "INCONCLUSIVE"
            comparison["confidence"] = 0.5

    elif iron_condor:
        comparison["recommendation"] = "IRON_CONDOR"
        comparison["reasoning"] = ["Only iron condor data available"]
        comparison["confidence"] = 0.5
    elif bull_put:
        comparison["recommendation"] = "BULL_PUT_SPREAD"
        comparison["reasoning"] = ["Only bull put spread data available"]
        comparison["confidence"] = 0.5
    else:
        comparison["recommendation"] = "INSUFFICIENT_DATA"
        comparison["reasoning"] = ["No backtest data available"]
        comparison["confidence"] = 0

    return comparison


def print_comparison(comparison: dict) -> None:
    """Print comparison results."""
    print("\n" + "=" * 60)
    print("📊 STRATEGY COMPARISON REPORT")
    print("=" * 60)

    if comparison["iron_condor"]:
        ic = comparison["iron_condor"]
        print("\n🦅 IRON CONDOR")
        print(f"   Backtests: {ic['backtest_count']}")
        print(f"   Trades: {ic['total_trades']}")
        print(f"   Win Rate: {ic['avg_win_rate']*100:.1f}%")
        print(f"   Total P/L: ${ic['total_pnl']:.2f}")
        print(f"   Avg P/L/Trade: ${ic['avg_pnl_per_trade']:.2f}")
        print(f"   Sharpe: {ic['avg_sharpe']:.2f}")
        print(f"   Profit Factor: {ic['avg_profit_factor']:.2f}")
        print(f"   Max Drawdown: {ic['avg_max_drawdown']*100:.1f}%")

    if comparison["bull_put_spread"]:
        bp = comparison["bull_put_spread"]
        print("\n🐂 BULL PUT SPREAD")
        print(f"   Backtests: {bp['backtest_count']}")
        print(f"   Trades: {bp['total_trades']}")
        print(f"   Win Rate: {bp['avg_win_rate']*100:.1f}%")
        print(f"   Total P/L: ${bp['total_pnl']:.2f}")
        print(f"   Avg P/L/Trade: ${bp['avg_pnl_per_trade']:.2f}")
        print(f"   Sharpe: {bp['avg_sharpe']:.2f}")
        print(f"   Profit Factor: {bp['avg_profit_factor']:.2f}")
        print(f"   Max Drawdown: {bp['avg_max_drawdown']*100:.1f}%")

    print("\n" + "-" * 60)
    print("📋 REASONING:")
    for reason in comparison.get("reasoning", []):
        print(f"   • {reason}")

    print("\n" + "-" * 60)
    rec = comparison.get("recommendation", "UNKNOWN")
    conf = comparison.get("confidence", 0) * 100
    print(f"🎯 RECOMMENDATION: {rec} (Confidence: {conf:.0f}%)")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Compare backtest strategies")
    parser.add_argument(
        "--backtest-dir",
        type=str,
        default="data/backtests",
        help="Directory containing backtest results",
    )
    parser.add_argument("--output", type=str, help="Output file for comparison results")

    args = parser.parse_args()

    backtest_dir = Path(args.backtest_dir)
    if not backtest_dir.exists():
        print(f"❌ Backtest directory not found: {backtest_dir}")
        return 1

    comparison = compare_strategies(backtest_dir)
    print_comparison(comparison)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(comparison, indent=2, default=str))
        print(f"\n📁 Comparison saved to: {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
