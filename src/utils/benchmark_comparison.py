"""
Benchmark Comparison Utility

Compares trading performance against passive strategies:
- Buy-and-hold SPY
- 60/40 Portfolio (SPY/BND)
"""

import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class BenchmarkComparator:
    """Compare trading performance against benchmarks."""

    def __init__(self):
        self.risk_free_rate = 0.04  # 4% annual

    def calculate_spy_performance(
        self, start_date: datetime, end_date: datetime, initial_capital: float
    ) -> dict[str, Any]:
        """
        Calculate buy-and-hold SPY performance.

        Args:
            start_date: Start date
            end_date: End date
            initial_capital: Starting capital

        Returns:
            Performance metrics
        """
        try:
            import yfinance as yf

            spy = yf.Ticker("SPY")
            hist = spy.history(start=start_date, end=end_date)

            if hist.empty:
                return {"error": "No SPY data available"}

            start_price = hist.iloc[0]["Close"]
            end_price = hist.iloc[-1]["Close"]

            shares = initial_capital / start_price
            final_value = shares * end_price
            total_return = final_value - initial_capital
            total_return_pct = (total_return / initial_capital) * 100

            # Calculate daily returns for Sharpe
            hist["Returns"] = hist["Close"].pct_change()
            daily_returns = hist["Returns"].dropna()

            sharpe = 0.0
            if len(daily_returns) > 1:
                mean_return = daily_returns.mean()
                std_return = daily_returns.std()
                if std_return > 0:
                    risk_free_daily = self.risk_free_rate / 252
                    sharpe = (mean_return - risk_free_daily) / std_return * np.sqrt(252)

            return {
                "strategy": "Buy-and-Hold SPY",
                "initial_capital": initial_capital,
                "final_value": final_value,
                "total_return": total_return,
                "total_return_pct": total_return_pct,
                "sharpe_ratio": sharpe,
                "max_drawdown": self._calculate_max_drawdown(hist["Close"]),
            }
        except Exception as e:
            logger.error(f"Failed to calculate SPY performance: {e}")
            return {"error": str(e)}

    def calculate_6040_performance(
        self, start_date: datetime, end_date: datetime, initial_capital: float
    ) -> dict[str, Any]:
        """
        Calculate 60/40 portfolio performance (60% SPY, 40% BND).

        Args:
            start_date: Start date
            end_date: End date
            initial_capital: Starting capital

        Returns:
            Performance metrics
        """
        try:
            import yfinance as yf

            spy = yf.Ticker("SPY")
            bnd = yf.Ticker("BND")

            spy_hist = spy.history(start=start_date, end=end_date)
            bnd_hist = bnd.history(start=start_date, end=end_date)

            if spy_hist.empty or bnd_hist.empty:
                return {"error": "No benchmark data available"}

            # Align dates
            common_dates = spy_hist.index.intersection(bnd_hist.index)
            if len(common_dates) < 2:
                return {"error": "Insufficient overlapping data"}

            spy_prices = spy_hist.loc[common_dates]["Close"]
            bnd_prices = bnd_hist.loc[common_dates]["Close"]

            # Calculate portfolio value
            spy_allocation = initial_capital * 0.6
            bnd_allocation = initial_capital * 0.4

            spy_shares = spy_allocation / spy_prices.iloc[0]
            bnd_shares = bnd_allocation / bnd_prices.iloc[0]

            portfolio_values = spy_shares * spy_prices + bnd_shares * bnd_prices

            final_value = portfolio_values.iloc[-1]
            total_return = final_value - initial_capital
            total_return_pct = (total_return / initial_capital) * 100

            # Calculate daily returns
            daily_returns = portfolio_values.pct_change().dropna()

            sharpe = 0.0
            if len(daily_returns) > 1:
                mean_return = daily_returns.mean()
                std_return = daily_returns.std()
                if std_return > 0:
                    risk_free_daily = self.risk_free_rate / 252
                    sharpe = (mean_return - risk_free_daily) / std_return * np.sqrt(252)

            return {
                "strategy": "60/40 Portfolio (SPY/BND)",
                "initial_capital": initial_capital,
                "final_value": final_value,
                "total_return": total_return,
                "total_return_pct": total_return_pct,
                "sharpe_ratio": sharpe,
                "max_drawdown": self._calculate_max_drawdown(portfolio_values),
            }
        except Exception as e:
            logger.error(f"Failed to calculate 60/40 performance: {e}")
            return {"error": str(e)}

    def _calculate_max_drawdown(self, prices: pd.Series) -> float:
        """Calculate maximum drawdown."""
        if len(prices) < 2:
            return 0.0

        peak = prices.expanding().max()
        drawdown = (prices - peak) / peak
        max_drawdown = abs(drawdown.min()) * 100

        return max_drawdown

    def compare_strategies(
        self,
        strategy_performance: dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
    ) -> dict[str, Any]:
        """
        Compare strategy performance against benchmarks.

        Args:
            strategy_performance: Strategy performance metrics
            start_date: Start date
            end_date: End date
            initial_capital: Starting capital

        Returns:
            Comparison results
        """
        spy_perf = self.calculate_spy_performance(start_date, end_date, initial_capital)
        perf_6040 = self.calculate_6040_performance(start_date, end_date, initial_capital)

        comparison = {
            "strategy": strategy_performance,
            "spy": spy_perf,
            "6040": perf_6040,
            "vs_spy": {},
            "vs_6040": {},
        }

        # Compare vs SPY
        if "error" not in spy_perf:
            comparison["vs_spy"] = {
                "return_diff": (
                    strategy_performance.get("total_return_pct", 0)
                    - spy_perf.get("total_return_pct", 0)
                ),
                "sharpe_diff": (
                    strategy_performance.get("sharpe_ratio", 0) - spy_perf.get("sharpe_ratio", 0)
                ),
                "beats_spy": (
                    strategy_performance.get("total_return_pct", 0)
                    > spy_perf.get("total_return_pct", 0)
                ),
            }

        # Compare vs 60/40
        if "error" not in perf_6040:
            comparison["vs_6040"] = {
                "return_diff": (
                    strategy_performance.get("total_return_pct", 0)
                    - perf_6040.get("total_return_pct", 0)
                ),
                "sharpe_diff": (
                    strategy_performance.get("sharpe_ratio", 0) - perf_6040.get("sharpe_ratio", 0)
                ),
                "beats_6040": (
                    strategy_performance.get("total_return_pct", 0)
                    > perf_6040.get("total_return_pct", 0)
                ),
            }

        return comparison
