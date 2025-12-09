"""
Benchmark Comparison Module

Provides comprehensive benchmark comparison capabilities for backtest results,
including buy-and-hold comparison, alpha/beta calculation, and relative performance metrics.

Features:
    - Automatic benchmark data fetching (SPY, QQQ, or custom)
    - Buy-and-hold strategy comparison
    - Alpha/Beta calculation using regression
    - Information Ratio and Tracking Error
    - Relative drawdown analysis
    - Market outperformance statistics

Author: Trading System
Created: 2025-12-09
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkMetrics:
    """Metrics for a single benchmark comparison."""

    # Benchmark identification
    symbol: str
    name: str

    # Returns comparison
    strategy_return: float  # Total strategy return %
    benchmark_return: float  # Total benchmark return %
    excess_return: float  # Strategy - Benchmark
    outperformance_ratio: float  # Strategy / Benchmark

    # Risk-adjusted metrics
    alpha: float  # Jensen's Alpha (annualized)
    beta: float  # Market sensitivity
    r_squared: float  # Correlation with benchmark
    information_ratio: float  # Risk-adjusted excess return
    tracking_error: float  # Standard deviation of excess returns

    # Drawdown comparison
    strategy_max_drawdown: float
    benchmark_max_drawdown: float
    relative_drawdown: float  # Strategy DD vs Benchmark DD

    # Outperformance statistics
    pct_days_outperformed: float  # % of days strategy beat benchmark
    best_outperformance_day: float  # Largest single-day outperformance
    worst_underperformance_day: float  # Worst single-day underperformance
    max_consecutive_outperformance: int  # Longest streak of outperforming

    # Sharpe comparison
    strategy_sharpe: float
    benchmark_sharpe: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "strategy_return": self.strategy_return,
            "benchmark_return": self.benchmark_return,
            "excess_return": self.excess_return,
            "outperformance_ratio": self.outperformance_ratio,
            "alpha": self.alpha,
            "beta": self.beta,
            "r_squared": self.r_squared,
            "information_ratio": self.information_ratio,
            "tracking_error": self.tracking_error,
            "strategy_max_drawdown": self.strategy_max_drawdown,
            "benchmark_max_drawdown": self.benchmark_max_drawdown,
            "relative_drawdown": self.relative_drawdown,
            "pct_days_outperformed": self.pct_days_outperformed,
            "best_outperformance_day": self.best_outperformance_day,
            "worst_underperformance_day": self.worst_underperformance_day,
            "max_consecutive_outperformance": self.max_consecutive_outperformance,
            "strategy_sharpe": self.strategy_sharpe,
            "benchmark_sharpe": self.benchmark_sharpe,
        }


@dataclass
class BenchmarkComparisonResult:
    """Complete benchmark comparison results for a backtest."""

    # Metadata
    strategy_name: str
    start_date: str
    end_date: str
    trading_days: int

    # Primary benchmark (usually SPY)
    primary_benchmark: BenchmarkMetrics

    # Additional benchmarks for comparison
    additional_benchmarks: list[BenchmarkMetrics] = field(default_factory=list)

    # Buy-and-hold comparison
    buy_hold_return: float = 0.0  # Return if just buying and holding primary
    buy_hold_sharpe: float = 0.0
    buy_hold_max_drawdown: float = 0.0

    # Time series data for charting
    strategy_equity_curve: list[float] = field(default_factory=list)
    benchmark_equity_curves: dict[str, list[float]] = field(default_factory=dict)
    excess_return_curve: list[float] = field(default_factory=list)

    def generate_report(self) -> str:
        """Generate human-readable benchmark comparison report."""
        lines = [
            "=" * 80,
            "BENCHMARK COMPARISON REPORT",
            "=" * 80,
            "",
            f"Strategy: {self.strategy_name}",
            f"Period: {self.start_date} to {self.end_date} ({self.trading_days} trading days)",
            "",
            "PRIMARY BENCHMARK: " + self.primary_benchmark.name,
            "-" * 80,
            f"  Strategy Return:     {self.primary_benchmark.strategy_return:+.2f}%",
            f"  Benchmark Return:    {self.primary_benchmark.benchmark_return:+.2f}%",
            f"  Excess Return:       {self.primary_benchmark.excess_return:+.2f}%",
            f"  Outperformance:      {self.primary_benchmark.outperformance_ratio:.2f}x",
            "",
            "RISK-ADJUSTED METRICS",
            "-" * 80,
            f"  Alpha (annualized):  {self.primary_benchmark.alpha:+.2f}%",
            f"  Beta:                {self.primary_benchmark.beta:.2f}",
            f"  R-Squared:           {self.primary_benchmark.r_squared:.2f}",
            f"  Information Ratio:   {self.primary_benchmark.information_ratio:.2f}",
            f"  Tracking Error:      {self.primary_benchmark.tracking_error:.2f}%",
            "",
            "DRAWDOWN COMPARISON",
            "-" * 80,
            f"  Strategy Max DD:     {self.primary_benchmark.strategy_max_drawdown:.2f}%",
            f"  Benchmark Max DD:    {self.primary_benchmark.benchmark_max_drawdown:.2f}%",
            f"  Relative DD:         {self.primary_benchmark.relative_drawdown:.2f}x",
            "",
            "OUTPERFORMANCE STATISTICS",
            "-" * 80,
            f"  Days Outperformed:   {self.primary_benchmark.pct_days_outperformed:.1f}%",
            f"  Best Day vs Bench:   {self.primary_benchmark.best_outperformance_day:+.2f}%",
            f"  Worst Day vs Bench:  {self.primary_benchmark.worst_underperformance_day:+.2f}%",
            f"  Max Win Streak:      {self.primary_benchmark.max_consecutive_outperformance} days",
            "",
            "SHARPE RATIO COMPARISON",
            "-" * 80,
            f"  Strategy Sharpe:     {self.primary_benchmark.strategy_sharpe:.2f}",
            f"  Benchmark Sharpe:    {self.primary_benchmark.benchmark_sharpe:.2f}",
            "",
            "BUY-AND-HOLD COMPARISON",
            "-" * 80,
            f"  Buy & Hold Return:   {self.buy_hold_return:+.2f}%",
            f"  Buy & Hold Sharpe:   {self.buy_hold_sharpe:.2f}",
            f"  Buy & Hold Max DD:   {self.buy_hold_max_drawdown:.2f}%",
            "",
        ]

        # Additional benchmarks
        if self.additional_benchmarks:
            lines.append("ADDITIONAL BENCHMARKS")
            lines.append("-" * 80)
            for bm in self.additional_benchmarks:
                lines.append(f"  {bm.name} ({bm.symbol}):")
                lines.append(f"    Return: {bm.benchmark_return:+.2f}%")
                lines.append(f"    Excess: {bm.excess_return:+.2f}%")
                lines.append(f"    Alpha:  {bm.alpha:+.2f}%")
                lines.append("")

        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 80)
        if self.primary_benchmark.excess_return > 0:
            lines.append(
                f"  Strategy OUTPERFORMED benchmark by {self.primary_benchmark.excess_return:.2f}%"
            )
        else:
            lines.append(
                f"  Strategy UNDERPERFORMED benchmark by {abs(self.primary_benchmark.excess_return):.2f}%"
            )

        if self.primary_benchmark.alpha > 0:
            lines.append(f"  Positive alpha of {self.primary_benchmark.alpha:.2f}% suggests skill")
        else:
            lines.append(f"  Negative alpha of {self.primary_benchmark.alpha:.2f}% suggests no edge")

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "trading_days": self.trading_days,
            "primary_benchmark": self.primary_benchmark.to_dict(),
            "additional_benchmarks": [b.to_dict() for b in self.additional_benchmarks],
            "buy_hold_return": self.buy_hold_return,
            "buy_hold_sharpe": self.buy_hold_sharpe,
            "buy_hold_max_drawdown": self.buy_hold_max_drawdown,
        }


class BenchmarkComparator:
    """
    Compare backtest results against market benchmarks.

    Provides comprehensive analysis of strategy performance relative to
    buy-and-hold and common market indices.
    """

    # Common benchmark symbols with descriptions
    BENCHMARKS = {
        "SPY": "S&P 500 ETF",
        "QQQ": "NASDAQ-100 ETF",
        "IWM": "Russell 2000 Small Cap ETF",
        "DIA": "Dow Jones Industrial ETF",
        "VTI": "Total US Stock Market ETF",
        "EFA": "International Developed Markets ETF",
        "BND": "US Aggregate Bond ETF",
    }

    def __init__(
        self,
        primary_benchmark: str = "SPY",
        risk_free_rate: float = 0.04,
        additional_benchmarks: list[str] | None = None,
    ):
        """
        Initialize benchmark comparator.

        Args:
            primary_benchmark: Primary benchmark symbol (default: SPY)
            risk_free_rate: Annual risk-free rate for Sharpe calculation (default: 4%)
            additional_benchmarks: Optional list of additional benchmarks to compare
        """
        self.primary_benchmark = primary_benchmark
        self.risk_free_rate = risk_free_rate
        self.additional_benchmarks = additional_benchmarks or []
        self._benchmark_cache: dict[str, pd.DataFrame] = {}

    def compare(
        self,
        equity_curve: list[float],
        dates: list[str],
        strategy_name: str = "Strategy",
    ) -> BenchmarkComparisonResult:
        """
        Compare strategy performance against benchmarks.

        Args:
            equity_curve: List of daily portfolio values
            dates: List of dates corresponding to equity curve (YYYY-MM-DD format)
            strategy_name: Name of the strategy for reporting

        Returns:
            BenchmarkComparisonResult with comprehensive comparison metrics
        """
        if len(equity_curve) < 2 or len(dates) < 2:
            raise ValueError("Need at least 2 data points for comparison")

        if len(equity_curve) != len(dates):
            raise ValueError("equity_curve and dates must have same length")

        # Parse dates
        start_date = dates[0]
        end_date = dates[-1]

        # Calculate strategy returns
        strategy_returns = self._calculate_returns(equity_curve)

        # Fetch and process primary benchmark
        primary_data = self._fetch_benchmark_data(self.primary_benchmark, start_date, end_date)
        if primary_data is None or primary_data.empty:
            raise ValueError(f"Failed to fetch benchmark data for {self.primary_benchmark}")

        # Align benchmark data with strategy dates
        primary_aligned = self._align_benchmark_to_dates(primary_data, dates)
        primary_returns = self._calculate_returns(primary_aligned)

        # Calculate primary benchmark metrics
        primary_metrics = self._calculate_benchmark_metrics(
            symbol=self.primary_benchmark,
            name=self.BENCHMARKS.get(self.primary_benchmark, self.primary_benchmark),
            strategy_returns=strategy_returns,
            benchmark_returns=primary_returns,
            strategy_equity=equity_curve,
            benchmark_equity=primary_aligned,
        )

        # Calculate buy-and-hold metrics
        buy_hold_return = (primary_aligned[-1] / primary_aligned[0] - 1) * 100
        buy_hold_sharpe = self._calculate_sharpe(primary_returns)
        buy_hold_max_dd = self._calculate_max_drawdown(primary_aligned)

        # Process additional benchmarks
        additional_metrics = []
        benchmark_curves = {self.primary_benchmark: primary_aligned}

        for symbol in self.additional_benchmarks:
            try:
                data = self._fetch_benchmark_data(symbol, start_date, end_date)
                if data is not None and not data.empty:
                    aligned = self._align_benchmark_to_dates(data, dates)
                    returns = self._calculate_returns(aligned)
                    metrics = self._calculate_benchmark_metrics(
                        symbol=symbol,
                        name=self.BENCHMARKS.get(symbol, symbol),
                        strategy_returns=strategy_returns,
                        benchmark_returns=returns,
                        strategy_equity=equity_curve,
                        benchmark_equity=aligned,
                    )
                    additional_metrics.append(metrics)
                    benchmark_curves[symbol] = aligned
            except Exception as e:
                logger.warning(f"Failed to process benchmark {symbol}: {e}")

        # Calculate excess return curve
        excess_curve = [
            (s / primary_aligned[0]) / (b / primary_aligned[0]) - 1
            for s, b in zip(equity_curve, primary_aligned)
        ]

        return BenchmarkComparisonResult(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            trading_days=len(dates),
            primary_benchmark=primary_metrics,
            additional_benchmarks=additional_metrics,
            buy_hold_return=buy_hold_return,
            buy_hold_sharpe=buy_hold_sharpe,
            buy_hold_max_drawdown=buy_hold_max_dd,
            strategy_equity_curve=equity_curve,
            benchmark_equity_curves=benchmark_curves,
            excess_return_curve=excess_curve,
        )

    def _fetch_benchmark_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame | None:
        """
        Fetch historical benchmark data.

        Uses yfinance with caching to minimize API calls.
        """
        cache_key = f"{symbol}_{start_date}_{end_date}"
        if cache_key in self._benchmark_cache:
            return self._benchmark_cache[cache_key]

        try:
            # Add buffer days for alignment
            start_dt = datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=5)
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=5)

            ticker = yf.Ticker(symbol)
            history = ticker.history(
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
                auto_adjust=True,
            )

            if history is None or history.empty:
                logger.warning(f"No data returned for {symbol}")
                return None

            self._benchmark_cache[cache_key] = history
            logger.info(f"Fetched {len(history)} bars for benchmark {symbol}")
            return history

        except Exception as e:
            logger.error(f"Failed to fetch benchmark {symbol}: {e}")
            return None

    def _align_benchmark_to_dates(
        self,
        benchmark_data: pd.DataFrame,
        dates: list[str],
    ) -> list[float]:
        """
        Align benchmark data to strategy dates.

        Uses forward-fill for missing dates.
        """
        aligned = []
        benchmark_data.index = pd.to_datetime(benchmark_data.index).date

        last_price = None
        for date_str in dates:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Find matching or previous date
            if target_date in benchmark_data.index:
                last_price = float(benchmark_data.loc[target_date, "Close"])
            else:
                # Forward-fill from last known price
                earlier_dates = [d for d in benchmark_data.index if d <= target_date]
                if earlier_dates:
                    last_price = float(benchmark_data.loc[max(earlier_dates), "Close"])
                elif last_price is None:
                    # Use first available price
                    last_price = float(benchmark_data["Close"].iloc[0])

            aligned.append(last_price)

        # Normalize to start at same value as strategy
        if aligned and aligned[0] != 0:
            return aligned

        return aligned

    def _calculate_returns(self, values: list[float]) -> np.ndarray:
        """Calculate daily returns from value series."""
        values_arr = np.array(values)
        returns = np.diff(values_arr) / values_arr[:-1]
        return returns

    def _calculate_sharpe(self, returns: np.ndarray) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(returns) == 0:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        daily_rf = self.risk_free_rate / 252
        sharpe = (mean_return - daily_rf) / std_return * np.sqrt(252)
        return float(sharpe)

    def _calculate_max_drawdown(self, values: list[float]) -> float:
        """Calculate maximum drawdown percentage."""
        values_arr = np.array(values)
        running_max = np.maximum.accumulate(values_arr)
        drawdowns = (values_arr - running_max) / running_max
        return float(abs(np.min(drawdowns)) * 100)

    def _calculate_benchmark_metrics(
        self,
        symbol: str,
        name: str,
        strategy_returns: np.ndarray,
        benchmark_returns: np.ndarray,
        strategy_equity: list[float],
        benchmark_equity: list[float],
    ) -> BenchmarkMetrics:
        """Calculate comprehensive benchmark comparison metrics."""
        # Ensure same length
        min_len = min(len(strategy_returns), len(benchmark_returns))
        strat_ret = strategy_returns[:min_len]
        bench_ret = benchmark_returns[:min_len]

        # Total returns
        strategy_total = (strategy_equity[-1] / strategy_equity[0] - 1) * 100
        benchmark_total = (benchmark_equity[-1] / benchmark_equity[0] - 1) * 100
        excess_return = strategy_total - benchmark_total
        outperformance_ratio = (
            (1 + strategy_total / 100) / (1 + benchmark_total / 100)
            if benchmark_total != -100
            else 0.0
        )

        # Alpha and Beta using linear regression
        if len(strat_ret) > 1 and np.std(bench_ret) > 0:
            # Beta = Cov(strategy, benchmark) / Var(benchmark)
            covariance = np.cov(strat_ret, bench_ret)[0, 1]
            variance = np.var(bench_ret)
            beta = covariance / variance if variance > 0 else 1.0

            # Alpha = mean(strategy) - beta * mean(benchmark) - risk_free
            daily_rf = self.risk_free_rate / 252
            alpha_daily = np.mean(strat_ret) - beta * np.mean(bench_ret) - daily_rf * (1 - beta)
            alpha = alpha_daily * 252 * 100  # Annualized %

            # R-squared
            correlation = np.corrcoef(strat_ret, bench_ret)[0, 1]
            r_squared = correlation**2 if not np.isnan(correlation) else 0.0
        else:
            beta = 1.0
            alpha = 0.0
            r_squared = 0.0

        # Information Ratio and Tracking Error
        excess_returns = strat_ret - bench_ret
        tracking_error = np.std(excess_returns) * np.sqrt(252) * 100
        if tracking_error > 0:
            information_ratio = (np.mean(excess_returns) * 252 * 100) / tracking_error
        else:
            information_ratio = 0.0

        # Drawdown comparison
        strategy_dd = self._calculate_max_drawdown(strategy_equity)
        benchmark_dd = self._calculate_max_drawdown(benchmark_equity)
        relative_dd = strategy_dd / benchmark_dd if benchmark_dd > 0 else 1.0

        # Outperformance statistics
        daily_outperformance = strat_ret - bench_ret
        pct_outperformed = (np.sum(daily_outperformance > 0) / len(daily_outperformance)) * 100
        best_day = float(np.max(daily_outperformance) * 100)
        worst_day = float(np.min(daily_outperformance) * 100)

        # Max consecutive outperformance
        max_streak = 0
        current_streak = 0
        for out in daily_outperformance > 0:
            if out:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0

        # Sharpe ratios
        strategy_sharpe = self._calculate_sharpe(strat_ret)
        benchmark_sharpe = self._calculate_sharpe(bench_ret)

        return BenchmarkMetrics(
            symbol=symbol,
            name=name,
            strategy_return=strategy_total,
            benchmark_return=benchmark_total,
            excess_return=excess_return,
            outperformance_ratio=outperformance_ratio,
            alpha=alpha,
            beta=beta,
            r_squared=r_squared,
            information_ratio=information_ratio,
            tracking_error=tracking_error,
            strategy_max_drawdown=strategy_dd,
            benchmark_max_drawdown=benchmark_dd,
            relative_drawdown=relative_dd,
            pct_days_outperformed=pct_outperformed,
            best_outperformance_day=best_day,
            worst_underperformance_day=worst_day,
            max_consecutive_outperformance=max_streak,
            strategy_sharpe=strategy_sharpe,
            benchmark_sharpe=benchmark_sharpe,
        )


def compare_to_benchmark(
    equity_curve: list[float],
    dates: list[str],
    benchmark: str = "SPY",
    strategy_name: str = "Strategy",
) -> BenchmarkComparisonResult:
    """
    Convenience function to compare backtest results to a benchmark.

    Args:
        equity_curve: List of daily portfolio values
        dates: List of dates (YYYY-MM-DD format)
        benchmark: Benchmark symbol (default: SPY)
        strategy_name: Name of strategy for reporting

    Returns:
        BenchmarkComparisonResult
    """
    comparator = BenchmarkComparator(primary_benchmark=benchmark)
    return comparator.compare(equity_curve, dates, strategy_name)


def compare_to_buy_and_hold(
    equity_curve: list[float],
    dates: list[str],
    symbols: list[str],
    initial_capital: float,
) -> dict[str, Any]:
    """
    Compare strategy to buy-and-hold of the traded symbols.

    Args:
        equity_curve: Strategy equity curve
        dates: List of dates
        symbols: List of symbols that were traded
        initial_capital: Starting capital

    Returns:
        Dictionary with buy-and-hold comparison metrics
    """
    if not symbols:
        return {"error": "No symbols provided"}

    comparator = BenchmarkComparator()
    results = {}

    for symbol in symbols:
        try:
            data = comparator._fetch_benchmark_data(symbol, dates[0], dates[-1])
            if data is not None and not data.empty:
                aligned = comparator._align_benchmark_to_dates(data, dates)

                # Calculate buy-and-hold assuming equal allocation
                allocation = initial_capital / len(symbols)
                shares = allocation / aligned[0]
                buy_hold_curve = [shares * price for price in aligned]

                bh_return = (buy_hold_curve[-1] / buy_hold_curve[0] - 1) * 100
                bh_returns = comparator._calculate_returns(buy_hold_curve)
                bh_sharpe = comparator._calculate_sharpe(bh_returns)
                bh_dd = comparator._calculate_max_drawdown(buy_hold_curve)

                results[symbol] = {
                    "return": bh_return,
                    "sharpe": bh_sharpe,
                    "max_drawdown": bh_dd,
                    "final_value": buy_hold_curve[-1],
                }
        except Exception as e:
            logger.warning(f"Failed to calculate buy-and-hold for {symbol}: {e}")
            results[symbol] = {"error": str(e)}

    # Combined buy-and-hold (equal weight)
    if results:
        combined_return = sum(r.get("return", 0) for r in results.values() if "return" in r)
        combined_return /= len([r for r in results.values() if "return" in r])
        results["combined"] = {"return": combined_return}

    # Compare to strategy
    strategy_return = (equity_curve[-1] / equity_curve[0] - 1) * 100
    results["strategy"] = {"return": strategy_return}
    results["excess_vs_buy_hold"] = strategy_return - results.get("combined", {}).get("return", 0)

    return results


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example equity curve
    initial = 100000
    equity_curve = [initial]
    dates = []

    from datetime import date, timedelta

    current = date(2024, 1, 1)
    for i in range(252):  # One year
        if current.weekday() < 5:  # Weekdays only
            # Random walk with slight upward bias
            change = np.random.normal(0.0005, 0.01)
            equity_curve.append(equity_curve[-1] * (1 + change))
            dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    # Compare to SPY
    result = compare_to_benchmark(equity_curve, dates, benchmark="SPY")
    print(result.generate_report())
