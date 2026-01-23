#!/usr/bin/env python3
"""
Iron Condor Backtester for SPY/SPX

Off-market backtesting engine for iron condors that runs during evenings,
weekends, and holidays. Generates lessons for RAG database.

Iron Condor = Bull Put Spread + Bear Call Spread
- Sell OTM put (15-20 delta)
- Buy further OTM put (protection)
- Sell OTM call (15-20 delta)
- Buy further OTM call (protection)

Profit when underlying stays within range (high probability with 15-delta wings).

Usage:
    python scripts/backtest/iron_condor_backtester.py --days 30
    python scripts/backtest/iron_condor_backtester.py --start 2025-01-01 --end 2025-12-31
    python scripts/backtest/iron_condor_backtester.py --ticker XSP  # For tax-optimized SPX mini
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
from scipy.stats import norm

# Alpaca imports
try:
    from alpaca.data.historical.stock import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.trading.client import TradingClient
except ImportError:
    print("ERROR: alpaca-py not installed. Run: pip install alpaca-py")
    sys.exit(1)


# ============================================================================
# CONFIGURATION
# ============================================================================


@dataclass
class IronCondorConfig:
    """Configuration for iron condor backtesting."""

    # Underlying (SPY for liquidity, XSP/SPX for tax optimization)
    underlying_symbol: str = "SPY"

    # Delta selection (absolute value, negative for puts)
    short_delta: float = 0.16  # 15-20 delta = 80-85% POP
    wing_width: float = 5.0  # $5 wide spreads

    # DTE selection
    dte_min: int = 30
    dte_max: int = 45

    # Exit conditions (per LL-268 research)
    profit_target_pct: float = 0.50  # Take profit at 50% of credit
    stop_loss_pct: float = 2.00  # Exit at 200% of credit (1:2 risk/reward)
    max_dte: int = 7  # Close at 7 DTE regardless (gamma risk)

    # Risk parameters
    risk_free_rate: float = 0.05
    max_position_pct: float = 0.05  # Max 5% of account per trade

    # Account size for position sizing
    account_size: float = 30000.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "IronCondorConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class IronCondorResult:
    """Result of a single iron condor trade."""

    status: str  # 'profit_target', 'stop_loss', 'expired', 'time_exit'
    pnl: float  # In dollars
    entry_date: date
    exit_date: date
    dte_at_entry: int
    dte_at_exit: int
    short_put_strike: float
    long_put_strike: float
    short_call_strike: float
    long_call_strike: float
    credit_received: float
    underlying_at_entry: float
    underlying_at_exit: float
    put_side_pnl: float
    call_side_pnl: float
    exit_reason: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["entry_date"] = self.entry_date.isoformat()
        d["exit_date"] = self.exit_date.isoformat()
        return d


# ============================================================================
# OPTIONS MATH
# ============================================================================


def black_scholes_price(
    S: float, K: float, T: float, r: float, sigma: float, option_type: str = "put"
) -> float:
    """Calculate Black-Scholes option price."""
    if T <= 0:
        if option_type == "put":
            return max(0, K - S)
        return max(0, S - K)

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    if option_type == "call":
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def strike_from_delta(
    S: float, T: float, r: float, sigma: float, delta: float, option_type: str = "put"
) -> float:
    """Find strike price that gives target delta."""
    if option_type == "put":
        # For put: delta = -N(-d1), so N(-d1) = -delta
        # d1 = norm.ppf(-delta)
        target_d1 = -norm.ppf(-delta)
    else:
        # For call: delta = N(d1)
        target_d1 = norm.ppf(delta)

    # K = S * exp(-(d1 * sigma * sqrt(T) - (r + 0.5 * sigma^2) * T))
    K = S * np.exp(-(target_d1 * sigma * np.sqrt(T) - (r + 0.5 * sigma**2) * T))
    return round(K)


# ============================================================================
# BACKTESTER CLASS
# ============================================================================


class IronCondorBacktester:
    """
    Backtester for SPY/SPX iron condors.

    Based on research from LL-268 and LL-293:
    - 15-20 delta short strikes = 80-85% probability of profit
    - $5 wide wings for defined risk
    - Exit at 50% profit or 7 DTE
    - Stop at 200% of credit
    """

    def __init__(
        self, alpaca_key: str, alpaca_secret: str, config: Optional[IronCondorConfig] = None
    ):
        self.config = config or IronCondorConfig()
        self.ny_tz = ZoneInfo("America/New_York")

        # Initialize Alpaca clients
        self.trade_client = TradingClient(
            api_key=alpaca_key, secret_key=alpaca_secret, paper=True
        )
        self.stock_client = StockHistoricalDataClient(
            api_key=alpaca_key, secret_key=alpaca_secret
        )

        print(f"✅ Iron Condor Backtester initialized for {self.config.underlying_symbol}")
        print(f"   Short delta: {self.config.short_delta} (POP: ~{(1-self.config.short_delta)*100:.0f}%)")
        print(f"   Wing width: ${self.config.wing_width}")
        print(f"   DTE range: {self.config.dte_min}-{self.config.dte_max} days")

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

    def estimate_iv(self, bars: pd.DataFrame, lookback: int = 20) -> float:
        """Estimate implied volatility from historical data."""
        if len(bars) < 2:
            return 0.18  # Default SPY IV

        closes = bars["close"].values[-lookback:] if len(bars) >= lookback else bars["close"].values
        if len(closes) < 2:
            return 0.18

        log_returns = np.log(closes[1:] / closes[:-1])
        daily_vol = np.std(log_returns)
        annual_vol = daily_vol * np.sqrt(252)

        # Clamp to realistic SPY range
        return max(0.10, min(0.40, annual_vol))

    def simulate_iron_condor(
        self,
        entry_date: date,
        bars_slice: pd.DataFrame,
        iv: float,
    ) -> Optional[IronCondorResult]:
        """
        Simulate a single iron condor trade.

        Entry: Sell 15-20 delta strangle, buy $5 OTM protection
        Exit: 50% profit, 200% loss, or 7 DTE
        """
        # Get entry price (use open of entry day)
        entry_bar = bars_slice[bars_slice["timestamp"].dt.date == entry_date]
        if entry_bar.empty:
            return None

        S = entry_bar.iloc[0]["open"]
        T = self.config.dte_min / 365  # Time to expiry in years

        # Calculate strikes based on delta
        short_put_strike = strike_from_delta(
            S, T, self.config.risk_free_rate, iv, -self.config.short_delta, "put"
        )
        long_put_strike = short_put_strike - self.config.wing_width

        short_call_strike = strike_from_delta(
            S, T, self.config.risk_free_rate, iv, self.config.short_delta, "call"
        )
        long_call_strike = short_call_strike + self.config.wing_width

        # Calculate premiums
        short_put_premium = black_scholes_price(
            S, short_put_strike, T, self.config.risk_free_rate, iv, "put"
        )
        long_put_premium = black_scholes_price(
            S, long_put_strike, T, self.config.risk_free_rate, iv, "put"
        )
        short_call_premium = black_scholes_price(
            S, short_call_strike, T, self.config.risk_free_rate, iv, "call"
        )
        long_call_premium = black_scholes_price(
            S, long_call_strike, T, self.config.risk_free_rate, iv, "call"
        )

        # Net credit received (per share, multiply by 100 for contract)
        put_spread_credit = max(0.10, short_put_premium - long_put_premium)
        call_spread_credit = max(0.10, short_call_premium - long_call_premium)
        total_credit = put_spread_credit + call_spread_credit

        # Apply realistic bid-ask spread (5-10% slippage)
        slippage = total_credit * np.random.uniform(0.05, 0.10)
        total_credit = total_credit - slippage

        # Simulate holding period
        profit_target = total_credit * self.config.profit_target_pct
        stop_loss = total_credit * self.config.stop_loss_pct

        # Track P/L through holding period
        exit_date = None
        exit_price = S
        exit_reason = "expired"
        put_side_pnl = 0
        call_side_pnl = 0

        future_bars = bars_slice[bars_slice["timestamp"].dt.date > entry_date]

        for _, bar in future_bars.iterrows():
            current_date = bar["timestamp"].date() if hasattr(bar["timestamp"], "date") else bar["timestamp"]
            days_held = (current_date - entry_date).days
            dte_remaining = self.config.dte_min - days_held

            if dte_remaining <= 0:
                break

            current_price = bar["close"]

            # Estimate current position value
            T_remaining = dte_remaining / 365
            current_iv = iv * (1 + np.random.uniform(-0.1, 0.1))  # IV variation

            current_short_put = black_scholes_price(
                current_price, short_put_strike, T_remaining, self.config.risk_free_rate, current_iv, "put"
            )
            current_long_put = black_scholes_price(
                current_price, long_put_strike, T_remaining, self.config.risk_free_rate, current_iv, "put"
            )
            current_short_call = black_scholes_price(
                current_price, short_call_strike, T_remaining, self.config.risk_free_rate, current_iv, "call"
            )
            current_long_call = black_scholes_price(
                current_price, long_call_strike, T_remaining, self.config.risk_free_rate, current_iv, "call"
            )

            put_side_value = current_short_put - current_long_put
            call_side_value = current_short_call - current_long_call
            current_position_value = put_side_value + call_side_value

            # P/L = credit received - current value to close
            unrealized_pnl = total_credit - current_position_value

            put_side_pnl = put_spread_credit - put_side_value
            call_side_pnl = call_spread_credit - call_side_value

            # Check exit conditions
            if unrealized_pnl >= profit_target:
                exit_date = current_date
                exit_price = current_price
                exit_reason = "profit_target"
                break
            elif unrealized_pnl <= -stop_loss:
                exit_date = current_date
                exit_price = current_price
                exit_reason = "stop_loss"
                break
            elif dte_remaining <= self.config.max_dte:
                exit_date = current_date
                exit_price = current_price
                exit_reason = "time_exit"
                break

        if exit_date is None:
            # Expired - determine final P/L based on where price ended
            last_bar = future_bars.iloc[-1] if not future_bars.empty else entry_bar.iloc[0]
            exit_date = last_bar["timestamp"].date() if hasattr(last_bar["timestamp"], "date") else entry_date
            exit_price = last_bar["close"]

            # At expiration
            if exit_price < short_put_strike:
                # Put side ITM - loss
                put_side_pnl = put_spread_credit - min(short_put_strike - exit_price, self.config.wing_width)
            else:
                put_side_pnl = put_spread_credit

            if exit_price > short_call_strike:
                # Call side ITM - loss
                call_side_pnl = call_spread_credit - min(exit_price - short_call_strike, self.config.wing_width)
            else:
                call_side_pnl = call_spread_credit

            exit_reason = "expired"

        # Calculate final P/L (per contract = 100 shares)
        final_pnl = (put_side_pnl + call_side_pnl) * 100

        return IronCondorResult(
            status=exit_reason,
            pnl=final_pnl,
            entry_date=entry_date,
            exit_date=exit_date,
            dte_at_entry=self.config.dte_min,
            dte_at_exit=max(0, self.config.dte_min - (exit_date - entry_date).days),
            short_put_strike=short_put_strike,
            long_put_strike=long_put_strike,
            short_call_strike=short_call_strike,
            long_call_strike=long_call_strike,
            credit_received=total_credit * 100,
            underlying_at_entry=S,
            underlying_at_exit=exit_price,
            put_side_pnl=put_side_pnl * 100,
            call_side_pnl=call_side_pnl * 100,
            exit_reason=exit_reason,
        )

    def run(self, start_date: date, end_date: date) -> tuple[list[IronCondorResult], dict]:
        """Run backtest over date range."""
        print(f"\n🚀 Starting Iron Condor backtest: {start_date} to {end_date}")

        # Get data with lookback for IV estimation
        lookback_start = start_date - timedelta(days=60)
        bars = self.get_daily_bars(lookback_start, end_date)

        if bars.empty:
            print("❌ No data available")
            return [], {}

        base_iv = self.estimate_iv(bars)
        print(f"📈 Base IV estimate: {base_iv * 100:.1f}%")

        results = []
        current_date = start_date

        while current_date <= end_date - timedelta(days=self.config.dte_min):
            # Only enter on trading days (Mon-Fri)
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            # Get bars up to current date for IV estimation
            bars_to_date = bars[bars["timestamp"].dt.date <= current_date]
            current_iv = self.estimate_iv(bars_to_date)

            # Get future bars for simulation
            future_end = current_date + timedelta(days=self.config.dte_min + 5)
            bars_slice = bars[
                (bars["timestamp"].dt.date >= current_date) &
                (bars["timestamp"].dt.date <= future_end)
            ]

            if bars_slice.empty:
                current_date += timedelta(days=7)  # Skip to next week
                continue

            result = self.simulate_iron_condor(current_date, bars_slice, current_iv)

            if result:
                results.append(result)
                emoji = "✅" if result.pnl > 0 else "❌"
                print(
                    f"  {emoji} {result.entry_date}: ${result.pnl:.2f} "
                    f"({result.exit_reason}, {result.dte_at_exit} DTE remaining)"
                )

            # Skip to next entry opportunity (weekly trades)
            current_date += timedelta(days=7)

        # Calculate summary
        summary = self._calculate_summary(results, start_date, end_date)
        return results, summary

    def _calculate_summary(
        self, results: list[IronCondorResult], start_date: date, end_date: date
    ) -> dict:
        """Calculate summary metrics."""
        if not results:
            return {"total_trades": 0, "error": "No trades executed"}

        pnls = [r.pnl for r in results]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        return {
            "total_trades": len(results),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(results) if results else 0,
            "total_pnl": sum(pnls),
            "avg_pnl": np.mean(pnls),
            "avg_win": np.mean(wins) if wins else 0,
            "avg_loss": np.mean(losses) if losses else 0,
            "max_win": max(pnls),
            "max_loss": min(pnls),
            "profit_factor": abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float("inf"),
            "sharpe_ratio": np.mean(pnls) / np.std(pnls) if np.std(pnls) > 0 else 0,
            "exit_reasons": {
                "profit_target": len([r for r in results if r.exit_reason == "profit_target"]),
                "stop_loss": len([r for r in results if r.exit_reason == "stop_loss"]),
                "time_exit": len([r for r in results if r.exit_reason == "time_exit"]),
                "expired": len([r for r in results if r.exit_reason == "expired"]),
            },
            "config": self.config.to_dict(),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timestamp": datetime.now().isoformat(),
        }

    def generate_rag_lessons(
        self, results: list[IronCondorResult], summary: dict
    ) -> list[dict]:
        """Generate lessons for RAG database."""
        lessons = []

        if not results:
            return lessons

        # Lesson 1: Summary
        lessons.append({
            "id": f"iron_condor_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "type": "BACKTEST_SUMMARY",
            "title": f"Iron Condor Backtest: {summary.get('start_date')} to {summary.get('end_date')}",
            "content": f"""
## Iron Condor Backtest Results

**Period**: {summary.get("start_date")} to {summary.get("end_date")}
**Underlying**: {self.config.underlying_symbol}

### Performance
- **Total Trades**: {summary.get("total_trades")}
- **Win Rate**: {summary.get("win_rate", 0) * 100:.1f}%
- **Total P&L**: ${summary.get("total_pnl", 0):.2f}
- **Average Trade**: ${summary.get("avg_pnl", 0):.2f}
- **Profit Factor**: {summary.get("profit_factor", 0):.2f}
- **Sharpe Ratio**: {summary.get("sharpe_ratio", 0):.2f}

### Exit Analysis
- Profit Target (50%): {summary.get("exit_reasons", {}).get("profit_target", 0)} trades
- Stop Loss (200%): {summary.get("exit_reasons", {}).get("stop_loss", 0)} trades
- Time Exit (7 DTE): {summary.get("exit_reasons", {}).get("time_exit", 0)} trades
- Expired: {summary.get("exit_reasons", {}).get("expired", 0)} trades

### Configuration
- Short Delta: {self.config.short_delta}
- Wing Width: ${self.config.wing_width}
- DTE: {self.config.dte_min}-{self.config.dte_max}
- Profit Target: {self.config.profit_target_pct * 100}%
- Stop Loss: {self.config.stop_loss_pct * 100}%

### Key Insight
{"This configuration achieved target 80%+ win rate!" if summary.get("win_rate", 0) >= 0.80 else f"Win rate {summary.get('win_rate', 0) * 100:.1f}% below 80% target. Consider tighter deltas or wider wings."}
            """,
            "metadata": summary,
        })

        return lessons


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="Iron Condor Backtester")
    parser.add_argument("--days", type=int, default=90, help="Days to backtest")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--ticker", type=str, default="SPY", help="Underlying (SPY, XSP, SPX)")
    parser.add_argument("--delta", type=float, default=0.16, help="Short strike delta")
    parser.add_argument("--width", type=float, default=5.0, help="Wing width in dollars")
    parser.add_argument("--output", type=str, default="data/backtests", help="Output directory")

    args = parser.parse_args()

    # Load API keys
    alpaca_key = os.environ.get("ALPACA_API_KEY")
    alpaca_secret = os.environ.get("ALPACA_SECRET_KEY")

    if not alpaca_key or not alpaca_secret:
        print("❌ ALPACA_API_KEY and ALPACA_SECRET_KEY required")
        sys.exit(1)

    # Date range
    if args.start and args.end:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    else:
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=args.days)

    # Config
    config = IronCondorConfig(
        underlying_symbol=args.ticker,
        short_delta=args.delta,
        wing_width=args.width,
    )

    # Run
    backtester = IronCondorBacktester(alpaca_key, alpaca_secret, config)
    results, summary = backtester.run(start_date, end_date)

    # Generate lessons
    lessons = backtester.generate_rag_lessons(results, summary)

    # Save
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    summary_path = output_dir / f"iron_condor_summary_{timestamp}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    results_path = output_dir / f"iron_condor_results_{timestamp}.json"
    with open(results_path, "w") as f:
        json.dump([r.to_dict() for r in results], f, indent=2, default=str)

    lessons_path = output_dir / f"iron_condor_lessons_{timestamp}.json"
    with open(lessons_path, "w") as f:
        json.dump(lessons, f, indent=2, default=str)

    # Print summary
    print("\n" + "=" * 60)
    print("📊 IRON CONDOR BACKTEST SUMMARY")
    print("=" * 60)
    print(f"Trades: {summary.get('total_trades', 0)}")
    print(f"Win Rate: {summary.get('win_rate', 0) * 100:.1f}%")
    print(f"Total P&L: ${summary.get('total_pnl', 0):.2f}")
    print(f"Avg Trade: ${summary.get('avg_pnl', 0):.2f}")
    print(f"Profit Factor: {summary.get('profit_factor', 0):.2f}")
    print(f"Sharpe: {summary.get('sharpe_ratio', 0):.2f}")
    print("=" * 60)
    print(f"📁 Results: {results_path}")

    return 0 if summary.get("win_rate", 0) >= 0.70 else 1


if __name__ == "__main__":
    sys.exit(main())
