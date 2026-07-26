"""Bull put credit spread backtester for SPY.

Replaces the stub implementation with a working backtest that:
  - Loads SPY historical price data from data/historical/
  - Simulates bull put credit spreads using a simplified Black-Scholes model
  - Applies the put-credit profile rules (0.15 delta, $5 wing, 30-45 DTE,
    25% take profit, 200% stop loss, 7 DTE force exit, 24h min hold)
  - Calculates proper metrics (win rate, profit factor, expectancy, max drawdown)

Usage:
    python -m scripts.backtest.bull_put_spread_backtester --start 2025-10-01 --end 2025-11-29
    python -m scripts.backtest.bull_put_spread_backtester --start 2025-10-01 --end 2025-11-29 --verbose
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import norm

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_DIR = PROJECT_ROOT / "data" / "historical"

# Risk-free rate approximation (3-month T-bill yield, 2025-2026 average)
RISK_FREE_RATE = 0.045


def _norm_cdf(x: float) -> float:
    """Standard normal CDF."""
    return float(norm.cdf(x))


def _norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    return float(norm.pdf(x))


def black_scholes_put(
    spot: float, strike: float, dte_days: float, vol: float, rate: float = RISK_FREE_RATE
) -> float:
    """Calculate put option price using Black-Scholes.

    Args:
        spot: Current underlying price.
        strike: Put strike price.
        dte_days: Days to expiry.
        vol: Annualized volatility.
        rate: Risk-free rate (annualized).

    Returns:
        Put option price per share.
    """
    if dte_days <= 0 or vol <= 0:
        # At expiry, put is worth max(0, strike - spot)
        return max(0.0, strike - spot)
    dte_years = dte_days / 365.0
    sqrt_t = math.sqrt(dte_years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * dte_years) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    put_price = strike * math.exp(-rate * dte_years) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
    return max(0.0, put_price)


def calculate_put_delta(
    spot: float, strike: float, dte_days: float, vol: float, rate: float = RISK_FREE_RATE
) -> float:
    """Calculate put option delta (negative for puts)."""
    if dte_days <= 0 or vol <= 0:
        return -1.0 if spot < strike else 0.0
    dte_years = dte_days / 365.0
    sqrt_t = math.sqrt(dte_years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * dte_years) / (vol * sqrt_t)
    return float(-_norm_cdf(-d1))


def find_strike_for_delta(
    spot: float, target_delta: float, dte_days: float, vol: float, rate: float = RISK_FREE_RATE
) -> float:
    """Find the strike price that produces approximately the target put delta.

    Uses binary search on strike price. For puts:
      - strike < spot → OTM put → delta ≈ 0 (slightly negative)
      - strike > spot → ITM put → delta ≈ -1

    So to get delta = -0.15 (target), we need strike slightly below spot.
    Binary search range: [spot*0.5, spot*1.5].
    """
    if dte_days <= 0:
        return spot  # At expiry, any strike near spot works
    lo, hi = spot * 0.5, spot * 1.5
    for _ in range(50):
        mid = (lo + hi) / 2
        delta = calculate_put_delta(spot, mid, dte_days, vol, rate)
        # delta is negative; target_delta is positive (e.g., 0.15 means -0.15 delta)
        if abs(delta) < target_delta:
            # Put too OTM (delta ≈ 0) → increase strike toward ITM
            lo = mid
        else:
            # Put too ITM (delta too negative) → decrease strike toward OTM
            hi = mid
    return (lo + hi) / 2


def estimate_volatility(prices: list[float]) -> float:
    """Estimate annualized volatility from daily price series."""
    if len(prices) < 2:
        return 0.15  # Default 15% vol
    returns = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
    if not returns:
        return 0.15
    vol = float(np.std(returns)) * math.sqrt(252)
    return max(0.05, min(0.50, vol))  # Clamp to 5%-50%


def load_spy_prices(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Load SPY historical price data from CSV files.

    Handles two CSV formats:
      1. Simple: Date,Open,High,Low,Close,Volume
      2. Multi-index: 3 header rows, data starts at row 4

    Returns list of dicts with 'date', 'open', 'high', 'low', 'close', 'volume'.
    """
    prices: list[dict[str, Any]] = []
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()

    csv_files = sorted(HISTORICAL_DIR.glob("SPY_*.csv"))
    for csv_file in csv_files:
        with open(csv_file, newline="", encoding="utf-8-sig") as f:
            # Peek at first line to detect format
            first_line = f.readline().strip()
            f.seek(0)

            if first_line.startswith("Date,Open,High,Low,Close,Volume"):
                # Simple format
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        row_date = datetime.strptime(row["Date"], "%Y-%m-%d").date()
                    except (ValueError, KeyError):
                        continue
                    if start <= row_date <= end:
                        prices.append(
                            {
                                "date": row_date,
                                "open": float(row["Open"]),
                                "high": float(row["High"]),
                                "low": float(row["Low"]),
                                "close": float(row["Close"]),
                                "volume": float(row.get("Volume", 0)),
                            }
                        )
            else:
                # Multi-index format: skip 3 header rows
                lines = f.readlines()
                data_lines = lines[3:]  # Skip 3 header rows
                for line in data_lines:
                    parts = line.strip().split(",")
                    if len(parts) < 6:
                        continue
                    try:
                        row_date = datetime.strptime(parts[0], "%Y-%m-%d").date()
                    except ValueError:
                        continue
                    if start <= row_date <= end:
                        prices.append(
                            {
                                "date": row_date,
                                "open": float(parts[3]),
                                "high": float(parts[2]),
                                "low": float(parts[4]),
                                "close": float(parts[1]),
                                "volume": float(parts[5]) if parts[5] else 0.0,
                            }
                        )

    # Deduplicate by date, keeping last occurrence
    seen: dict[str, dict[str, Any]] = {}
    for p in prices:
        seen[p["date"].isoformat()] = p
    prices = sorted(seen.values(), key=lambda x: x["date"])
    return prices


@dataclass
class PutCreditTrade:
    """A single bull put credit spread trade."""

    entry_date: date
    exit_date: date | None
    short_strike: float
    long_strike: float
    short_put_price: float
    long_put_price: float
    credit: float
    max_profit: float
    max_loss: float
    exit_reason: str | None = None
    exit_price: float | None = None
    pnl: float = 0.0
    held_days: int = 0
    entry_delta: float = 0.0
    exit_delta: float = 0.0


@dataclass
class BacktestConfig:
    """Configuration for bull put spread backtest."""

    target_delta: float = 0.15
    delta_band_min: float = 0.10
    delta_band_max: float = 0.22
    wing_width: float = 5.0
    take_profit_pct: float = 0.25
    stop_loss_pct: float = 2.0
    exit_dte: int = 7
    min_hold_days: int = 1  # 24h minimum
    max_dte: int = 45
    min_dte: int = 30
    min_credit: float = 0.50
    commission_per_leg: float = 0.50  # $0.50 per leg per contract
    contracts: int = 1


@dataclass
class BacktestResults:
    """Results of a bull put spread backtest."""

    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    avg_credit: float = 0.0
    avg_hold_days: float = 0.0
    exit_reasons: dict[str, int] = field(default_factory=dict)
    trades: list[dict[str, Any]] = field(default_factory=list)


class BullPutSpreadBacktester:
    """Backtester for SPY bull put credit spreads."""

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()
        self.trades: list[PutCreditTrade] = []
        self.results: dict[str, Any] = {}
        self._price_lookup: dict[date, dict[str, Any]] = {}

    def calculate_spread_premium(
        self,
        underlying_price: float,
        strike_short: float,
        strike_long: float,
        dte: int,
        vol: float,
    ) -> float:
        """Calculate theoretical credit for a bull put spread.

        Credit = short_put_price - long_put_price (per share).
        """
        short_put = black_scholes_put(underlying_price, strike_short, dte, vol)
        long_put = black_scholes_put(underlying_price, strike_long, dte, vol)
        return max(0.0, short_put - long_put)

    def _find_entry_strike(
        self, spot: float, dte: int, vol: float
    ) -> tuple[float, float, float, float]:
        """Find short and long strikes for the target delta and wing width.

        Returns: (short_strike, long_strike, short_delta, short_put_price)
        """
        short_strike = find_strike_for_delta(spot, self.config.target_delta, dte, vol)
        long_strike = short_strike - self.config.wing_width
        short_delta = calculate_put_delta(spot, short_strike, dte, vol)
        short_put_price = black_scholes_put(spot, short_strike, dte, vol)
        return short_strike, long_strike, short_delta, short_put_price

    def _simulate_exit(
        self,
        trade: PutCreditTrade,
        prices: list[dict[str, Any]],
        vol: float,
        entry_idx: int,
    ) -> PutCreditTrade:
        """Simulate exit logic for a trade based on TP/SL/DTE rules.

        Iterates through daily prices after entry to find the exit point.
        """
        max_profit = trade.max_profit
        take_profit = max_profit * self.config.take_profit_pct
        stop_loss = -(max_profit * self.config.stop_loss_pct)

        for i in range(entry_idx + 1, len(prices)):
            day = prices[i]
            spot = day["close"]
            # Recalculate remaining DTE from the original entry DTE
            original_dte = (
                trade.entry_date + timedelta(days=self.config.max_dte) - trade.entry_date
            ).days
            remaining_dte = original_dte - (day["date"] - trade.entry_date).days

            if remaining_dte <= 0:
                # Expiry — close at intrinsic value
                short_intrinsic = max(0.0, trade.short_strike - spot)
                long_intrinsic = max(0.0, trade.long_strike - spot)
                current_debit = max(0.0, short_intrinsic - long_intrinsic)
                trade.pnl = (trade.credit - current_debit) * 100 * self.config.contracts
                trade.exit_reason = "expiry"
                trade.exit_price = current_debit
                trade.held_days = (day["date"] - trade.entry_date).days
                trade.exit_delta = calculate_put_delta(
                    spot, trade.short_strike, max(1, remaining_dte), vol
                )
                return trade

            # Calculate current spread value
            short_put = black_scholes_put(spot, trade.short_strike, remaining_dte, vol)
            long_put = black_scholes_put(spot, trade.long_strike, remaining_dte, vol)
            current_debit = max(0.0, short_put - long_put)
            current_pnl = (trade.credit - current_debit) * 100 * self.config.contracts

            held_days = (day["date"] - trade.entry_date).days

            # Check exit conditions (only after min hold period)
            if held_days >= self.config.min_hold_days:
                if current_pnl >= take_profit:
                    trade.pnl = current_pnl
                    trade.exit_reason = "profit_target"
                    trade.exit_price = current_debit
                    trade.held_days = held_days
                    trade.exit_delta = calculate_put_delta(
                        spot, trade.short_strike, remaining_dte, vol
                    )
                    return trade
                if current_pnl <= stop_loss:
                    trade.pnl = current_pnl
                    trade.exit_reason = "stop_loss"
                    trade.exit_price = current_debit
                    trade.held_days = held_days
                    trade.exit_delta = calculate_put_delta(
                        spot, trade.short_strike, remaining_dte, vol
                    )
                    return trade

            # DTE force exit
            if remaining_dte <= self.config.exit_dte:
                trade.pnl = current_pnl
                trade.exit_reason = "dte_exit"
                trade.exit_price = current_debit
                trade.held_days = held_days
                trade.exit_delta = calculate_put_delta(spot, trade.short_strike, remaining_dte, vol)
                return trade

        # If no exit triggered, close at last available price
        day = prices[-1]
        spot = day["close"]
        remaining_dte = max(
            1, (trade.entry_date + timedelta(days=self.config.max_dte) - day["date"]).days
        )
        short_put = black_scholes_put(spot, trade.short_strike, remaining_dte, vol)
        long_put = black_scholes_put(spot, trade.long_strike, remaining_dte, vol)
        current_debit = max(0.0, short_put - long_put)
        trade.pnl = (trade.credit - current_debit) * 100 * self.config.contracts
        trade.exit_reason = "end_of_data"
        trade.exit_price = current_debit
        trade.held_days = (day["date"] - trade.entry_date).days
        trade.exit_delta = calculate_put_delta(spot, trade.short_strike, remaining_dte, vol)
        return trade

    def backtest_strategy(self, start_date: str, end_date: str) -> dict[str, Any]:
        """Run backtest for bull put spread strategy over a date range.

        Entry logic:
          - On each trading day, check if delta band conditions are met
          - Enter a 1-lot bull put credit spread with target 0.15 delta
          - Apply TP/SL/DTE exit rules

        Args:
            start_date: ISO date string for backtest start.
            end_date: ISO date string for backtest end.

        Returns:
            Dictionary with backtest results and metrics.
        """
        prices = load_spy_prices(start_date, end_date)
        if not prices:
            return {"error": "No price data found for the specified date range"}

        self._price_lookup = {p["date"]: p for p in prices}

        # Estimate volatility from the price series
        close_prices = [p["close"] for p in prices]
        vol = estimate_volatility(close_prices)

        # Entry loop: try to enter a trade each day if conditions are met
        # Skip entries within min_hold_days of a previous entry (avoid same-day churn)
        last_entry_date: date | None = None

        for i, day in enumerate(prices):
            spot = day["close"]
            entry_date = day["date"]

            # Enforce min hold between entries (no same-day re-entry after a loss)
            if last_entry_date is not None:
                if (entry_date - last_entry_date).days < self.config.min_hold_days:
                    continue

            # Find strikes for target delta
            short_strike, long_strike, short_delta, short_put_price = self._find_entry_strike(
                spot, self.config.max_dte, vol
            )

            # Check delta band
            if not (self.config.delta_band_min <= abs(short_delta) <= self.config.delta_band_max):
                continue

            # Calculate credit
            credit = self.calculate_spread_premium(
                spot, short_strike, long_strike, self.config.max_dte, vol
            )

            # Subtract commission
            commission = self.config.commission_per_leg * 2 * self.config.contracts
            credit -= commission / 100.0  # commission is per share

            # Check min credit
            if credit < self.config.min_credit:
                continue

            # Create trade
            max_profit = credit * 100 * self.config.contracts
            max_loss = (self.config.wing_width - credit) * 100 * self.config.contracts

            trade = PutCreditTrade(
                entry_date=entry_date,
                exit_date=None,
                short_strike=short_strike,
                long_strike=long_strike,
                short_put_price=short_put_price,
                long_put_price=short_put_price - credit,
                credit=credit,
                max_profit=max_profit,
                max_loss=max_loss,
                entry_delta=short_delta,
            )

            # Simulate exit
            trade = self._simulate_exit(trade, prices, vol, i)
            self.trades.append(trade)
            last_entry_date = entry_date

        # Calculate results
        results = self.calculate_metrics()
        results["volatility_used"] = round(vol, 4)
        self.results = results
        return results

    def add_trade(self, trade_data: dict[str, Any]) -> None:
        """Add a trade to the backtest from a dictionary."""
        trade = PutCreditTrade(
            entry_date=datetime.strptime(trade_data["entry_date"], "%Y-%m-%d").date(),
            exit_date=datetime.strptime(trade_data["exit_date"], "%Y-%m-%d").date()
            if trade_data.get("exit_date")
            else None,
            short_strike=trade_data["short_strike"],
            long_strike=trade_data["long_strike"],
            short_put_price=trade_data.get("short_put_price", 0.0),
            long_put_price=trade_data.get("long_put_price", 0.0),
            credit=trade_data["credit"],
            max_profit=trade_data.get("max_profit", 0.0),
            max_loss=trade_data.get("max_loss", 0.0),
            exit_reason=trade_data.get("exit_reason"),
            exit_price=trade_data.get("exit_price"),
            pnl=trade_data.get("pnl", 0.0),
            held_days=trade_data.get("held_days", 0),
            entry_delta=trade_data.get("entry_delta", 0.0),
            exit_delta=trade_data.get("exit_delta", 0.0),
        )
        self.trades.append(trade)

    def calculate_metrics(self) -> dict[str, Any]:
        """Calculate performance metrics from completed trades."""
        if not self.trades:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "breakevens": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "total_pnl": 0.0,
                "max_drawdown": 0.0,
                "avg_credit": 0.0,
                "avg_hold_days": 0.0,
                "exit_reasons": {},
                "volatility_used": 0.0,
                "trades": [],
            }

        pnls = [t.pnl for t in self.trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        breakevens = [p for p in pnls if p == 0]

        total_pnl = sum(pnls)
        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        win_rate = len(wins) / len(self.trades) * 100
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0
        expectancy = total_pnl / len(self.trades)

        # Max drawdown on cumulative P&L
        cumulative = []
        running = 0.0
        for p in pnls:
            running += p
            cumulative.append(running)
        peak = cumulative[0]
        max_dd = 0.0
        for c in cumulative:
            if c > peak:
                peak = c
            dd = peak - c
            if dd > max_dd:
                max_dd = dd

        # Exit reason distribution
        exit_reasons: dict[str, int] = {}
        for t in self.trades:
            reason = t.exit_reason or "unknown"
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

        avg_credit = sum(t.credit for t in self.trades) / len(self.trades)
        avg_hold = sum(t.held_days for t in self.trades) / len(self.trades)

        return {
            "total_trades": len(self.trades),
            "wins": len(wins),
            "losses": len(losses),
            "breakevens": len(breakevens),
            "win_rate": round(win_rate, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else 999.99,
            "expectancy": round(expectancy, 2),
            "total_pnl": round(total_pnl, 2),
            "max_drawdown": round(max_dd, 2),
            "avg_credit": round(avg_credit, 4),
            "avg_hold_days": round(avg_hold, 1),
            "exit_reasons": exit_reasons,
            "trades": [
                {
                    "entry_date": t.entry_date.isoformat(),
                    "exit_reason": t.exit_reason,
                    "credit": round(t.credit, 4),
                    "pnl": round(t.pnl, 2),
                    "held_days": t.held_days,
                    "short_strike": t.short_strike,
                    "long_strike": t.long_strike,
                    "entry_delta": round(t.entry_delta, 4),
                }
                for t in self.trades
            ],
        }


def main():
    """CLI entry point for running the backtest."""
    parser = argparse.ArgumentParser(description="Backtest SPY bull put credit spreads")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed trade log")
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file path (default: print to stdout)",
    )
    args = parser.parse_args()

    config = BacktestConfig()
    backtester = BullPutSpreadBacktester(config)
    results = backtester.backtest_strategy(args.start, args.end)

    if args.verbose:
        print(f"\n{'=' * 60}")
        print(f"Bull Put Credit Spread Backtest: {args.start} to {args.end}")
        print(f"{'=' * 60}")
        print(f"Volatility used: {results.get('volatility_used', 'N/A')}")
        print("\nSummary:")
        print(f"  Total trades: {results['total_trades']}")
        print(
            f"  Wins: {results['wins']}, Losses: {results['losses']}, Breakevens: {results['breakevens']}"
        )
        print(f"  Win rate: {results['win_rate']}%")
        print(f"  Avg win: ${results['avg_win']}")
        print(f"  Avg loss: ${results['avg_loss']}")
        print(f"  Profit factor: {results['profit_factor']}")
        print(f"  Expectancy: ${results['expectancy']}/trade")
        print(f"  Total P&L: ${results['total_pnl']}")
        print(f"  Max drawdown: ${results['max_drawdown']}")
        print(f"  Avg credit: ${results['avg_credit']}")
        print(f"  Avg hold: {results['avg_hold_days']} days")
        print(f"\n  Exit reasons: {results['exit_reasons']}")
        print("\n  Trades:")
        for t in results.get("trades", []):
            print(
                f"    {t['entry_date']}: credit=${t['credit']}, pnl=${t['pnl']}, "
                f"exit={t['exit_reason']}, held={t['held_days']}d, delta={t['entry_delta']}"
            )

    output = json.dumps(results, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Results written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
