"""
Automated Backtesting for LLM Signals

Tests LLM trading signals against historical data before going live.
Validates that signals would have been profitable in the past.

Created: Dec 11, 2025
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

BACKTEST_RESULTS_PATH = Path("data/backtest_results.json")


@dataclass
class BacktestResult:
    """Result of a signal backtest."""
    signal_id: str
    symbol: str
    signal_direction: str  # BUY/SELL
    model: str
    timestamp: str
    # Backtest metrics
    lookback_days: int
    win_rate: float
    avg_return: float
    max_drawdown: float
    sharpe_ratio: float
    total_trades: int
    profitable_trades: int
    # Validation
    is_valid: bool
    validation_message: str
    # Historical performance
    historical_returns: list[float]


class SignalBacktester:
    """
    Backtests LLM signals against historical data.

    Before acting on any LLM signal:
    1. Fetch historical price data
    2. Simulate what would have happened with similar signals
    3. Calculate win rate, Sharpe ratio, max drawdown
    4. Only approve if metrics exceed thresholds
    """

    def __init__(
        self,
        alpaca_api: Optional[Any] = None,
        min_win_rate: float = 0.50,  # 50% minimum win rate
        min_sharpe: float = 0.5,  # Minimum Sharpe ratio
        max_drawdown: float = 0.20,  # Maximum 20% drawdown
        lookback_days: int = 30,  # Days of historical data
    ):
        self.alpaca_api = alpaca_api
        self.min_win_rate = min_win_rate
        self.min_sharpe = min_sharpe
        self.max_drawdown = max_drawdown
        self.lookback_days = lookback_days

        self.results_cache: dict[str, BacktestResult] = {}

        logger.info(
            f"SignalBacktester initialized: "
            f"min_win_rate={min_win_rate}, min_sharpe={min_sharpe}"
        )

    def backtest_signal(
        self,
        symbol: str,
        signal_direction: str,
        model: str,
        holding_period_days: int = 5,
    ) -> BacktestResult:
        """
        Backtest a trading signal against historical data.

        Args:
            symbol: Stock symbol
            signal_direction: BUY or SELL
            model: Model that generated the signal
            holding_period_days: How long to hold the position

        Returns:
            BacktestResult with validation status
        """
        import uuid

        signal_id = f"bt_{uuid.uuid4().hex[:8]}"

        # Fetch historical data
        historical_prices = self._fetch_historical_prices(symbol)

        if len(historical_prices) < self.lookback_days:
            return BacktestResult(
                signal_id=signal_id,
                symbol=symbol,
                signal_direction=signal_direction,
                model=model,
                timestamp=datetime.now(timezone.utc).isoformat(),
                lookback_days=len(historical_prices),
                win_rate=0.0,
                avg_return=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                total_trades=0,
                profitable_trades=0,
                is_valid=False,
                validation_message=f"Insufficient data: {len(historical_prices)} days",
                historical_returns=[],
            )

        # Simulate trades at each historical point
        returns = []
        for i in range(len(historical_prices) - holding_period_days):
            entry_price = historical_prices[i]
            exit_price = historical_prices[i + holding_period_days]

            if signal_direction.upper() == "BUY":
                trade_return = (exit_price - entry_price) / entry_price
            else:  # SELL (short)
                trade_return = (entry_price - exit_price) / entry_price

            returns.append(trade_return)

        returns = np.array(returns)

        # Calculate metrics
        win_rate = np.mean(returns > 0) if len(returns) > 0 else 0
        avg_return = np.mean(returns) if len(returns) > 0 else 0
        sharpe_ratio = self._calculate_sharpe(returns)
        max_drawdown = self._calculate_max_drawdown(returns)
        total_trades = len(returns)
        profitable_trades = int(np.sum(returns > 0))

        # Validate
        is_valid, validation_message = self._validate_metrics(
            win_rate, sharpe_ratio, max_drawdown, avg_return
        )

        result = BacktestResult(
            signal_id=signal_id,
            symbol=symbol,
            signal_direction=signal_direction,
            model=model,
            timestamp=datetime.now(timezone.utc).isoformat(),
            lookback_days=self.lookback_days,
            win_rate=float(win_rate),
            avg_return=float(avg_return),
            max_drawdown=float(max_drawdown),
            sharpe_ratio=float(sharpe_ratio),
            total_trades=total_trades,
            profitable_trades=profitable_trades,
            is_valid=is_valid,
            validation_message=validation_message,
            historical_returns=returns.tolist()[:20],  # Keep last 20
        )

        # Cache result
        cache_key = f"{symbol}_{signal_direction}_{model}"
        self.results_cache[cache_key] = result

        self._save_results()

        if is_valid:
            logger.info(
                f"Backtest PASSED for {signal_direction} {symbol}: "
                f"win_rate={win_rate:.1%}, sharpe={sharpe_ratio:.2f}"
            )
        else:
            logger.warning(
                f"Backtest FAILED for {signal_direction} {symbol}: {validation_message}"
            )

        return result

    def _fetch_historical_prices(self, symbol: str) -> list[float]:
        """Fetch historical closing prices."""
        if not self.alpaca_api:
            # Return simulated data for testing
            logger.warning("No Alpaca API - using simulated price data")
            np.random.seed(42)  # Reproducible
            base_price = 100.0
            returns = np.random.normal(0.0005, 0.02, self.lookback_days)
            prices = [base_price]
            for r in returns:
                prices.append(prices[-1] * (1 + r))
            return prices

        try:
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=self.lookback_days + 10)

            bars = self.alpaca_api.get_bars(
                symbol,
                "1Day",
                start=start.isoformat(),
                end=end.isoformat(),
            )

            return [float(bar.c) for bar in bars]
        except Exception as e:
            logger.error(f"Failed to fetch historical prices for {symbol}: {e}")
            return []

    def _calculate_sharpe(self, returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio."""
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0

        excess_returns = returns - risk_free_rate / 252  # Daily risk-free rate
        return float(np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252))

    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown."""
        if len(returns) == 0:
            return 0.0

        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (running_max - cumulative) / running_max
        return float(np.max(drawdowns))

    def _validate_metrics(
        self,
        win_rate: float,
        sharpe_ratio: float,
        max_drawdown: float,
        avg_return: float,
    ) -> tuple[bool, str]:
        """Validate backtest metrics against thresholds."""
        issues = []

        if win_rate < self.min_win_rate:
            issues.append(f"Win rate {win_rate:.1%} < {self.min_win_rate:.1%}")

        if sharpe_ratio < self.min_sharpe:
            issues.append(f"Sharpe {sharpe_ratio:.2f} < {self.min_sharpe:.2f}")

        if max_drawdown > self.max_drawdown:
            issues.append(f"Max drawdown {max_drawdown:.1%} > {self.max_drawdown:.1%}")

        if avg_return < 0:
            issues.append(f"Negative avg return: {avg_return:.2%}")

        if issues:
            return False, "; ".join(issues)

        return True, "All metrics within thresholds"

    def get_cached_result(
        self,
        symbol: str,
        signal_direction: str,
        model: str,
    ) -> Optional[BacktestResult]:
        """Get cached backtest result if available."""
        cache_key = f"{symbol}_{signal_direction}_{model}"
        return self.results_cache.get(cache_key)

    def _save_results(self) -> None:
        """Save backtest results to disk."""
        BACKTEST_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "results": {
                k: {
                    "signal_id": v.signal_id,
                    "symbol": v.symbol,
                    "signal_direction": v.signal_direction,
                    "model": v.model,
                    "timestamp": v.timestamp,
                    "win_rate": v.win_rate,
                    "avg_return": v.avg_return,
                    "sharpe_ratio": v.sharpe_ratio,
                    "max_drawdown": v.max_drawdown,
                    "is_valid": v.is_valid,
                    "validation_message": v.validation_message,
                }
                for k, v in self.results_cache.items()
            },
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        try:
            with open(BACKTEST_RESULTS_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save backtest results: {e}")
