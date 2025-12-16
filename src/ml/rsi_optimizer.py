"""
RSI Threshold Optimizer for Crypto Trading

This module optimizes the RSI threshold for crypto entry signals using historical data.
It backtests different RSI thresholds and calculates performance metrics to find the optimal value.

Key Features:
- Load historical crypto data (90+ days)
- Grid search over RSI thresholds (40, 45, 50, 55, 60)
- Calculate win rate, average return, Sharpe ratio
- Generate actionable insights
- Save results to JSON

Usage:
    from src.ml.rsi_optimizer import RSIOptimizer

    optimizer = RSIOptimizer(symbol="BTC-USD", lookback_days=90)
    results = optimizer.optimize()
    print(f"Optimal RSI: {results['best_threshold']}")
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from src.utils.technical_indicators import calculate_macd, calculate_rsi, calculate_volume_ratio

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Results from backtesting a single RSI threshold."""

    threshold: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_return: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    trades: list[dict]


class RSIOptimizer:
    """
    Optimize RSI threshold for crypto trading using historical backtesting.

    This class implements a grid search over different RSI thresholds and
    evaluates trading performance to find the optimal entry signal.

    Attributes:
        symbol: Crypto symbol to optimize (e.g., "BTC-USD")
        lookback_days: Number of historical days to use for optimization
        thresholds: List of RSI thresholds to test
        initial_capital: Starting capital for backtesting
        position_size: Position size as fraction of capital (0-1)
    """

    # Default RSI thresholds to test
    DEFAULT_THRESHOLDS = [40, 45, 50, 55, 60]

    def __init__(
        self,
        symbol: str = "BTC-USD",
        lookback_days: int = 90,
        thresholds: list[float] | None = None,
        initial_capital: float = 10000.0,
        position_size: float = 1.0,
    ):
        """
        Initialize RSI Optimizer.

        Args:
            symbol: Crypto symbol (e.g., "BTC-USD", "ETH-USD")
            lookback_days: Days of historical data to use (default: 90)
            thresholds: RSI thresholds to test (default: [40, 45, 50, 55, 60])
            initial_capital: Starting capital for backtesting
            position_size: Position size as fraction of capital
        """
        self.symbol = symbol
        self.lookback_days = lookback_days
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self.initial_capital = initial_capital
        self.position_size = position_size

        # Historical data
        self.data: pd.DataFrame | None = None

        logger.info(
            f"RSIOptimizer initialized: {symbol}, {lookback_days} days, "
            f"thresholds={self.thresholds}"
        )

    def load_data(self) -> pd.DataFrame:
        """
        Load historical crypto data from yfinance.

        Returns:
            DataFrame with OHLCV data

        Raises:
            ValueError: If data cannot be loaded
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.lookback_days + 30)  # Extra buffer

        logger.info(f"Loading {self.symbol} data from {start_date.date()} to {end_date.date()}")

        try:
            ticker = yf.Ticker(self.symbol)
            data = ticker.history(start=start_date, end=end_date)

            if data.empty or len(data) < self.lookback_days * 0.7:
                raise ValueError(
                    f"Insufficient data for {self.symbol}: got {len(data)} bars, "
                    f"need at least {int(self.lookback_days * 0.7)}"
                )

            logger.info(f"Successfully loaded {len(data)} bars for {self.symbol}")
            self.data = data
            return data

        except Exception as e:
            raise ValueError(f"Failed to load data for {self.symbol}: {e}") from e

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators (RSI, MACD, Volume Ratio).

        Args:
            data: OHLCV DataFrame

        Returns:
            DataFrame with indicators added as columns
        """
        df = data.copy()

        # Calculate RSI for each row (using rolling window)
        rsi_values = []
        for i in range(len(df)):
            if i < 14:
                rsi_values.append(50.0)  # Neutral RSI for initial period
            else:
                prices_slice = df["Close"].iloc[: i + 1]
                rsi = calculate_rsi(prices_slice, period=14)
                rsi_values.append(rsi)

        df["RSI"] = rsi_values

        # Calculate MACD (vectorized)
        macd_values = []
        macd_signals = []
        macd_histograms = []

        for i in range(len(df)):
            if i < 26:
                macd_values.append(0.0)
                macd_signals.append(0.0)
                macd_histograms.append(0.0)
            else:
                prices_slice = df["Close"].iloc[: i + 1]
                macd, signal, histogram = calculate_macd(prices_slice)
                macd_values.append(macd)
                macd_signals.append(signal)
                macd_histograms.append(histogram)

        df["MACD"] = macd_values
        df["MACD_Signal"] = macd_signals
        df["MACD_Histogram"] = macd_histograms

        # Calculate Volume Ratio (vectorized)
        volume_ratios = []
        for i in range(len(df)):
            if i < 20:
                volume_ratios.append(1.0)
            else:
                hist_slice = df.iloc[: i + 1]
                vol_ratio = calculate_volume_ratio(hist_slice, window=20)
                volume_ratios.append(vol_ratio)

        df["Volume_Ratio"] = volume_ratios

        logger.info(f"Calculated indicators for {len(df)} bars")
        return df

    def backtest_threshold(self, threshold: float, data: pd.DataFrame) -> BacktestResult:
        """
        Backtest a single RSI threshold using simple buy-and-hold with entry signals.

        Strategy:
        - Buy when RSI > threshold AND MACD > 0 AND Volume Ratio > 0.8
        - Hold until conditions reverse
        - Track all trades and calculate metrics

        Args:
            threshold: RSI threshold to test
            data: DataFrame with indicators

        Returns:
            BacktestResult with performance metrics
        """
        capital = self.initial_capital
        position = 0.0  # Current position size
        entry_price = 0.0

        trades = []
        equity_curve = [capital]

        for i in range(26, len(data)):  # Start after warm-up period
            row = data.iloc[i]
            rsi = row["RSI"]
            macd_hist = row["MACD_Histogram"]
            volume_ratio = row["Volume_Ratio"]
            price = row["Close"]

            # Entry signal: RSI > threshold, MACD bullish, Volume confirmation
            entry_signal = (
                rsi > threshold
                and macd_hist > 0
                and volume_ratio > 0.8
            )

            # Exit signal: RSI drops back below threshold OR MACD turns bearish
            exit_signal = (
                rsi <= threshold
                or macd_hist < 0
            )

            # Enter position
            if position == 0 and entry_signal:
                position = (capital * self.position_size) / price
                entry_price = price
                logger.debug(
                    f"ENTER: {data.index[i].date()} @ ${price:.2f}, "
                    f"RSI={rsi:.1f}, MACD={macd_hist:.2f}"
                )

            # Exit position
            elif position > 0 and exit_signal:
                exit_price = price
                trade_return = (exit_price - entry_price) / entry_price
                profit = position * (exit_price - entry_price)
                capital += profit

                trades.append({
                    "entry_date": data.index[i - 1].strftime("%Y-%m-%d"),
                    "exit_date": data.index[i].strftime("%Y-%m-%d"),
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "return": round(trade_return * 100, 2),
                    "profit": round(profit, 2),
                    "rsi_at_entry": round(rsi, 1),
                })

                logger.debug(
                    f"EXIT: {data.index[i].date()} @ ${price:.2f}, "
                    f"Return={trade_return * 100:.2f}%"
                )

                position = 0.0
                entry_price = 0.0

            # Update equity curve
            if position > 0:
                current_equity = capital - (position * entry_price) + (position * price)
            else:
                current_equity = capital

            equity_curve.append(current_equity)

        # Calculate metrics
        winning_trades = sum(1 for t in trades if t["return"] > 0)
        losing_trades = sum(1 for t in trades if t["return"] <= 0)
        total_trades = len(trades)

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        returns = [t["return"] / 100 for t in trades]  # Convert to decimal
        avg_return = np.mean(returns) if returns else 0.0
        total_return = (capital - self.initial_capital) / self.initial_capital

        # Sharpe ratio (annualized, assuming ~252 trading days)
        # Apply volatility floor to prevent extreme Sharpe ratios
        MIN_VOLATILITY_FLOOR = 0.001  # Increased from 0.0001 to prevent extreme ratios
        if returns and len(returns) > 1:
            std_return = np.std(returns, ddof=1)
            # Apply volatility floor
            std_return = max(std_return, MIN_VOLATILITY_FLOOR)
            sharpe_ratio = (avg_return / std_return) * np.sqrt(252)
            # Clamp to reasonable bounds [-10, 10]
            sharpe_ratio = np.clip(sharpe_ratio, -10.0, 10.0)
        else:
            sharpe_ratio = 0.0

        # Max drawdown
        equity_arr = np.array(equity_curve)
        running_max = np.maximum.accumulate(equity_arr)
        drawdown = (equity_arr - running_max) / running_max
        max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0.0

        logger.info(
            f"Threshold {threshold}: {total_trades} trades, {win_rate:.1f}% win rate, "
            f"Sharpe={sharpe_ratio:.2f}, Total Return={total_return * 100:.2f}%"
        )

        return BacktestResult(
            threshold=threshold,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_return=avg_return,
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            trades=trades,
        )

    def optimize(self) -> dict[str, Any]:
        """
        Run optimization across all RSI thresholds and find the best one.

        Returns:
            Dictionary with optimization results including:
            - best_threshold: Optimal RSI threshold
            - best_sharpe: Sharpe ratio at optimal threshold
            - all_results: Results for all thresholds
            - recommendation: Trading recommendation
        """
        logger.info("=" * 80)
        logger.info("Starting RSI Threshold Optimization")
        logger.info("=" * 80)

        # Load data
        if self.data is None:
            self.load_data()

        # Calculate indicators
        data_with_indicators = self.calculate_indicators(self.data)

        # Backtest each threshold
        results = []
        for threshold in self.thresholds:
            result = self.backtest_threshold(threshold, data_with_indicators)
            results.append(result)

        # Find best threshold (optimize for Sharpe ratio)
        best_result = max(results, key=lambda r: r.sharpe_ratio)

        # Compile results
        optimization_results = {
            "symbol": self.symbol,
            "lookback_days": self.lookback_days,
            "optimization_date": datetime.now().isoformat(),
            "best_threshold": best_result.threshold,
            "best_sharpe": round(best_result.sharpe_ratio, 3),
            "best_win_rate": round(best_result.win_rate, 2),
            "best_total_return": round(best_result.total_return * 100, 2),
            "all_results": [
                {
                    "threshold": r.threshold,
                    "total_trades": r.total_trades,
                    "win_rate": round(r.win_rate, 2),
                    "avg_return": round(r.avg_return * 100, 2),
                    "total_return": round(r.total_return * 100, 2),
                    "sharpe_ratio": round(r.sharpe_ratio, 3),
                    "max_drawdown": round(r.max_drawdown * 100, 2),
                }
                for r in results
            ],
            "recommendation": self._generate_recommendation(best_result),
        }

        logger.info("=" * 80)
        logger.info("OPTIMIZATION COMPLETE")
        logger.info(f"Best RSI Threshold: {best_result.threshold}")
        logger.info(f"Sharpe Ratio: {best_result.sharpe_ratio:.3f}")
        logger.info(f"Win Rate: {best_result.win_rate:.2f}%")
        logger.info(f"Total Return: {best_result.total_return * 100:.2f}%")
        logger.info("=" * 80)

        return optimization_results

    def _generate_recommendation(self, result: BacktestResult) -> str:
        """Generate trading recommendation based on results."""
        if result.sharpe_ratio > 1.5 and result.win_rate > 55:
            return (
                f"STRONG BUY: RSI > {result.threshold} shows excellent risk-adjusted returns "
                f"(Sharpe {result.sharpe_ratio:.2f}, {result.win_rate:.1f}% win rate)"
            )
        elif result.sharpe_ratio > 1.0 and result.win_rate > 50:
            return (
                f"BUY: RSI > {result.threshold} shows good risk-adjusted returns "
                f"(Sharpe {result.sharpe_ratio:.2f}, {result.win_rate:.1f}% win rate)"
            )
        elif result.sharpe_ratio > 0.5:
            return (
                f"NEUTRAL: RSI > {result.threshold} shows moderate performance "
                f"(Sharpe {result.sharpe_ratio:.2f}, {result.win_rate:.1f}% win rate)"
            )
        else:
            return (
                f"CAUTION: RSI > {result.threshold} shows weak performance "
                f"(Sharpe {result.sharpe_ratio:.2f}, {result.win_rate:.1f}% win rate). "
                f"Consider alternative thresholds or strategies."
            )

    def save_results(self, results: dict[str, Any], output_path: str | Path) -> None:
        """
        Save optimization results to JSON file.

        Args:
            results: Optimization results dictionary
            output_path: Path to save JSON file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"Results saved to {output_path}")


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Optimize BTC RSI threshold
    optimizer = RSIOptimizer(symbol="BTC-USD", lookback_days=90)
    results = optimizer.optimize()

    # Save results
    optimizer.save_results(results, "data/rsi_optimization_results.json")

    # Print summary
    print("\n" + "=" * 80)
    print("RSI OPTIMIZATION SUMMARY")
    print("=" * 80)
    print(f"Symbol: {results['symbol']}")
    print(f"Optimal RSI Threshold: {results['best_threshold']}")
    print(f"Sharpe Ratio: {results['best_sharpe']}")
    print(f"Win Rate: {results['best_win_rate']}%")
    print(f"Total Return: {results['best_total_return']}%")
    print(f"\nRecommendation: {results['recommendation']}")
    print("=" * 80)
