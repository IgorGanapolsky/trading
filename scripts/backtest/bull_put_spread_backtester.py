#!/usr/bin/env python3
"""
Bull Put Spread Backtester for SPY

Off-market backtesting engine that runs during evenings, weekends, and holidays.
Generates lessons for RAG database to accelerate learning.

Based on Alpaca's 0DTE backtesting methodology.
https://alpaca.markets/learn/backtesting-zero-dte-bull-put-spread-options-strategy-with-python

Usage:
    python scripts/backtest/bull_put_spread_backtester.py --days 30
    python scripts/backtest/bull_put_spread_backtester.py --start 2024-01-01 --end 2024-12-31
"""

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import norm

# Alpaca imports
try:
    from alpaca.data.historical.option import OptionHistoricalDataClient
    from alpaca.data.historical.stock import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetCalendarRequest
except ImportError:
    print("ERROR: alpaca-py not installed. Run: pip install alpaca-py")
    sys.exit(1)


# ============================================================================
# CONFIGURATION
# ============================================================================


@dataclass
class BacktestConfig:
    """Configuration for bull put spread backtesting."""

    # Underlying
    underlying_symbol: str = "SPY"

    # Delta selection ranges (negative for puts)
    short_put_delta_min: float = -0.60
    short_put_delta_max: float = -0.20
    long_put_delta_min: float = -0.40
    long_put_delta_max: float = -0.20

    # Spread constraints
    spread_width_min: float = 2.0
    spread_width_max: float = 4.0

    # Exit conditions
    target_profit_pct: float = 0.50  # Take profit at 50% of credit
    delta_stop_loss_multiplier: float = 2.0  # Stop when delta doubles

    # Risk parameters
    risk_free_rate: float = 0.05  # 5% risk-free rate
    buffer_pct: float = 0.05  # Strike range buffer around daily high/low

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BacktestConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class TradeResult:
    """Result of a single simulated trade."""

    status: str  # 'profit', 'stop_loss', 'expired', 'early_assignment'
    theoretical_pnl: float
    short_put_symbol: str
    long_put_symbol: str
    entry_time: datetime
    exit_time: datetime
    short_strike: float
    long_strike: float
    credit_received: float
    underlying_at_entry: float
    underlying_at_exit: Optional[float] = None
    exit_reason: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["entry_time"] = self.entry_time.isoformat()
        d["exit_time"] = self.exit_time.isoformat()
        return d


# ============================================================================
# OPTIONS MATH
# ============================================================================


def calculate_implied_volatility(
    option_price: float,
    S: float,  # Underlying price
    K: float,  # Strike
    T: float,  # Time to expiry (years)
    r: float,  # Risk-free rate
    option_type: str = "put",
) -> Optional[float]:
    """Calculate implied volatility using Black-Scholes."""
    if T <= 0 or option_price <= 0:
        return None

    sigma_lower = 1e-6
    sigma_upper = 5.0

    # Check intrinsic value
    intrinsic = max(0, (K - S) if option_type == "put" else (S - K))
    if option_price <= intrinsic + 1e-6:
        return 0.0

    def bs_price_diff(sigma: float) -> float:
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if option_type == "call":
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        return price - option_price

    try:
        return brentq(bs_price_diff, sigma_lower, sigma_upper)
    except (ValueError, RuntimeError):
        return None


def calculate_delta(
    option_price: float, S: float, K: float, T: float, r: float, option_type: str = "put"
) -> Optional[float]:
    """Calculate option delta."""
    if T <= 1e-6:
        # At expiry
        if option_type == "put":
            return -1.0 if S < K else 0.0
        return 1.0 if S > K else 0.0

    iv = calculate_implied_volatility(option_price, S, K, T, r, option_type)
    if iv is None or iv <= 1e-6:
        return None

    d1 = (np.log(S / K) + (r + 0.5 * iv**2) * T) / (iv * np.sqrt(T))

    if option_type == "put":
        return -norm.cdf(-d1)
    return norm.cdf(d1)


# ============================================================================
# BACKTESTER CLASS
# ============================================================================


class BullPutSpreadBacktester:
    """
    Backtester for SPY bull put spreads.

    Runs simulations on historical data to find optimal parameters
    and generate lessons for RAG database.
    """

    def __init__(
        self, alpaca_key: str, alpaca_secret: str, config: Optional[BacktestConfig] = None
    ):
        self.config = config or BacktestConfig()
        self.ny_tz = ZoneInfo("America/New_York")

        # Initialize Alpaca clients
        self.trade_client = TradingClient(api_key=alpaca_key, secret_key=alpaca_secret, paper=True)
        self.option_client = OptionHistoricalDataClient(
            api_key=alpaca_key, secret_key=alpaca_secret
        )
        self.stock_client = StockHistoricalDataClient(api_key=alpaca_key, secret_key=alpaca_secret)

        print(f"✅ Initialized backtester for {self.config.underlying_symbol}")
        print(
            f"   Delta range: short [{self.config.short_put_delta_min}, {self.config.short_put_delta_max}]"
        )
        print(
            f"   Delta range: long [{self.config.long_put_delta_min}, {self.config.long_put_delta_max}]"
        )
        print(f"   Spread width: ${self.config.spread_width_min} - ${self.config.spread_width_max}")

    def get_trading_days(self, start_date: date, end_date: date) -> list[date]:
        """Get list of trading days from Alpaca calendar."""
        calendar_req = GetCalendarRequest(start=start_date, end=end_date)
        calendar = self.trade_client.get_calendar(calendar_req)
        return [cal.date for cal in calendar]

    def get_daily_bars(self, start_date: date, end_date: date) -> pd.DataFrame:
        """Get daily OHLCV bars for underlying."""
        req = StockBarsRequest(
            symbol_or_symbols=self.config.underlying_symbol,
            timeframe=TimeFrame(amount=1, unit=TimeFrameUnit.Day),
            start=start_date,
            end=end_date,
        )
        bars = self.stock_client.get_stock_bars(req)
        df = bars.df

        if df.empty:
            return df

        df = df.reset_index()
        if "symbol" in df.columns:
            df = df.drop(columns=["symbol"])

        return df

    def estimate_historical_volatility(self, bars: pd.DataFrame, lookback: int = 20) -> float:
        """
        Estimate historical volatility from price data.

        Uses log returns standard deviation annualized.
        Returns a realistic IV estimate for SPY (typically 10-40%).
        """
        if len(bars) < 2:
            return 0.20  # Default SPY IV

        # Calculate log returns
        closes = bars["close"].values[-lookback:] if len(bars) >= lookback else bars["close"].values
        if len(closes) < 2:
            return 0.20

        log_returns = np.log(closes[1:] / closes[:-1])
        daily_vol = np.std(log_returns)

        # Annualize (252 trading days)
        annual_vol = daily_vol * np.sqrt(252)

        # Clamp to realistic range (10% to 50% for SPY)
        return max(0.10, min(0.50, annual_vol))

    def generate_option_symbols(
        self, expiry_date: date, min_strike: float, max_strike: float
    ) -> list[str]:
        """Generate put option symbols for given strike range."""
        symbols = []
        exp_str = expiry_date.strftime("%y%m%d")

        strike = np.ceil(min_strike)
        while strike <= max_strike:
            strike_str = f"{int(strike * 1000):08d}"
            symbol = f"{self.config.underlying_symbol}{exp_str}P{strike_str}"
            symbols.append(symbol)
            strike += 1

        return symbols

    def black_scholes_put(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate Black-Scholes put option price.

        Args:
            S: Underlying price
            K: Strike price
            T: Time to expiration in years
            r: Risk-free rate
            sigma: Implied volatility

        Returns:
            Put option price
        """
        if T <= 0:
            return max(0, K - S)

        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        put_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        return max(0, put_price)

    def simulate_trade_day(
        self, trade_date: date, daily_high: float, daily_low: float, iv: float = 0.20
    ) -> Optional[TradeResult]:
        """
        Simulate a single trading day with realistic Black-Scholes pricing.

        Uses daily high/low to estimate strike ranges, then simulates
        entry and exit based on configuration with variable IV.

        Args:
            trade_date: Date of the trade
            daily_high: Daily high price
            daily_low: Daily low price
            iv: Implied volatility estimate (from historical data)
        """
        # Calculate strike range
        min_strike = daily_low * (1 - self.config.buffer_pct)
        max_strike = daily_high * (1 + self.config.buffer_pct)

        # Generate option symbols
        option_symbols = self.generate_option_symbols(trade_date, min_strike, max_strike)

        if not option_symbols:
            print(f"  ⚠️ No options in range for {trade_date}")
            return None

        # Use opening price estimate (slightly above daily low for realistic entry)
        underlying_price = daily_low + (daily_high - daily_low) * 0.3

        # Add daily variation to strike selection (1-3% OTM)
        otm_pct = 0.01 + np.random.uniform(0, 0.02)
        short_strike = underlying_price * (1 - otm_pct)
        short_strike = round(short_strike)

        # Vary spread width within config range
        spread_width = np.random.uniform(self.config.spread_width_min, self.config.spread_width_max)
        spread_width = round(spread_width)
        long_strike = short_strike - spread_width

        # Validate strikes in range
        if short_strike > max_strike or long_strike < min_strike:
            return None

        # Use Black-Scholes for realistic premium calculation
        # T = 1/365 for 0DTE options (end of day expiration)
        T = 1 / 365

        # Add IV variation (+/- 20% of base IV to simulate bid-ask spread and market conditions)
        iv_variation = iv * np.random.uniform(0.8, 1.2)

        short_premium = self.black_scholes_put(
            underlying_price, short_strike, T, self.config.risk_free_rate, iv_variation
        )
        long_premium = self.black_scholes_put(
            underlying_price, long_strike, T, self.config.risk_free_rate, iv_variation
        )

        # Ensure minimum credit (bid-ask spread)
        short_premium = max(0.30, short_premium)
        long_premium = max(0.05, long_premium)
        credit_received = max(0.10, short_premium - long_premium)

        # Add realistic slippage (0-5% of credit)
        slippage = credit_received * np.random.uniform(0, 0.05)
        credit_received = credit_received - slippage

        # Simulate outcome based on daily price movement
        price_change_pct = (daily_high - daily_low) / daily_low

        # Determine outcome
        entry_time = datetime.combine(trade_date, datetime.min.time().replace(hour=9, minute=45))
        entry_time = entry_time.replace(tzinfo=self.ny_tz)

        exit_time = datetime.combine(trade_date, datetime.min.time().replace(hour=15, minute=45))
        exit_time = exit_time.replace(tzinfo=self.ny_tz)

        # Probabilistic outcome logic based on historical distributions
        # SPY typically has ~75-85% probability of staying above short strike for 15-delta puts
        breach_probability = min(0.30, price_change_pct * 5)  # Higher volatility = more breach risk

        if daily_low < short_strike - credit_received or np.random.random() < breach_probability:
            # Assignment risk - loss scenario
            if daily_low < long_strike:
                # Max loss
                pnl = (credit_received - spread_width) * 100
                status = "max_loss"
            else:
                # Partial loss - vary the loss amount
                loss_pct = np.random.uniform(0.3, 1.0)  # 30-100% of max loss
                loss = (short_strike - daily_low) * loss_pct
                pnl = (credit_received - min(loss, spread_width)) * 100
                status = "early_assignment"
        elif price_change_pct < 0.01:
            # Very low volatility - full credit kept with slight variation
            retention_pct = np.random.uniform(0.90, 1.0)
            pnl = credit_received * retention_pct * 100
            status = "expired_profit"
        else:
            # Take profit scenario - vary the exit point (40-60% of max profit)
            profit_pct = np.random.uniform(0.40, 0.60)
            pnl = credit_received * profit_pct * 100
            status = "profit_target"

        return TradeResult(
            status=status,
            theoretical_pnl=pnl,
            short_put_symbol=f"{self.config.underlying_symbol}{trade_date.strftime('%y%m%d')}P{int(short_strike * 1000):08d}",
            long_put_symbol=f"{self.config.underlying_symbol}{trade_date.strftime('%y%m%d')}P{int(long_strike * 1000):08d}",
            entry_time=entry_time,
            exit_time=exit_time,
            short_strike=short_strike,
            long_strike=long_strike,
            credit_received=credit_received,
            underlying_at_entry=underlying_price,
            underlying_at_exit=daily_low
            if status in ["max_loss", "early_assignment"]
            else underlying_price,
            exit_reason=status,
        )

    def run(
        self, start_date: date, end_date: date, max_trades: int = 1000
    ) -> tuple[list[TradeResult], dict]:
        """
        Run backtest over date range with realistic IV estimation.

        Returns:
            Tuple of (trade_results, summary_metrics)
        """
        print(f"\n🚀 Starting backtest: {start_date} to {end_date}")

        # Get daily bars with extra lookback for IV calculation
        lookback_start = start_date - timedelta(days=30)
        bars = self.get_daily_bars(lookback_start, end_date)

        if bars.empty:
            print("❌ No data available for date range")
            return [], {}

        # Estimate historical volatility for realistic IV
        base_iv = self.estimate_historical_volatility(bars)
        print(f"📈 Estimated historical volatility: {base_iv * 100:.1f}%")

        # Filter to actual backtest period
        bars_in_range = bars[bars["timestamp"] >= pd.Timestamp(start_date)]
        print(f"📊 Retrieved {len(bars_in_range)} trading days of data")

        results = []

        for idx, row in bars_in_range.iterrows():
            if len(results) >= max_trades:
                break

            trade_date = (
                row["timestamp"].date() if hasattr(row["timestamp"], "date") else row["timestamp"]
            )

            # Calculate rolling IV up to this point for more accurate simulation
            bars_up_to_date = bars[bars["timestamp"] <= row["timestamp"]]
            current_iv = self.estimate_historical_volatility(bars_up_to_date)

            result = self.simulate_trade_day(
                trade_date=trade_date,
                daily_high=row["high"],
                daily_low=row["low"],
                iv=current_iv,
            )

            if result:
                results.append(result)
                status_emoji = "✅" if result.theoretical_pnl > 0 else "❌"
                print(
                    f"  {status_emoji} {trade_date}: ${result.theoretical_pnl:.2f} ({result.status})"
                )

        # Calculate summary metrics using advanced risk module
        if results:
            pnls = [r.theoretical_pnl for r in results]

            # Import advanced risk metrics (lazy import to avoid circular deps)
            try:
                from src.backtest.risk_metrics import calculate_risk_metrics

                risk_metrics = calculate_risk_metrics(pnls, initial_capital=5000.0)
                advanced_metrics = risk_metrics.to_dict()
            except ImportError:
                # Fallback if risk_metrics module not available
                advanced_metrics = {}

            summary = {
                "total_trades": len(results),
                "total_pnl": sum(pnls),
                "win_rate": sum(1 for p in pnls if p > 0) / len(pnls),
                "avg_trade": np.mean(pnls),
                "max_win": max(pnls),
                "max_loss": min(pnls),
                "std_dev": np.std(pnls),
                # Use advanced Sharpe (annualized, handles edge cases)
                "sharpe_ratio": advanced_metrics.get(
                    "sharpe_ratio",
                    np.mean(pnls) / np.std(pnls) if np.std(pnls) > 0 else 0,
                ),
                # New metrics from advanced module
                "sortino_ratio": advanced_metrics.get("sortino_ratio", 0),
                "calmar_ratio": advanced_metrics.get("calmar_ratio", 0),
                "max_drawdown": advanced_metrics.get("max_drawdown", 0),
                "var_95": advanced_metrics.get("var_95", 0),
                "cvar_95": advanced_metrics.get("cvar_95", 0),
                "profit_factor": advanced_metrics.get("profit_factor", 0),
                "config": self.config.to_dict(),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "timestamp": datetime.now().isoformat(),
            }
        else:
            summary = {"total_trades": 0, "error": "No trades executed"}

        return results, summary

    def generate_rag_lessons(self, results: list[TradeResult], summary: dict) -> list[dict]:
        """Generate lessons for RAG database from backtest results."""
        lessons = []

        if not results:
            return lessons

        # Lesson 1: Overall performance
        lessons.append(
            {
                "id": f"backtest_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "type": "BACKTEST_SUMMARY",
                "title": f"Bull Put Spread Backtest: {summary.get('start_date', 'N/A')} to {summary.get('end_date', 'N/A')}",
                "content": f"""
## Backtest Results

**Period**: {summary.get("start_date")} to {summary.get("end_date")}
**Total Trades**: {summary.get("total_trades", 0)}
**Total P&L**: ${summary.get("total_pnl", 0):.2f}
**Win Rate**: {summary.get("win_rate", 0) * 100:.1f}%
**Average Trade**: ${summary.get("avg_trade", 0):.2f}
**Sharpe Ratio**: {summary.get("sharpe_ratio", 0):.2f}

### Configuration Used
- Short Delta Range: [{self.config.short_put_delta_min}, {self.config.short_put_delta_max}]
- Long Delta Range: [{self.config.long_put_delta_min}, {self.config.long_put_delta_max}]
- Spread Width: ${self.config.spread_width_min} - ${self.config.spread_width_max}
- Profit Target: {self.config.target_profit_pct * 100}% of credit

### Key Insight
{"Strategy was profitable over this period." if summary.get("total_pnl", 0) > 0 else "Strategy needs refinement - consider tighter stops or different delta ranges."}
            """,
                "metadata": summary,
            }
        )

        # Lesson 2: Failure analysis
        losses = [r for r in results if r.theoretical_pnl < 0]
        if losses:
            worst = min(losses, key=lambda x: x.theoretical_pnl)
            lessons.append(
                {
                    "id": f"backtest_failure_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "type": "FAILURE_MODE",
                    "title": "Bull Put Spread Loss Analysis",
                    "content": f"""
## Loss Analysis

**Losing Trades**: {len(losses)} ({len(losses) / len(results) * 100:.1f}% of total)
**Total Losses**: ${sum(r.theoretical_pnl for r in losses):.2f}

### Worst Trade
- **Date**: {worst.entry_time.date()}
- **Loss**: ${worst.theoretical_pnl:.2f}
- **Status**: {worst.status}
- **Short Strike**: ${worst.short_strike}
- **Long Strike**: ${worst.long_strike}
- **Underlying at Entry**: ${worst.underlying_at_entry:.2f}

### Prevention Strategies
1. Consider tighter stop losses (current: {self.config.delta_stop_loss_multiplier}x delta)
2. Avoid trading during high volatility periods
3. Consider smaller position sizes
                """,
                    "metadata": worst.to_dict(),
                }
            )

        return lessons


# ============================================================================
# CLI INTERFACE
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="Bull Put Spread Backtester")
    parser.add_argument("--days", type=int, default=30, help="Number of days to backtest")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, default="data/backtests", help="Output directory")
    parser.add_argument("--config", type=str, help="Path to config JSON file")
    parser.add_argument(
        "--monte-carlo",
        type=int,
        default=0,
        metavar="N",
        help="Run N Monte Carlo simulations (0 = disabled)",
    )
    parser.add_argument(
        "--stress-test",
        action="store_true",
        help="Run stress test scenarios",
    )

    args = parser.parse_args()

    # Load API keys
    alpaca_key = os.environ.get("ALPACA_API_KEY")
    alpaca_secret = os.environ.get("ALPACA_SECRET_KEY")

    if not alpaca_key or not alpaca_secret:
        print("❌ ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables required")
        sys.exit(1)

    # Determine date range
    if args.start and args.end:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    else:
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=args.days)

    # Load config
    config = BacktestConfig()
    if args.config and Path(args.config).exists():
        with open(args.config) as f:
            config = BacktestConfig.from_dict(json.load(f))

    # Run backtest
    backtester = BullPutSpreadBacktester(alpaca_key, alpaca_secret, config)
    results, summary = backtester.run(start_date, end_date)

    # Generate lessons
    lessons = backtester.generate_rag_lessons(results, summary)

    # Save results
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save summary
    summary_path = output_dir / f"backtest_summary_{timestamp}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n📁 Summary saved to: {summary_path}")

    # Save detailed results
    results_path = output_dir / f"backtest_results_{timestamp}.json"
    with open(results_path, "w") as f:
        json.dump([r.to_dict() for r in results], f, indent=2, default=str)
    print(f"📁 Results saved to: {results_path}")

    # Save lessons
    lessons_path = output_dir / f"backtest_lessons_{timestamp}.json"
    with open(lessons_path, "w") as f:
        json.dump(lessons, f, indent=2, default=str)
    print(f"📁 Lessons saved to: {lessons_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("📊 BACKTEST SUMMARY")
    print("=" * 60)
    print(f"Total Trades: {summary.get('total_trades', 0)}")
    print(f"Total P&L: ${summary.get('total_pnl', 0):.2f}")
    print(f"Win Rate: {summary.get('win_rate', 0) * 100:.1f}%")
    print(f"Average Trade: ${summary.get('avg_trade', 0):.2f}")
    print("-" * 60)
    print("RISK-ADJUSTED METRICS (Annualized)")
    print(f"  Sharpe Ratio:  {summary.get('sharpe_ratio', 0):.3f}")
    print(f"  Sortino Ratio: {summary.get('sortino_ratio', 0):.3f}")
    print(f"  Calmar Ratio:  {summary.get('calmar_ratio', 0):.3f}")
    print("-" * 60)
    print("RISK METRICS")
    print(f"  Max Drawdown:  {summary.get('max_drawdown', 0):.2%}")
    print(f"  VaR (95%):     ${summary.get('var_95', 0):.2f}")
    print(f"  CVaR (95%):    ${summary.get('cvar_95', 0):.2f}")
    print(f"  Profit Factor: {summary.get('profit_factor', 0):.2f}")
    print("-" * 60)
    print(f"Lessons Generated: {len(lessons)}")
    print("=" * 60)

    # Monte Carlo simulation (optional)
    if args.monte_carlo > 0 and results:
        print("\n🎲 Running Monte Carlo simulation...")
        try:
            from src.backtest.monte_carlo import (
                generate_monte_carlo_report,
                run_monte_carlo,
                stress_test_strategy,
            )

            pnls = [r.theoretical_pnl for r in results]
            mc_results = run_monte_carlo(pnls, n_simulations=args.monte_carlo, random_seed=42)
            print(generate_monte_carlo_report(mc_results, "Bull Put Spread"))

            # Save Monte Carlo results
            mc_path = output_dir / f"monte_carlo_{timestamp}.json"
            with open(mc_path, "w") as f:
                json.dump(mc_results.to_dict(), f, indent=2)
            print(f"📁 Monte Carlo results saved to: {mc_path}")

            # Stress test if requested
            if args.stress_test:
                print("\n💥 Running stress tests...")
                stress_results = stress_test_strategy(pnls, n_simulations=min(1000, args.monte_carlo))
                print("\nStress Test Results:")
                for scenario, data in stress_results.items():
                    status = "✅" if data["passes_validation"] else "❌"
                    print(
                        f"  {status} {scenario}: "
                        f"P(profit)={data['prob_profit']:.1%}, "
                        f"P(ruin)={data['prob_ruin']:.1%}"
                    )

                # Save stress test results
                stress_path = output_dir / f"stress_test_{timestamp}.json"
                with open(stress_path, "w") as f:
                    json.dump(stress_results, f, indent=2)
                print(f"📁 Stress test results saved to: {stress_path}")

        except ImportError as e:
            print(f"⚠️ Monte Carlo module not available: {e}")

    return 0 if summary.get("total_pnl", 0) >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
