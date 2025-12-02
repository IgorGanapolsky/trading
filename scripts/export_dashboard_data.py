#!/usr/bin/env python3
"""
Export Dashboard Data to CSV/Excel

Exports comprehensive dashboard metrics to CSV and Excel formats for:
- Custom analytics
- Regulatory compliance
- External reporting
- Data visualization tools
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.dashboard_metrics import TradingMetricsCalculator

DATA_DIR = Path("data")
EXPORT_DIR = Path("data/exports")
EXPORT_DIR.mkdir(exist_ok=True, parents=True)


def export_performance_log_csv():
    """Export performance log to CSV."""
    perf_log_file = DATA_DIR / "performance_log.json"
    if not perf_log_file.exists():
        print("⚠️  Performance log not found")
        return None

    with open(perf_log_file) as f:
        perf_log = json.load(f)

    if not perf_log:
        print("⚠️  Performance log is empty")
        return None

    # Convert to DataFrame
    df = pd.DataFrame(perf_log)

    # Export to CSV
    csv_file = EXPORT_DIR / f"performance_log_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(csv_file, index=False)
    print(f"✅ Exported performance log to: {csv_file}")

    return csv_file


def export_trades_csv():
    """Export all trades to CSV."""
    all_trades = []

    # Find all trade files
    trade_files = list(DATA_DIR.glob("trades_*.json"))

    for trade_file in trade_files:
        with open(trade_file) as f:
            trades = json.load(f)
            if isinstance(trades, list):
                for trade in trades:
                    trade["trade_date"] = trade_file.stem.replace("trades_", "")
                    all_trades.append(trade)

    if not all_trades:
        print("⚠️  No trades found")
        return None

    # Convert to DataFrame
    df = pd.DataFrame(all_trades)

    # Export to CSV
    csv_file = EXPORT_DIR / f"trades_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(csv_file, index=False)
    print(f"✅ Exported trades to: {csv_file}")

    return csv_file


def export_metrics_summary_csv():
    """Export metrics summary to CSV."""
    calculator = TradingMetricsCalculator(DATA_DIR)
    metrics = calculator.calculate_all_metrics()

    # Flatten metrics for CSV export
    summary_data = []

    # Account Summary
    account = metrics.get("account_summary", {})
    summary_data.append(
        {
            "Category": "Account",
            "Metric": "Starting Balance",
            "Value": account.get("starting_balance", 0),
            "Unit": "USD",
        }
    )
    summary_data.append(
        {
            "Category": "Account",
            "Metric": "Current Equity",
            "Value": account.get("current_equity", 0),
            "Unit": "USD",
        }
    )
    summary_data.append(
        {
            "Category": "Account",
            "Metric": "Total P/L",
            "Value": account.get("total_pl", 0),
            "Unit": "USD",
        }
    )
    summary_data.append(
        {
            "Category": "Account",
            "Metric": "Total P/L %",
            "Value": account.get("total_pl_pct", 0),
            "Unit": "%",
        }
    )

    # Risk Metrics
    risk = metrics.get("risk_metrics", {})
    summary_data.append(
        {
            "Category": "Risk",
            "Metric": "Max Drawdown",
            "Value": risk.get("max_drawdown_pct", 0),
            "Unit": "%",
        }
    )
    summary_data.append(
        {
            "Category": "Risk",
            "Metric": "Sharpe Ratio",
            "Value": risk.get("sharpe_ratio", 0),
            "Unit": "Ratio",
        }
    )
    summary_data.append(
        {
            "Category": "Risk",
            "Metric": "Sortino Ratio",
            "Value": risk.get("sortino_ratio", 0),
            "Unit": "Ratio",
        }
    )
    summary_data.append(
        {
            "Category": "Risk",
            "Metric": "Volatility (Annualized)",
            "Value": risk.get("volatility_annualized", 0),
            "Unit": "%",
        }
    )

    # Performance Metrics
    perf = metrics.get("performance_metrics", {})
    summary_data.append(
        {
            "Category": "Performance",
            "Metric": "Profit Factor",
            "Value": perf.get("profit_factor", 0),
            "Unit": "Ratio",
        }
    )
    summary_data.append(
        {
            "Category": "Performance",
            "Metric": "Win Rate",
            "Value": perf.get("win_rate", 0),
            "Unit": "%",
        }
    )
    summary_data.append(
        {
            "Category": "Performance",
            "Metric": "Expectancy per Trade",
            "Value": perf.get("expectancy_per_trade", 0),
            "Unit": "USD",
        }
    )

    # Benchmark
    benchmark = metrics.get("benchmark_comparison", {})
    summary_data.append(
        {
            "Category": "Benchmark",
            "Metric": "Portfolio Return",
            "Value": benchmark.get("portfolio_return", 0),
            "Unit": "%",
        }
    )
    summary_data.append(
        {
            "Category": "Benchmark",
            "Metric": "Benchmark Return (SPY)",
            "Value": benchmark.get("benchmark_return", 0),
            "Unit": "%",
        }
    )
    summary_data.append(
        {
            "Category": "Benchmark",
            "Metric": "Alpha",
            "Value": benchmark.get("alpha", 0),
            "Unit": "%",
        }
    )

    # Convert to DataFrame
    df = pd.DataFrame(summary_data)

    # Export to CSV
    csv_file = EXPORT_DIR / f"metrics_summary_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(csv_file, index=False)
    print(f"✅ Exported metrics summary to: {csv_file}")

    return csv_file


def export_to_excel():
    """Export all data to Excel workbook with multiple sheets."""
    excel_file = EXPORT_DIR / f"dashboard_export_{datetime.now().strftime('%Y%m%d')}.xlsx"

    with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
        # Performance Log Sheet
        perf_log_file = DATA_DIR / "performance_log.json"
        if perf_log_file.exists():
            with open(perf_log_file) as f:
                perf_log = json.load(f)
            if perf_log:
                df_perf = pd.DataFrame(perf_log)
                df_perf.to_excel(writer, sheet_name="Performance Log", index=False)

        # Trades Sheet
        all_trades = []
        trade_files = list(DATA_DIR.glob("trades_*.json"))
        for trade_file in trade_files:
            with open(trade_file) as f:
                trades = json.load(f)
                if isinstance(trades, list):
                    for trade in trades:
                        trade["trade_date"] = trade_file.stem.replace("trades_", "")
                        all_trades.append(trade)
        if all_trades:
            df_trades = pd.DataFrame(all_trades)
            df_trades.to_excel(writer, sheet_name="Trades", index=False)

        # Metrics Summary Sheet
        calculator = TradingMetricsCalculator(DATA_DIR)
        metrics = calculator.calculate_all_metrics()

        # Flatten metrics
        summary_data = []
        for category, category_data in metrics.items():
            if isinstance(category_data, dict):
                for key, value in category_data.items():
                    if isinstance(value, (int, float, str)):
                        summary_data.append({"Category": category, "Metric": key, "Value": value})

        if summary_data:
            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, sheet_name="Metrics Summary", index=False)

    print(f"✅ Exported all data to Excel: {excel_file}")
    return excel_file


def main():
    """Export all dashboard data."""
    print("=" * 70)
    print("DASHBOARD DATA EXPORT")
    print("=" * 70)
    print()

    # Export CSV files
    print("Exporting CSV files...")
    export_performance_log_csv()
    export_trades_csv()
    export_metrics_summary_csv()

    print()
    print("Exporting Excel workbook...")
    export_to_excel()

    print()
    print("=" * 70)
    print("✅ Export complete!")
    print(f"📁 Files saved to: {EXPORT_DIR}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
