"""
Trading-Specific Experiment Templates.

Pre-built experiment functions for common trading research:
- Strategy parameter optimization
- Indicator tuning
- Risk parameter sweeps
- Model comparison
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from src.experiments.experiment_runner import (
    ExperimentResult,
    HyperparameterGrid,
)

logger = logging.getLogger(__name__)


@dataclass
class MockOHLCV:
    """Mock OHLCV data for testing."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def generate_mock_data(n_bars: int = 1000, volatility: float = 0.02) -> list[dict[str, float]]:
    """Generate mock price data for backtesting."""
    import random

    data = []
    price = 100.0

    for i in range(n_bars):
        # Random walk with drift
        change = random.gauss(0.0001, volatility)
        price *= 1 + change

        high = price * (1 + abs(random.gauss(0, volatility / 2)))
        low = price * (1 - abs(random.gauss(0, volatility / 2)))

        data.append(
            {
                "timestamp": i,
                "open": price * (1 + random.gauss(0, volatility / 4)),
                "high": high,
                "low": low,
                "close": price,
                "volume": random.uniform(1000, 10000),
            }
        )

    return data


def calculate_rsi(prices: list[float], period: int = 14) -> list[float]:
    """Calculate RSI indicator."""
    if len(prices) < period + 1:
        return [50.0] * len(prices)

    rsi_values = [50.0] * period  # Pad initial values

    gains = []
    losses = []

    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        gains.append(max(0, change))
        losses.append(max(0, -change))

    # Calculate initial averages
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(prices)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period

        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        rsi_values.append(rsi)

    return rsi_values


def calculate_macd(
    prices: list[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[list[float], list[float], list[float]]:
    """Calculate MACD indicator."""

    def ema(data: list[float], period: int) -> list[float]:
        result = []
        multiplier = 2 / (period + 1)

        # Start with SMA
        if len(data) < period:
            return [data[0]] * len(data)

        sma = sum(data[:period]) / period
        result = [sma] * period

        for i in range(period, len(data)):
            ema_val = (data[i] - result[-1]) * multiplier + result[-1]
            result.append(ema_val)

        return result

    fast_ema = ema(prices, fast_period)
    slow_ema = ema(prices, slow_period)

    macd_line = [f - s for f, s in zip(fast_ema, slow_ema)]
    signal_line = ema(macd_line, signal_period)
    histogram = [m - s for m, s in zip(macd_line, signal_line)]

    return macd_line, signal_line, histogram


def rsi_strategy_backtest(
    params: dict[str, Any], data: Optional[list[dict]] = None
) -> dict[str, float]:
    """
    Backtest RSI-based strategy.

    Params:
        rsi_period: RSI calculation period
        oversold: Buy threshold (e.g., 30)
        overbought: Sell threshold (e.g., 70)
        stop_loss_pct: Stop loss percentage
        take_profit_pct: Take profit percentage
    """
    if data is None:
        data = generate_mock_data(1000)

    prices = [d["close"] for d in data]
    rsi = calculate_rsi(prices, params.get("rsi_period", 14))

    oversold = params.get("oversold", 30)
    overbought = params.get("overbought", 70)
    stop_loss_pct = params.get("stop_loss_pct", 2.0)
    take_profit_pct = params.get("take_profit_pct", 4.0)

    trades = []
    position = None  # None or (entry_price, entry_idx)

    for i in range(1, len(data)):
        if position is None:
            # Check for entry
            if rsi[i] < oversold and rsi[i - 1] >= oversold:
                position = (prices[i], i)
        else:
            entry_price, entry_idx = position
            current_price = prices[i]
            pnl_pct = (current_price - entry_price) / entry_price * 100

            # Check exits
            exit_reason = None
            if pnl_pct <= -stop_loss_pct:
                exit_reason = "stop_loss"
            elif pnl_pct >= take_profit_pct:
                exit_reason = "take_profit"
            elif rsi[i] > overbought:
                exit_reason = "signal"

            if exit_reason:
                trades.append(
                    {
                        "pnl_pct": pnl_pct,
                        "bars_held": i - entry_idx,
                        "exit_reason": exit_reason,
                    }
                )
                position = None

    # Close any open position
    if position:
        entry_price, entry_idx = position
        pnl_pct = (prices[-1] - entry_price) / entry_price * 100
        trades.append(
            {
                "pnl_pct": pnl_pct,
                "bars_held": len(data) - entry_idx,
                "exit_reason": "end",
            }
        )

    return calculate_backtest_metrics(trades)


def macd_strategy_backtest(
    params: dict[str, Any], data: Optional[list[dict]] = None
) -> dict[str, float]:
    """
    Backtest MACD-based strategy.

    Params:
        macd_fast: Fast EMA period
        macd_slow: Slow EMA period
        macd_signal: Signal line period
        stop_loss_pct: Stop loss percentage
    """
    if data is None:
        data = generate_mock_data(1000)

    prices = [d["close"] for d in data]
    macd_line, signal_line, histogram = calculate_macd(
        prices,
        params.get("macd_fast", 12),
        params.get("macd_slow", 26),
        params.get("macd_signal", 9),
    )

    stop_loss_pct = params.get("stop_loss_pct", 2.0)

    trades = []
    position = None

    for i in range(1, len(data)):
        if position is None:
            # Buy on MACD crossover
            if histogram[i] > 0 and histogram[i - 1] <= 0:
                position = (prices[i], i)
        else:
            entry_price, entry_idx = position
            current_price = prices[i]
            pnl_pct = (current_price - entry_price) / entry_price * 100

            # Exit conditions
            exit_reason = None
            if pnl_pct <= -stop_loss_pct:
                exit_reason = "stop_loss"
            elif histogram[i] < 0 and histogram[i - 1] >= 0:
                exit_reason = "signal"

            if exit_reason:
                trades.append(
                    {
                        "pnl_pct": pnl_pct,
                        "bars_held": i - entry_idx,
                        "exit_reason": exit_reason,
                    }
                )
                position = None

    if position:
        entry_price, entry_idx = position
        pnl_pct = (prices[-1] - entry_price) / entry_price * 100
        trades.append(
            {
                "pnl_pct": pnl_pct,
                "bars_held": len(data) - entry_idx,
                "exit_reason": "end",
            }
        )

    return calculate_backtest_metrics(trades)


def combined_strategy_backtest(
    params: dict[str, Any], data: Optional[list[dict]] = None
) -> dict[str, float]:
    """
    Backtest combined RSI + MACD strategy.

    Entry: RSI oversold AND MACD bullish
    Exit: RSI overbought OR MACD bearish OR stop/target
    """
    if data is None:
        data = generate_mock_data(1000)

    prices = [d["close"] for d in data]

    # Calculate indicators
    rsi = calculate_rsi(prices, params.get("rsi_period", 14))
    macd_line, signal_line, histogram = calculate_macd(
        prices,
        params.get("macd_fast", 12),
        params.get("macd_slow", 26),
        params.get("macd_signal", 9),
    )

    oversold = params.get("oversold", 30)
    overbought = params.get("overbought", 70)
    stop_loss_pct = params.get("stop_loss_pct", 2.0)
    take_profit_pct = params.get("take_profit_pct", 5.0)

    trades = []
    position = None

    for i in range(1, len(data)):
        if position is None:
            # Entry: RSI oversold + MACD bullish
            rsi_entry = rsi[i] < oversold
            macd_entry = histogram[i] > 0

            if rsi_entry and macd_entry:
                position = (prices[i], i)
        else:
            entry_price, entry_idx = position
            current_price = prices[i]
            pnl_pct = (current_price - entry_price) / entry_price * 100

            # Exit conditions
            exit_reason = None
            if pnl_pct <= -stop_loss_pct:
                exit_reason = "stop_loss"
            elif pnl_pct >= take_profit_pct:
                exit_reason = "take_profit"
            elif rsi[i] > overbought:
                exit_reason = "rsi_overbought"
            elif histogram[i] < 0 and histogram[i - 1] >= 0:
                exit_reason = "macd_bearish"

            if exit_reason:
                trades.append(
                    {
                        "pnl_pct": pnl_pct,
                        "bars_held": i - entry_idx,
                        "exit_reason": exit_reason,
                    }
                )
                position = None

    if position:
        entry_price, entry_idx = position
        pnl_pct = (prices[-1] - entry_price) / entry_price * 100
        trades.append(
            {
                "pnl_pct": pnl_pct,
                "bars_held": len(data) - entry_idx,
                "exit_reason": "end",
            }
        )

    return calculate_backtest_metrics(trades)


def calculate_backtest_metrics(trades: list[dict]) -> dict[str, float]:
    """Calculate standard backtest metrics from trades."""
    if not trades:
        return {
            "total_return": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "num_trades": 0,
            "avg_profit": 0.0,
            "avg_loss": 0.0,
            "max_drawdown": 0.0,
            "avg_bars_held": 0.0,
        }

    pnls = [t["pnl_pct"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    total_return = sum(pnls)
    win_rate = len(wins) / len(trades) if trades else 0
    avg_profit = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0

    # Sharpe ratio (assuming daily returns, annualized)
    avg_return = total_return / len(trades)
    std_return = (
        math.sqrt(sum((p - avg_return) ** 2 for p in pnls) / len(pnls)) if len(pnls) > 1 else 1
    )
    sharpe_ratio = (avg_return / std_return) * math.sqrt(252) if std_return > 0 else 0

    # Sortino ratio (only downside deviation)
    negative_returns = [p for p in pnls if p < 0]
    downside_std = (
        math.sqrt(sum(p**2 for p in negative_returns) / len(negative_returns))
        if negative_returns
        else 1
    )
    sortino_ratio = (avg_return / downside_std) * math.sqrt(252) if downside_std > 0 else 0

    # Profit factor
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    # Max drawdown
    cumulative = 0
    peak = 0
    max_drawdown = 0
    for pnl in pnls:
        cumulative += pnl
        peak = max(peak, cumulative)
        drawdown = peak - cumulative
        max_drawdown = max(max_drawdown, drawdown)

    # Average holding period
    avg_bars_held = sum(t["bars_held"] for t in trades) / len(trades)

    return {
        "total_return": round(total_return, 4),
        "sharpe_ratio": round(sharpe_ratio, 4),
        "sortino_ratio": round(sortino_ratio, 4),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4),
        "num_trades": len(trades),
        "avg_profit": round(avg_profit, 4),
        "avg_loss": round(avg_loss, 4),
        "max_drawdown": round(max_drawdown, 4),
        "avg_bars_held": round(avg_bars_held, 2),
    }


# Pre-defined parameter grids

RSI_PARAMETER_GRID = HyperparameterGrid(
    {
        "rsi_period": [7, 10, 14, 21],
        "oversold": [20, 25, 30, 35],
        "overbought": [65, 70, 75, 80],
        "stop_loss_pct": [1.5, 2.0, 2.5, 3.0],
        "take_profit_pct": [3.0, 4.0, 5.0, 6.0],
    }
)

MACD_PARAMETER_GRID = HyperparameterGrid(
    {
        "macd_fast": [8, 10, 12, 14],
        "macd_slow": [21, 26, 30],
        "macd_signal": [7, 9, 11],
        "stop_loss_pct": [1.5, 2.0, 2.5, 3.0],
    }
)

COMBINED_PARAMETER_GRID = HyperparameterGrid(
    {
        "rsi_period": [10, 14, 21],
        "oversold": [25, 30, 35],
        "overbought": [65, 70, 75],
        "macd_fast": [10, 12, 14],
        "macd_slow": [24, 26, 28],
        "macd_signal": [8, 9, 10],
        "stop_loss_pct": [1.5, 2.0, 2.5],
        "take_profit_pct": [4.0, 5.0, 6.0],
    }
)


async def run_rsi_optimization(
    max_experiments: int = 100,
    parallel: bool = True,
) -> tuple[list[ExperimentResult], str]:
    """Run RSI strategy optimization."""
    from src.experiments import run_experiment_sweep

    # Use random search for large grids
    mode = "random" if RSI_PARAMETER_GRID.total_combinations > max_experiments else "grid"

    results, report = await run_experiment_sweep(
        experiment_fn=rsi_strategy_backtest,
        params=RSI_PARAMETER_GRID.params,
        mode=mode,
        n_samples=max_experiments,
        parallel=parallel,
    )

    return results, report


async def run_macd_optimization(
    max_experiments: int = 100,
    parallel: bool = True,
) -> tuple[list[ExperimentResult], str]:
    """Run MACD strategy optimization."""
    from src.experiments import run_experiment_sweep

    mode = "random" if MACD_PARAMETER_GRID.total_combinations > max_experiments else "grid"

    results, report = await run_experiment_sweep(
        experiment_fn=macd_strategy_backtest,
        params=MACD_PARAMETER_GRID.params,
        mode=mode,
        n_samples=max_experiments,
        parallel=parallel,
    )

    return results, report


async def run_full_optimization(
    max_experiments: int = 500,
    parallel: bool = True,
) -> tuple[list[ExperimentResult], str]:
    """Run combined strategy optimization."""
    from src.experiments import run_experiment_sweep

    mode = "random"  # Always random for combined grid (too large)

    results, report = await run_experiment_sweep(
        experiment_fn=combined_strategy_backtest,
        params=COMBINED_PARAMETER_GRID.params,
        mode=mode,
        n_samples=max_experiments,
        parallel=parallel,
    )

    return results, report
