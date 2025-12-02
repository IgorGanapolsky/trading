#!/usr/bin/env python3
"""
Chart Generation for World-Class Dashboard

Generates visualizations for the trading dashboard:
- Equity curve
- Drawdown chart
- Daily P/L distribution
- Rolling Sharpe
- Win/loss distribution
- Trade holding time histogram

Uses matplotlib to create images that can be embedded in markdown.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DATA_DIR = Path("data")
CHARTS_DIR = Path("wiki") / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_equity_curve_chart(
    perf_log: list[dict], output_path: Optional[Path] = None
) -> Optional[str]:
    """Generate equity curve chart."""
    if not MATPLOTLIB_AVAILABLE or not perf_log or len(perf_log) < 2:
        return None

    # Extract data
    dates = []
    equity_values = []
    for entry in perf_log:
        date_str = entry.get("date", "")
        equity = entry.get("equity", 100000)
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str)
                dates.append(dt)
                equity_values.append(equity)
            except:
                pass

    if len(dates) < 2:
        return None

    # Create chart
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(dates, equity_values, linewidth=2, color="#2563eb", label="Portfolio Equity")
    ax.fill_between(dates, equity_values, alpha=0.3, color="#2563eb")
    ax.set_xlabel("Date", fontsize=10)
    ax.set_ylabel("Equity ($)", fontsize=10)
    ax.set_title("Equity Curve", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.legend()

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save
    if output_path is None:
        output_path = CHARTS_DIR / "equity_curve.png"

    plt.savefig(output_path, dpi=100, bbox_inches="tight")
    plt.close()

    return "charts/equity_curve.png"


def generate_drawdown_chart(
    perf_log: list[dict], output_path: Optional[Path] = None
) -> Optional[str]:
    """Generate drawdown chart."""
    if not MATPLOTLIB_AVAILABLE or not perf_log or len(perf_log) < 2:
        return None

    # Extract data
    dates = []
    equity_values = []
    for entry in perf_log:
        date_str = entry.get("date", "")
        equity = entry.get("equity", 100000)
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str)
                dates.append(dt)
                equity_values.append(equity)
            except:
                pass

    if len(dates) < 2:
        return None

    # Calculate drawdown
    peak = equity_values[0]
    drawdowns = []
    for equity in equity_values:
        if equity > peak:
            peak = equity
        drawdown = ((peak - equity) / peak * 100) if peak > 0 else 0.0
        drawdowns.append(drawdown)

    # Create chart
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.fill_between(dates, drawdowns, 0, alpha=0.5, color="#dc2626", label="Drawdown")
    ax.plot(dates, drawdowns, linewidth=2, color="#dc2626")
    ax.set_xlabel("Date", fontsize=10)
    ax.set_ylabel("Drawdown (%)", fontsize=10)
    ax.set_title("Drawdown Over Time", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.legend()

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save
    if output_path is None:
        output_path = CHARTS_DIR / "drawdown.png"

    plt.savefig(output_path, dpi=100, bbox_inches="tight")
    plt.close()

    return "charts/drawdown.png"


def generate_daily_pl_chart(
    perf_log: list[dict], output_path: Optional[Path] = None
) -> Optional[str]:
    """Generate daily P/L bar chart."""
    if not MATPLOTLIB_AVAILABLE or not perf_log or len(perf_log) < 2:
        return None

    # Extract data
    dates = []
    pl_values = []
    for entry in perf_log:
        date_str = entry.get("date", "")
        pl = entry.get("pl", 0)
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str)
                dates.append(dt)
                pl_values.append(pl)
            except:
                pass

    if len(dates) < 2:
        return None

    # Create chart
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ["#10b981" if pl >= 0 else "#ef4444" for pl in pl_values]
    ax.bar(dates, pl_values, color=colors, alpha=0.7, width=0.8)
    ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax.set_xlabel("Date", fontsize=10)
    ax.set_ylabel("Daily P/L ($)", fontsize=10)
    ax.set_title("Daily Profit/Loss", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="y")

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save
    if output_path is None:
        output_path = CHARTS_DIR / "daily_pl.png"

    plt.savefig(output_path, dpi=100, bbox_inches="tight")
    plt.close()

    return "charts/daily_pl.png"


def generate_rolling_sharpe_chart(
    perf_log: list[dict], window: int = 7, output_path: Optional[Path] = None
) -> Optional[str]:
    """Generate rolling Sharpe ratio chart."""
    if not MATPLOTLIB_AVAILABLE or not perf_log or len(perf_log) < window + 1:
        return None

    # Extract returns
    dates = []
    equity_values = []
    for entry in perf_log:
        date_str = entry.get("date", "")
        equity = entry.get("equity", 100000)
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str)
                dates.append(dt)
                equity_values.append(equity)
            except:
                pass

    if len(dates) < window + 1:
        return None

    # Calculate rolling Sharpe
    returns = []
    for i in range(1, len(equity_values)):
        if equity_values[i - 1] > 0:
            ret = (equity_values[i] - equity_values[i - 1]) / equity_values[i - 1]
            returns.append(ret)

    if len(returns) < window:
        return None

    rolling_sharpe = []
    rolling_dates = []

    for i in range(window, len(returns)):
        window_returns = returns[i - window : i]
        if len(window_returns) > 1:
            mean_ret = np.mean(window_returns)
            std_ret = np.std(window_returns)
            sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0.0
            rolling_sharpe.append(sharpe)
            # Use the date corresponding to the end of the window
            rolling_dates.append(dates[i])
        else:
            rolling_sharpe.append(0.0)
            rolling_dates.append(dates[i])

    if len(rolling_dates) == 0 or len(rolling_sharpe) == 0:
        return None

    # Ensure dates and sharpe arrays have same length
    min_len = min(len(rolling_dates), len(rolling_sharpe))
    rolling_dates = rolling_dates[:min_len]
    rolling_sharpe = rolling_sharpe[:min_len]

    # Create chart
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(
        rolling_dates,
        rolling_sharpe,
        linewidth=2,
        color="#8b5cf6",
        label=f"Rolling Sharpe ({window}d)",
    )
    ax.axhline(y=1.0, color="green", linestyle="--", linewidth=1, label="Target (1.0)")
    ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax.set_xlabel("Date", fontsize=10)
    ax.set_ylabel("Sharpe Ratio", fontsize=10)
    ax.set_title(f"Rolling Sharpe Ratio ({window}-Day Window)", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.legend()

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save
    if output_path is None:
        output_path = CHARTS_DIR / f"rolling_sharpe_{window}d.png"

    plt.savefig(output_path, dpi=100, bbox_inches="tight")
    plt.close()

    return f"charts/rolling_sharpe_{window}d.png"


def generate_attribution_bar_chart(
    strategy_data: dict[str, dict], output_path: Optional[Path] = None
) -> Optional[str]:
    """Generate performance attribution bar chart by strategy."""
    if not MATPLOTLIB_AVAILABLE or not strategy_data:
        return None

    strategies = []
    pl_values = []
    colors = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"]

    for i, (strategy_name, data) in enumerate(strategy_data.items()):
        strategies.append(strategy_name.replace("_", " ").title())
        pl_values.append(data.get("pl", 0.0))
        if i >= len(colors):
            colors.append("#6b7280")

    if len(strategies) == 0:
        return None

    # Create chart
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(strategies, pl_values, color=colors[: len(strategies)], alpha=0.7)
    ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax.set_xlabel("Strategy", fontsize=10)
    ax.set_ylabel("P/L ($)", fontsize=10)
    ax.set_title("Performance Attribution by Strategy", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="y")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height + (0.01 * max(pl_values) if max(pl_values) > 0 else -0.01 * min(pl_values)),
            f"${height:.2f}",
            ha="center",
            va="bottom" if height >= 0 else "top",
            fontsize=9,
        )

    # Save
    if output_path is None:
        output_path = CHARTS_DIR / "attribution_bar.png"

    plt.savefig(output_path, dpi=100, bbox_inches="tight")
    plt.close()

    return "charts/attribution_bar.png"


def generate_regime_timeline_chart(
    perf_log: list[dict],
    regime_data: Optional[dict] = None,
    output_path: Optional[Path] = None,
) -> Optional[str]:
    """Generate market regime timeline chart."""
    if not MATPLOTLIB_AVAILABLE or not perf_log or len(perf_log) < 2:
        return None

    # Extract dates
    dates = []
    equity_values = []
    for entry in perf_log:
        date_str = entry.get("date", "")
        equity = entry.get("equity", 100000)
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str)
                dates.append(dt)
                equity_values.append(equity)
            except:
                pass

    if len(dates) < 2:
        return None

    # Calculate returns to infer regime
    returns = []
    for i in range(1, len(equity_values)):
        if equity_values[i - 1] > 0:
            ret = (equity_values[i] - equity_values[i - 1]) / equity_values[i - 1]
            returns.append(ret)

    if len(returns) == 0:
        return None

    # Classify regime based on returns
    regime_colors = {
        "BULL": "#10b981",  # Green
        "BEAR": "#ef4444",  # Red
        "SIDEWAYS": "#f59e0b",  # Orange
        "VOLATILE": "#8b5cf6",  # Purple
    }

    regimes = []
    regime_dates = dates[1:]  # One less date than equity values

    for ret in returns:
        abs_ret = abs(ret)
        if ret > 0.002:  # >0.2% positive
            regimes.append("BULL")
        elif ret < -0.002:  # <-0.2% negative
            regimes.append("BEAR")
        elif abs_ret > 0.005:  # High volatility
            regimes.append("VOLATILE")
        else:
            regimes.append("SIDEWAYS")

    # Create chart
    fig, ax = plt.subplots(figsize=(14, 6))

    # Plot equity curve
    ax.plot(dates, equity_values, linewidth=2, color="#2563eb", alpha=0.3, label="Equity")

    # Color background by regime
    for i, (date, regime) in enumerate(zip(regime_dates, regimes)):
        if i < len(regime_dates) - 1:
            next_date = regime_dates[i + 1]
            color = regime_colors.get(regime, "#6b7280")
            ax.axvspan(date, next_date, alpha=0.2, color=color)

    # Add regime legend
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=color, alpha=0.3, label=regime) for regime, color in regime_colors.items()
    ]
    ax.legend(handles=legend_elements, loc="upper left")

    ax.set_xlabel("Date", fontsize=10)
    ax.set_ylabel("Equity ($)", fontsize=10)
    ax.set_title("Market Regime Timeline", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save
    if output_path is None:
        output_path = CHARTS_DIR / "regime_timeline.png"

    plt.savefig(output_path, dpi=100, bbox_inches="tight")
    plt.close()

    return "charts/regime_timeline.png"


def generate_all_charts(
    perf_log: list[dict], strategy_data: Optional[dict[str, dict]] = None
) -> dict[str, Optional[str]]:
    """Generate all charts and return paths."""
    charts = {}

    charts["equity_curve"] = generate_equity_curve_chart(perf_log)
    charts["drawdown"] = generate_drawdown_chart(perf_log)
    charts["daily_pl"] = generate_daily_pl_chart(perf_log)
    charts["rolling_sharpe_7d"] = generate_rolling_sharpe_chart(perf_log, window=7)
    charts["rolling_sharpe_30d"] = generate_rolling_sharpe_chart(perf_log, window=30)

    # Attribution chart (requires strategy data)
    if strategy_data:
        charts["attribution_bar"] = generate_attribution_bar_chart(strategy_data)

    # Regime timeline
    charts["regime_timeline"] = generate_regime_timeline_chart(perf_log)

    return charts


if __name__ == "__main__":
    # Test chart generation
    from scripts.dashboard_metrics import load_json_file

    perf_log = load_json_file(DATA_DIR / "performance_log.json")
    if isinstance(perf_log, list):
        charts = generate_all_charts(perf_log)
        print("Generated charts:")
        for name, path in charts.items():
            if path:
                print(f"  ✅ {name}: {path}")
            else:
                print(f"  ❌ {name}: Not generated (insufficient data)")
