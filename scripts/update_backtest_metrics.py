#!/usr/bin/env python3
"""
Update latest_summary.json with proper metrics from real trade data.

Uses the performance_metrics module to calculate annualized Sharpe ratio
and other risk-adjusted metrics from spread_performance.json.
"""

import json
import math
from datetime import datetime
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
SPREAD_PERF_FILE = DATA_DIR / "spread_performance.json"
BACKTEST_DIR = DATA_DIR / "backtests"
LATEST_SUMMARY = BACKTEST_DIR / "latest_summary.json"

# Constants
TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.045  # Current 3-month T-bill ~4.5%


def calculate_metrics_from_trades(trades: list, initial_capital: float = 5000.0) -> dict:
    """Calculate performance metrics from trade list."""
    if not trades:
        return {
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
            "volatility": 0.0,
            "calmar_ratio": 0.0,
        }

    pnls = [t.get("pnl", 0) for t in trades]
    returns = [p / initial_capital for p in pnls]

    # Basic stats
    n = len(returns)
    mean_return = sum(returns) / n

    # Variance and std dev (sample)
    if n > 1:
        variance = sum((r - mean_return) ** 2 for r in returns) / (n - 1)
        std_return = math.sqrt(variance)
    else:
        std_return = 0.0

    # Downside deviation (only negative returns)
    negative_returns = [r for r in returns if r < 0]
    if negative_returns and len(negative_returns) > 1:
        mean_neg = sum(negative_returns) / len(negative_returns)
        down_variance = sum((r - mean_neg) ** 2 for r in negative_returns) / (len(negative_returns) - 1)
        downside_dev = math.sqrt(down_variance)
    else:
        downside_dev = 0.0

    # Risk-free rate per period
    rf_per_period = RISK_FREE_RATE / TRADING_DAYS_PER_YEAR

    # Annualized Sharpe Ratio
    if std_return > 0:
        excess_return = mean_return - rf_per_period
        sharpe = (excess_return / std_return) * math.sqrt(TRADING_DAYS_PER_YEAR)
    else:
        sharpe = 0.0

    # Sortino Ratio
    if downside_dev > 0:
        sortino = ((mean_return - rf_per_period) / downside_dev) * math.sqrt(TRADING_DAYS_PER_YEAR)
    else:
        sortino = 10.0 if mean_return > 0 else 0.0

    # Max Drawdown
    equity_curve = [initial_capital]
    for pnl in pnls:
        equity_curve.append(equity_curve[-1] + pnl)

    running_max = equity_curve[0]
    max_dd = 0.0
    for equity in equity_curve:
        running_max = max(running_max, equity)
        drawdown = (running_max - equity) / running_max if running_max > 0 else 0
        max_dd = max(max_dd, drawdown)

    # Annualized volatility
    volatility = std_return * math.sqrt(TRADING_DAYS_PER_YEAR)

    # Total return (annualized estimate based on days tracked)
    total_return = sum(pnls) / initial_capital

    # Calmar ratio
    calmar = total_return / max_dd if max_dd > 0 else (10.0 if total_return > 0 else 0.0)

    # Profit factor
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (10.0 if gross_profit > 0 else 0.0)

    return {
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "max_drawdown": round(max_dd, 4),
        "volatility": round(volatility, 4),
        "calmar_ratio": round(calmar, 4),
        "profit_factor": round(profit_factor, 4),
        "total_return": round(total_return, 4),
    }


def main():
    """Update latest_summary.json with proper metrics."""
    print("=" * 60)
    print("UPDATING BACKTEST METRICS FROM REAL TRADE DATA")
    print("=" * 60)

    # Load spread performance data
    if not SPREAD_PERF_FILE.exists():
        print(f"ERROR: {SPREAD_PERF_FILE} not found")
        return

    with open(SPREAD_PERF_FILE) as f:
        spread_data = json.load(f)

    trades = spread_data.get("trades", [])
    summary = spread_data.get("summary", {})

    print(f"\nLoaded {len(trades)} trades from spread_performance.json")
    print(f"Total P/L: ${summary.get('total_pnl', 0):.2f}")
    print(f"Win Rate: {summary.get('win_rate_pct', 0):.1f}%")

    # Calculate proper metrics
    metrics = calculate_metrics_from_trades(trades)

    print("\nCalculated Metrics:")
    print(f"  Sharpe Ratio (annualized): {metrics['sharpe_ratio']:.2f}")
    print(f"  Sortino Ratio: {metrics['sortino_ratio']:.2f}")
    print(f"  Max Drawdown: {metrics['max_drawdown'] * 100:.1f}%")
    print(f"  Volatility (annualized): {metrics['volatility'] * 100:.1f}%")
    print(f"  Profit Factor: {metrics['profit_factor']:.2f}")

    # Load existing summary or create new
    if LATEST_SUMMARY.exists():
        with open(LATEST_SUMMARY) as f:
            latest = json.load(f)
    else:
        latest = {}

    # Update with new metrics
    pnls = [t.get("pnl", 0) for t in trades]
    latest.update({
        "total_trades": len(trades),
        "total_pnl": sum(pnls),
        "win_rate": summary.get("win_rate_pct", 0) / 100,
        "avg_trade": sum(pnls) / len(pnls) if pnls else 0,
        "max_win": max(pnls) if pnls else 0,
        "max_loss": min(pnls) if pnls else 0,
        "std_dev": metrics["volatility"] / math.sqrt(TRADING_DAYS_PER_YEAR) if metrics["volatility"] > 0 else 0,
        "sharpe_ratio": metrics["sharpe_ratio"],
        "sortino_ratio": metrics["sortino_ratio"],
        "max_drawdown": metrics["max_drawdown"],
        "profit_factor": metrics["profit_factor"],
        "calmar_ratio": metrics["calmar_ratio"],
        "volatility": metrics["volatility"],
        "data_source": "spread_performance.json (real trades)",
        "start_date": summary.get("start_date", "2026-01-13"),
        "end_date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
    })

    # Save updated summary
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    with open(LATEST_SUMMARY, "w") as f:
        json.dump(latest, f, indent=2)

    print(f"\n✅ Updated {LATEST_SUMMARY}")
    print("=" * 60)


if __name__ == "__main__":
    main()
