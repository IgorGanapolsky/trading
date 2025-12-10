"""
Canonical Baselines - Benchmark Strategies for Model Comparison

This module provides canonical baseline strategies that any new model must beat:

1. Buy-and-Hold: Simple buy and hold benchmark
2. Equal Weight: Equal allocation across assets
3. Moving Average Crossover: Classic trend following
4. Momentum (Time-Series): Past winners continue winning
5. Momentum (Cross-Sectional): Long winners, short losers
6. Mean Reversion: Fade extreme moves

These baselines establish the performance floor for any ML model.
A model that can't beat these baselines is not worth deploying.

Author: Trading System
Created: 2025-12-02
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Results from a strategy backtest."""

    strategy_name: str
    total_return: float
    annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_holding_period: float
    calmar_ratio: float

    # Time series
    equity_curve: pd.Series
    returns: pd.Series
    positions: pd.DataFrame
    trades: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    start_date: str = ""
    end_date: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "annual_volatility": self.annual_volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
            "avg_holding_period": self.avg_holding_period,
            "calmar_ratio": self.calmar_ratio,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "metadata": self.metadata,
        }


class BaselineStrategy(ABC):
    """Abstract base class for baseline strategies."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate trading signals from data."""
        pass

    def backtest(
        self,
        data: pd.DataFrame,
        initial_capital: float = 100000.0,
        transaction_cost: float = 0.001,
    ) -> BacktestResult:
        """
        Backtest the strategy.

        Args:
            data: OHLCV DataFrame
            initial_capital: Starting capital
            transaction_cost: Cost per trade as fraction

        Returns:
            BacktestResult with performance metrics
        """
        signals = self.generate_signals(data)

        # Calculate returns
        close = data["Close"]
        returns = close.pct_change()

        # Strategy returns (signal * next day return)
        positions = signals.shift(1)  # Trade on next bar
        strategy_returns = positions * returns

        # Apply transaction costs
        trades = (positions.diff().abs() > 0).sum()
        trade_dates = positions.diff().abs() > 0
        strategy_returns.loc[trade_dates] -= transaction_cost

        # Calculate metrics
        equity_curve = initial_capital * (1 + strategy_returns).cumprod()

        # Performance metrics
        total_return = (equity_curve.iloc[-1] / initial_capital) - 1
        n_years = len(data) / 252
        annual_return = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0
        annual_vol = strategy_returns.std() * np.sqrt(252)
        sharpe = annual_return / annual_vol if annual_vol > 0 else 0

        # Downside deviation for Sortino
        downside = strategy_returns[strategy_returns < 0]
        downside_vol = downside.std() * np.sqrt(252) if len(downside) > 0 else annual_vol
        sortino = annual_return / downside_vol if downside_vol > 0 else 0

        # Drawdown
        running_max = equity_curve.cummax()
        drawdown = (equity_curve - running_max) / running_max
        max_dd = drawdown.min()

        # Win rate
        daily_pnl = strategy_returns.dropna()
        win_rate = (daily_pnl > 0).mean() if len(daily_pnl) > 0 else 0

        # Profit factor
        gains = daily_pnl[daily_pnl > 0].sum()
        losses = abs(daily_pnl[daily_pnl < 0].sum())
        profit_factor = gains / losses if losses > 0 else float("inf")

        # Calmar ratio
        calmar = annual_return / abs(max_dd) if max_dd != 0 else 0

        return BacktestResult(
            strategy_name=self.name,
            total_return=float(total_return),
            annual_return=float(annual_return),
            annual_volatility=float(annual_vol),
            sharpe_ratio=float(sharpe),
            sortino_ratio=float(sortino),
            max_drawdown=float(max_dd),
            win_rate=float(win_rate),
            profit_factor=float(profit_factor),
            total_trades=int(trades),
            avg_holding_period=len(data) / max(trades, 1),
            calmar_ratio=float(calmar),
            equity_curve=equity_curve,
            returns=strategy_returns,
            positions=pd.DataFrame({"position": positions}),
            start_date=str(data.index[0])[:10],
            end_date=str(data.index[-1])[:10],
        )


class BuyAndHoldBaseline(BaselineStrategy):
    """Buy and hold benchmark - always long."""

    def __init__(self):
        super().__init__("Buy and Hold")

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Always return 1 (fully invested)."""
        return pd.Series(1.0, index=data.index)


class EqualWeightBaseline(BaselineStrategy):
    """Equal weight across assets (for multi-asset data)."""

    def __init__(self):
        super().__init__("Equal Weight")

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Equal weight signal."""
        return pd.Series(1.0, index=data.index)


class MovingAverageCrossover(BaselineStrategy):
    """Moving average crossover strategy."""

    def __init__(self, fast_period: int = 20, slow_period: int = 50):
        super().__init__(f"MA Cross ({fast_period}/{slow_period})")
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Long when fast MA > slow MA, else flat."""
        close = data["Close"]
        fast_ma = close.rolling(self.fast_period).mean()
        slow_ma = close.rolling(self.slow_period).mean()

        signal = pd.Series(0.0, index=data.index)
        signal[fast_ma > slow_ma] = 1.0

        return signal


class TimeSeriesMomentum(BaselineStrategy):
    """Time-series momentum (trend following)."""

    def __init__(self, lookback: int = 252, holding_period: int = 21):
        super().__init__(f"TS Momentum ({lookback}d)")
        self.lookback = lookback
        self.holding_period = holding_period

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Long if past return positive, else flat."""
        close = data["Close"]
        past_return = close.pct_change(self.lookback)

        signal = pd.Series(0.0, index=data.index)
        signal[past_return > 0] = 1.0

        return signal


class CrossSectionalMomentum(BaselineStrategy):
    """Cross-sectional momentum (relative strength)."""

    def __init__(self, lookback: int = 252, top_n: int = 3):
        super().__init__(f"XS Momentum (top {top_n})")
        self.lookback = lookback
        self.top_n = top_n

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """For single asset, use time-series momentum."""
        close = data["Close"]
        momentum = close.pct_change(self.lookback)

        # For single asset, signal is 1 if momentum > 0
        signal = pd.Series(0.0, index=data.index)
        signal[momentum > 0] = 1.0

        return signal

    def generate_multi_asset_signals(self, returns: pd.DataFrame) -> pd.DataFrame:
        """For multiple assets, rank by momentum."""
        momentum = returns.rolling(self.lookback).apply(lambda x: (1 + x).prod() - 1)

        # Rank assets
        ranks = momentum.rank(axis=1, ascending=False)

        # Long top N
        signals = (ranks <= self.top_n).astype(float)

        # Equal weight among selected
        signals = signals.div(signals.sum(axis=1), axis=0).fillna(0)

        return signals


class MeanReversionBaseline(BaselineStrategy):
    """Mean reversion (contrarian) strategy."""

    def __init__(self, lookback: int = 20, z_threshold: float = 2.0):
        super().__init__(f"Mean Reversion ({lookback}d, z={z_threshold})")
        self.lookback = lookback
        self.z_threshold = z_threshold

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Long when oversold (z < -threshold), short when overbought."""
        close = data["Close"]
        ma = close.rolling(self.lookback).mean()
        std = close.rolling(self.lookback).std()
        z_score = (close - ma) / (std + 1e-8)

        signal = pd.Series(0.0, index=data.index)
        signal[z_score < -self.z_threshold] = 1.0  # Oversold -> Long
        signal[z_score > self.z_threshold] = 0.0  # Overbought -> Flat (or short)

        return signal


class RSIMeanReversion(BaselineStrategy):
    """RSI-based mean reversion."""

    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70):
        super().__init__(f"RSI Mean Reversion ({period})")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Long when RSI oversold, flat when overbought."""
        close = data["Close"]

        # Calculate RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.period).mean()
        rs = gain / (loss + 1e-8)
        rsi = 100 - (100 / (1 + rs))

        signal = pd.Series(0.5, index=data.index)  # Neutral
        signal[rsi < self.oversold] = 1.0  # Oversold -> Long
        signal[rsi > self.overbought] = 0.0  # Overbought -> Flat

        return signal


class VolatilityBreakout(BaselineStrategy):
    """Volatility breakout strategy (Turtle-style)."""

    def __init__(self, lookback: int = 20, atr_mult: float = 2.0):
        super().__init__(f"Vol Breakout ({lookback}d)")
        self.lookback = lookback
        self.atr_mult = atr_mult

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Long on upside breakout, flat otherwise."""
        close = data["Close"]
        high = data["High"]
        low = data["Low"]

        # Calculate ATR
        tr = pd.concat(
            [
                high - low,
                abs(high - close.shift(1)),
                abs(low - close.shift(1)),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(self.lookback).mean()

        # Breakout levels
        upper = close.shift(1) + self.atr_mult * atr
        # Note: lower breakout not used for long-only strategy

        signal = pd.Series(0.0, index=data.index)
        signal[close > upper] = 1.0  # Upside breakout

        return signal


def run_baseline_comparison(
    data: pd.DataFrame,
    initial_capital: float = 100000.0,
    include_all: bool = True,
) -> pd.DataFrame:
    """
    Run all baseline strategies and compare performance.

    Args:
        data: OHLCV DataFrame
        initial_capital: Starting capital
        include_all: Include all baseline strategies

    Returns:
        DataFrame comparing all strategies
    """
    strategies = [
        BuyAndHoldBaseline(),
        MovingAverageCrossover(20, 50),
        MovingAverageCrossover(50, 200),
        TimeSeriesMomentum(126),
        TimeSeriesMomentum(252),
        MeanReversionBaseline(20, 2.0),
        RSIMeanReversion(14, 30, 70),
    ]

    if include_all:
        strategies.extend(
            [
                VolatilityBreakout(20, 2.0),
                CrossSectionalMomentum(126),
            ]
        )

    results = []
    for strategy in strategies:
        try:
            result = strategy.backtest(data, initial_capital)
            results.append(result.to_dict())
            logger.info(
                f"{strategy.name}: Return={result.total_return:.2%}, "
                f"Sharpe={result.sharpe_ratio:.2f}, MaxDD={result.max_drawdown:.2%}"
            )
        except Exception as e:
            logger.warning(f"Failed to backtest {strategy.name}: {e}")

    comparison = pd.DataFrame(results)

    # Sort by Sharpe ratio
    comparison = comparison.sort_values("sharpe_ratio", ascending=False)

    return comparison


def check_model_beats_baselines(
    model_result: BacktestResult,
    baseline_results: pd.DataFrame,
    min_sharpe_improvement: float = 0.1,
) -> dict[str, Any]:
    """
    Check if a model beats all baseline strategies.

    Args:
        model_result: Model backtest result
        baseline_results: DataFrame of baseline results
        min_sharpe_improvement: Minimum Sharpe improvement required

    Returns:
        Dictionary with comparison results
    """
    model_sharpe = model_result.sharpe_ratio
    max_baseline_sharpe = baseline_results["sharpe_ratio"].max()
    best_baseline = baseline_results.loc[baseline_results["sharpe_ratio"].idxmax(), "strategy_name"]

    beats_all = model_sharpe > max_baseline_sharpe + min_sharpe_improvement

    return {
        "model_sharpe": model_sharpe,
        "best_baseline_sharpe": max_baseline_sharpe,
        "best_baseline_name": best_baseline,
        "sharpe_improvement": model_sharpe - max_baseline_sharpe,
        "beats_all_baselines": beats_all,
        "recommendation": (
            "DEPLOY"
            if beats_all
            else f"DO NOT DEPLOY - Model must beat {best_baseline} (Sharpe {max_baseline_sharpe:.2f})"
        ),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("CANONICAL BASELINES DEMO")
    print("=" * 80)

    # Create sample data
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=1000, freq="D")
    close = 100 * (1 + np.random.randn(1000).cumsum() * 0.01)

    data = pd.DataFrame(
        {
            "Open": close * (1 + np.random.randn(1000) * 0.005),
            "High": close * (1 + np.abs(np.random.randn(1000)) * 0.015),
            "Low": close * (1 - np.abs(np.random.randn(1000)) * 0.015),
            "Close": close,
            "Volume": np.random.randint(1000000, 10000000, 1000),
        },
        index=dates,
    )

    # Run comparison
    print("\nRunning baseline comparison...")
    comparison = run_baseline_comparison(data)

    print("\n" + "=" * 80)
    print("BASELINE COMPARISON RESULTS")
    print("=" * 80)

    display_cols = [
        "strategy_name",
        "total_return",
        "annual_return",
        "sharpe_ratio",
        "max_drawdown",
        "win_rate",
    ]
    print(comparison[display_cols].to_string(index=False))

    print("\n" + "=" * 80)
    print("KEY INSIGHT: Any ML model must beat these baselines to be worth deploying!")
    print("=" * 80)
