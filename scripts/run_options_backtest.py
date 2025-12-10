#!/usr/bin/env python3
"""
Options Backtest - 6-Month Comprehensive Analysis

This script backtests covered calls and iron condors on SPY/QQQ
using historical data from June 2024 to December 2024.

Strategy Parameters:
- Covered Calls: 0.30 delta, 30-45 DTE
- Iron Condors: 0.16 delta wings, 45 DTE
- Target: $10/day premium income

Metrics Calculated:
- Win rate
- Sharpe ratio
- Maximum drawdown
- Total return
- Average daily P&L
- Risk-adjusted returns
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Use Alpaca for historical data (optional)
try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class OptionsBacktest:
    """
    Options-specific backtest engine for covered calls and iron condors.

    This backtester simulates options strategies using historical price data
    and statistical approximations for options pricing (since historical options
    data is limited/expensive).
    """

    def __init__(
        self,
        start_date: str = "2024-06-01",
        end_date: str = "2024-12-01",
        initial_capital: float = 100000.0,
    ):
        """
        Initialize options backtest.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_capital: Starting capital
        """
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.initial_capital = initial_capital
        self.current_capital = initial_capital

        # Portfolio state
        self.positions = []  # List of open positions
        self.closed_trades = []  # List of closed trades
        self.equity_curve = [initial_capital]
        self.dates = [start_date]

        # Strategy parameters
        self.covered_call_delta = 0.30
        self.covered_call_dte_min = 30
        self.covered_call_dte_max = 45

        self.iron_condor_delta = 0.16
        self.iron_condor_dte = 45

        self.target_daily_premium = 10.0

        # Historical data cache
        self.price_data = {}

        logger.info(f"Options Backtest initialized: {start_date} to {end_date}")
        logger.info(f"Initial Capital: ${initial_capital:,.2f}")

    def load_historical_data(self, symbols: list[str]) -> None:
        """
        Load historical price data - uses simulated data if API not available.

        Args:
            symbols: List of symbols (e.g., ['SPY', 'QQQ'])
        """
        logger.info(f"Loading historical data for {symbols}...")

        # Try Alpaca API first if available
        alpaca_key = os.getenv("ALPACA_API_KEY")
        alpaca_secret = os.getenv("ALPACA_SECRET_KEY")

        if ALPACA_AVAILABLE and alpaca_key and alpaca_secret:
            logger.info("Using Alpaca API for historical data...")
            self._load_from_alpaca(symbols, alpaca_key, alpaca_secret)
        else:
            if not ALPACA_AVAILABLE:
                logger.warning("Alpaca client not available - using simulated data")
            else:
                logger.warning("Alpaca credentials not found - using simulated data")
            self._generate_synthetic_data(symbols)

    def _load_from_alpaca(self, symbols: list[str], api_key: str, secret_key: str) -> None:
        """Load data from Alpaca API."""
        client = StockHistoricalDataClient(api_key, secret_key)

        for symbol in symbols:
            try:
                start_buffered = self.start_date - timedelta(days=252)
                end_buffered = self.end_date + timedelta(days=1)

                request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=TimeFrame.Day,
                    start=start_buffered,
                    end=end_buffered,
                    adjustment="all",
                )

                bars = client.get_stock_bars(request).df

                if bars is None or bars.empty:
                    logger.warning(f"No data for {symbol}, using synthetic")
                    self._generate_synthetic_data([symbol])
                    continue

                if "symbol" in bars.index.names:
                    bars = bars.droplevel("symbol")

                hist = bars.rename(
                    columns={
                        "open": "Open",
                        "high": "High",
                        "low": "Low",
                        "close": "Close",
                        "volume": "Volume",
                    }
                )

                hist["Returns"] = hist["Close"].pct_change()
                hist["HV_20"] = hist["Returns"].rolling(20).std() * np.sqrt(252)
                hist["HV_30"] = hist["Returns"].rolling(30).std() * np.sqrt(252)

                self.price_data[symbol] = hist
                logger.info(f"Loaded {len(hist)} bars for {symbol} from Alpaca")

            except Exception as e:
                logger.error(f"Alpaca failed for {symbol}: {e}, using synthetic")
                self._generate_synthetic_data([symbol])

    def _generate_synthetic_data(self, symbols: list[str]) -> None:
        """
        Generate synthetic price data for backtesting when real data unavailable.

        Uses realistic parameters based on SPY/QQQ historical behavior:
        - SPY: ~$450 starting price, 15% annual volatility
        - QQQ: ~$400 starting price, 20% annual volatility
        """
        logger.info("Generating synthetic price data for backtesting...")

        symbol_params = {
            "SPY": {"start_price": 450.0, "annual_vol": 0.15, "drift": 0.10},
            "QQQ": {"start_price": 400.0, "annual_vol": 0.20, "drift": 0.12},
        }

        # Generate date range
        start_buffered = self.start_date - timedelta(days=252)
        date_range = pd.date_range(start=start_buffered, end=self.end_date, freq="D")
        date_range = date_range[date_range.weekday < 5]  # Weekdays only

        for symbol in symbols:
            params = symbol_params.get(
                symbol, {"start_price": 100.0, "annual_vol": 0.18, "drift": 0.08}
            )

            # Generate geometric Brownian motion
            np.random.seed(42)  # Deterministic for testing
            n_days = len(date_range)
            dt = 1 / 252  # Daily time step

            # Daily returns following GBM
            returns = np.random.normal(
                params["drift"] * dt, params["annual_vol"] * np.sqrt(dt), n_days
            )

            # Generate price path
            prices = params["start_price"] * np.exp(np.cumsum(returns))

            # Create DataFrame
            hist = pd.DataFrame(
                {
                    "Open": prices * (1 + np.random.normal(0, 0.002, n_days)),
                    "High": prices * (1 + abs(np.random.normal(0, 0.005, n_days))),
                    "Low": prices * (1 - abs(np.random.normal(0, 0.005, n_days))),
                    "Close": prices,
                    "Volume": np.random.uniform(50_000_000, 100_000_000, n_days),
                },
                index=date_range,
            )

            # Calculate volatility
            hist["Returns"] = hist["Close"].pct_change()
            hist["HV_20"] = hist["Returns"].rolling(20).std() * np.sqrt(252)
            hist["HV_30"] = hist["Returns"].rolling(30).std() * np.sqrt(252)

            self.price_data[symbol] = hist
            logger.info(
                f"Generated {len(hist)} synthetic bars for {symbol} "
                f"(price range: ${hist['Close'].min():.2f} - ${hist['Close'].max():.2f})"
            )

    def estimate_option_premium(
        self,
        underlying_price: float,
        strike: float,
        dte: int,
        iv: float,
        option_type: str = "call",
        delta_target: float = 0.30,
    ) -> dict:
        """
        Estimate option premium using simplified Black-Scholes approximation.

        For backtesting purposes, we use statistical approximations rather than
        full Black-Scholes since we don't have historical options data.

        Args:
            underlying_price: Current stock price
            strike: Strike price
            dte: Days to expiration
            iv: Implied volatility (annualized)
            option_type: 'call' or 'put'
            delta_target: Target delta (used for strike selection)

        Returns:
            Dictionary with premium estimate and greeks
        """
        # Simplified approach: Premium ≈ expected move * probability
        # This is a rough approximation for backtesting

        # Calculate expected move based on IV and DTE
        time_factor = np.sqrt(dte / 252)
        expected_move = underlying_price * iv * time_factor

        # Delta approximation based on moneyness
        moneyness = (strike - underlying_price) / underlying_price

        # Rough delta estimate (this would normally use cumulative normal distribution)
        if option_type == "call":
            if strike > underlying_price:  # OTM call
                # Delta decreases as strike moves away from spot
                delta = 0.5 * np.exp(-abs(moneyness) * 2)
            else:  # ITM call
                delta = 0.5 + 0.5 * (1 - np.exp(-abs(moneyness) * 2))
        else:  # put
            if strike < underlying_price:  # OTM put
                delta = -0.5 * np.exp(-abs(moneyness) * 2)
            else:  # ITM put
                delta = -0.5 - 0.5 * (1 - np.exp(-abs(moneyness) * 2))

        # Premium approximation: Time value + intrinsic value
        intrinsic = (
            max(0, underlying_price - strike)
            if option_type == "call"
            else max(0, strike - underlying_price)
        )

        # Time value based on IV, DTE, and delta
        time_value = abs(delta) * expected_move * 0.4  # Scaling factor

        premium = intrinsic + time_value

        # Theta approximation (daily decay)
        theta = -time_value / dte if dte > 0 else 0

        return {
            "premium": premium,
            "delta": abs(delta),
            "theta": theta,
            "iv": iv,
            "expected_move": expected_move,
        }

    def find_covered_call_strike(
        self,
        symbol: str,
        current_date: datetime,
        dte: int = 35,
    ) -> dict | None:
        """
        Find optimal strike for covered call based on delta target.

        Args:
            symbol: Underlying symbol
            current_date: Current date
            dte: Days to expiration

        Returns:
            Strike details or None if no suitable strike found
        """
        if symbol not in self.price_data:
            return None

        hist = self.price_data[symbol]

        # Get data up to current date
        hist_filtered = hist[hist.index <= current_date]
        if len(hist_filtered) < 30:
            return None

        current_price = float(hist_filtered["Close"].iloc[-1])
        iv = float(hist_filtered["HV_30"].iloc[-1])

        if pd.isna(iv) or iv <= 0:
            iv = 0.20  # Default IV if not available

        # Search for strike that gives target delta
        # For OTM calls, strike > spot
        # Target delta = 0.30 typically means strike ~5-10% OTM

        best_strike = None
        best_delta_diff = float("inf")

        # Search strikes from 1% to 15% OTM
        for pct_otm in np.arange(0.01, 0.15, 0.005):
            strike = current_price * (1 + pct_otm)

            option_data = self.estimate_option_premium(
                underlying_price=current_price,
                strike=strike,
                dte=dte,
                iv=iv,
                option_type="call",
            )

            delta_diff = abs(option_data["delta"] - self.covered_call_delta)

            if delta_diff < best_delta_diff:
                best_delta_diff = delta_diff
                best_strike = {
                    "strike": strike,
                    "premium": option_data["premium"],
                    "delta": option_data["delta"],
                    "theta": option_data["theta"],
                    "iv": iv,
                    "underlying_price": current_price,
                    "dte": dte,
                }

        return best_strike

    def simulate_covered_call(
        self,
        symbol: str,
        entry_date: datetime,
        exit_date: datetime,
    ) -> dict | None:
        """
        Simulate a covered call trade from entry to exit.

        Args:
            symbol: Underlying symbol
            entry_date: Trade entry date
            exit_date: Trade exit date

        Returns:
            Trade result dictionary
        """
        hist = self.price_data[symbol]

        # Get entry data
        hist_entry = hist[hist.index <= entry_date]
        if len(hist_entry) < 30:
            return None

        entry_price = float(hist_entry["Close"].iloc[-1])

        # Find strike
        dte = (exit_date - entry_date).days
        strike_data = self.find_covered_call_strike(symbol, entry_date, dte)

        if not strike_data:
            return None

        strike = strike_data["strike"]
        premium_collected = strike_data["premium"]

        # Get exit data
        hist_exit = hist[hist.index <= exit_date]
        if len(hist_exit) == 0:
            return None

        exit_price = float(hist_exit["Close"].iloc[-1])

        # Calculate P&L
        # Covered call = Long stock + Short call
        stock_pnl = exit_price - entry_price

        # Call P&L (we sold it, so we profit if it expires worthless)
        if exit_price >= strike:
            # Stock called away - we keep premium but miss upside
            call_pnl = premium_collected  # We keep premium
            final_stock_pnl = strike - entry_price  # Stock sold at strike
            assigned = True
        else:
            # Call expires worthless - we keep stock and premium
            call_pnl = premium_collected
            final_stock_pnl = stock_pnl
            assigned = False

        total_pnl = final_stock_pnl + call_pnl

        return {
            "symbol": symbol,
            "strategy": "covered_call",
            "entry_date": entry_date.strftime("%Y-%m-%d"),
            "exit_date": exit_date.strftime("%Y-%m-%d"),
            "entry_price": entry_price,
            "exit_price": exit_price,
            "strike": strike,
            "premium": premium_collected,
            "dte": dte,
            "delta": strike_data["delta"],
            "assigned": assigned,
            "stock_pnl": final_stock_pnl,
            "option_pnl": call_pnl,
            "total_pnl": total_pnl,
            "return_pct": (total_pnl / entry_price) * 100,
        }

    def simulate_iron_condor(
        self,
        symbol: str,
        entry_date: datetime,
        exit_date: datetime,
    ) -> dict | None:
        """
        Simulate an iron condor trade.

        Iron condor = Short OTM put + Long OTM put (put spread)
                     + Short OTM call + Long OTM call (call spread)

        Args:
            symbol: Underlying symbol
            entry_date: Trade entry date
            exit_date: Trade exit date

        Returns:
            Trade result dictionary
        """
        hist = self.price_data[symbol]

        # Get entry data
        hist_entry = hist[hist.index <= entry_date]
        if len(hist_entry) < 30:
            return None

        entry_price = float(hist_entry["Close"].iloc[-1])
        iv = float(hist_entry["HV_30"].iloc[-1])

        if pd.isna(iv) or iv <= 0:
            iv = 0.20

        dte = (exit_date - entry_date).days

        # Iron condor structure (balanced around current price)
        # Call spread: Sell 16 delta call, Buy 5 delta call
        # Put spread: Sell 16 delta put, Buy 5 delta put

        # Approximate strikes based on delta
        # 16 delta call ~ 5-7% OTM
        # 5 delta call ~ 10-12% OTM
        short_call_strike = entry_price * 1.06
        long_call_strike = entry_price * 1.11

        # 16 delta put ~ 5-7% OTM
        # 5 delta put ~ 10-12% OTM
        short_put_strike = entry_price * 0.94
        long_put_strike = entry_price * 0.89

        # Calculate premiums
        short_call_data = self.estimate_option_premium(
            entry_price, short_call_strike, dte, iv, "call"
        )
        long_call_data = self.estimate_option_premium(
            entry_price, long_call_strike, dte, iv, "call"
        )
        short_put_data = self.estimate_option_premium(entry_price, short_put_strike, dte, iv, "put")
        long_put_data = self.estimate_option_premium(entry_price, long_put_strike, dte, iv, "put")

        # Net credit = premium collected - premium paid
        call_spread_credit = short_call_data["premium"] - long_call_data["premium"]
        put_spread_credit = short_put_data["premium"] - long_put_data["premium"]
        total_credit = call_spread_credit + put_spread_credit

        # Get exit data
        hist_exit = hist[hist.index <= exit_date]
        if len(hist_exit) == 0:
            return None

        exit_price = float(hist_exit["Close"].iloc[-1])

        # Calculate P&L at expiration
        # Win if price stays between short strikes
        # Max loss if price breaches a wing

        if short_put_strike <= exit_price <= short_call_strike:
            # Price inside range - all options expire worthless
            # We keep the full credit
            pnl = total_credit
            outcome = "max_profit"
        elif exit_price > short_call_strike:
            # Call spread tested
            if exit_price >= long_call_strike:
                # Max loss on call spread
                call_spread_loss = long_call_strike - short_call_strike
                pnl = total_credit - call_spread_loss
                outcome = "call_max_loss"
            else:
                # Partial loss on call spread
                call_spread_loss = exit_price - short_call_strike
                pnl = total_credit - call_spread_loss
                outcome = "call_tested"
        else:
            # Put spread tested
            if exit_price <= long_put_strike:
                # Max loss on put spread
                put_spread_loss = short_put_strike - long_put_strike
                pnl = total_credit - put_spread_loss
                outcome = "put_max_loss"
            else:
                # Partial loss on put spread
                put_spread_loss = short_put_strike - exit_price
                pnl = total_credit - put_spread_loss
                outcome = "put_tested"

        return {
            "symbol": symbol,
            "strategy": "iron_condor",
            "entry_date": entry_date.strftime("%Y-%m-%d"),
            "exit_date": exit_date.strftime("%Y-%m-%d"),
            "entry_price": entry_price,
            "exit_price": exit_price,
            "short_call_strike": short_call_strike,
            "long_call_strike": long_call_strike,
            "short_put_strike": short_put_strike,
            "long_put_strike": long_put_strike,
            "credit_collected": total_credit,
            "dte": dte,
            "outcome": outcome,
            "pnl": pnl,
            "return_pct": (pnl / (long_call_strike - short_call_strike)) * 100,  # Return on risk
        }

    def run_backtest(self, symbols: list[str] = None) -> dict:
        """
        Run comprehensive backtest for options strategies.

        Args:
            symbols: List of underlying symbols

        Returns:
            Backtest results dictionary
        """
        if symbols is None:
            symbols = ["SPY", "QQQ"]
        logger.info("=" * 80)
        logger.info("STARTING OPTIONS BACKTEST")
        logger.info("=" * 80)

        # Load data
        self.load_historical_data(symbols)

        # Generate trading dates (weekly options cycle for monthlies)
        current_date = self.start_date

        while current_date <= self.end_date:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            # Simulate trades every 2 weeks (to avoid overlapping positions)
            for symbol in symbols:
                # Covered Call (35 DTE)
                exit_date = current_date + timedelta(days=35)
                if exit_date <= self.end_date:
                    cc_trade = self.simulate_covered_call(symbol, current_date, exit_date)
                    if cc_trade:
                        self.closed_trades.append(cc_trade)

                # Iron Condor (45 DTE)
                exit_date = current_date + timedelta(days=45)
                if exit_date <= self.end_date:
                    ic_trade = self.simulate_iron_condor(symbol, current_date, exit_date)
                    if ic_trade:
                        self.closed_trades.append(ic_trade)

            # Move to next cycle (every 14 days to avoid overlap)
            current_date += timedelta(days=14)

        # Calculate metrics
        results = self._calculate_metrics()

        logger.info("=" * 80)
        logger.info("BACKTEST COMPLETE")
        logger.info("=" * 80)

        # Handle error responses
        if "error" in results:
            logger.error(f"Backtest error: {results['error']}")
            return results

        # Log results
        overall = results.get("overall_metrics", {})
        logger.info(f"Total Trades: {overall.get('total_trades', 0)}")
        logger.info(f"Win Rate: {overall.get('win_rate', 0):.1f}%")
        logger.info(f"Total Return: {overall.get('total_return', 0):.2f}%")
        logger.info(f"Sharpe Ratio: {overall.get('sharpe_ratio', 0):.2f}")
        logger.info(f"Max Drawdown: {overall.get('max_drawdown', 0):.2f}%")

        return results

    def _calculate_metrics(self) -> dict:
        """Calculate comprehensive performance metrics."""
        if not self.closed_trades:
            return {
                "error": "No trades executed",
                "total_trades": 0,
            }

        # Basic stats
        total_trades = len(self.closed_trades)

        # Separate by strategy (filter out None trades)
        valid_trades = [t for t in self.closed_trades if t is not None and "pnl" in t]
        cc_trades = [t for t in valid_trades if t.get("strategy") == "covered_call"]
        ic_trades = [t for t in valid_trades if t.get("strategy") == "iron_condor"]

        if not valid_trades:
            logger.warning("No valid trades with P&L data")
            return {
                "error": "No valid trades",
                "total_trades": total_trades,
                "valid_trades": 0,
            }

        # Win rate
        winning_trades = [t for t in valid_trades if t.get("pnl", 0) > 0]
        win_rate = (len(winning_trades) / len(valid_trades) * 100) if valid_trades else 0

        # P&L
        total_pnl = sum(t.get("pnl", 0) for t in valid_trades)
        avg_pnl = total_pnl / len(valid_trades) if valid_trades else 0

        # Calculate daily P&L for Sharpe
        trade_returns = [t.get("pnl", 0) for t in valid_trades]

        # Sharpe ratio (simplified - using trade returns)
        if len(trade_returns) > 1:
            mean_return = np.mean(trade_returns)
            std_return = np.std(trade_returns)
            sharpe = (mean_return / std_return) * np.sqrt(252 / 35) if std_return > 0 else 0
        else:
            sharpe = 0.0

        # Drawdown
        cumulative_pnl = np.cumsum(trade_returns)
        running_max = np.maximum.accumulate(cumulative_pnl)
        drawdown = cumulative_pnl - running_max
        max_drawdown = abs(np.min(drawdown)) if len(drawdown) > 0 else 0
        max_drawdown_pct = (
            (max_drawdown / self.initial_capital * 100) if self.initial_capital > 0 else 0
        )

        # Total return
        total_return = (total_pnl / self.initial_capital * 100) if self.initial_capital > 0 else 0

        # Strategy-specific metrics
        cc_win_rate = (
            (len([t for t in cc_trades if t.get("pnl", 0) > 0]) / len(cc_trades) * 100)
            if cc_trades
            else 0
        )
        ic_win_rate = (
            (len([t for t in ic_trades if t.get("pnl", 0) > 0]) / len(ic_trades) * 100)
            if ic_trades
            else 0
        )

        cc_avg_pnl = np.mean([t.get("pnl", 0) for t in cc_trades]) if cc_trades else 0
        ic_avg_pnl = np.mean([t.get("pnl", 0) for t in ic_trades]) if ic_trades else 0

        # Daily metrics
        trading_days = (self.end_date - self.start_date).days
        avg_daily_pnl = total_pnl / trading_days if trading_days > 0 else 0

        return {
            "backtest_period": {
                "start": self.start_date.strftime("%Y-%m-%d"),
                "end": self.end_date.strftime("%Y-%m-%d"),
                "days": trading_days,
            },
            "capital": {
                "initial": self.initial_capital,
                "final": self.initial_capital + total_pnl,
            },
            "overall_metrics": {
                "total_trades": len(valid_trades),
                "winning_trades": len(winning_trades),
                "losing_trades": len(valid_trades) - len(winning_trades),
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "total_return": total_return,
                "avg_pnl_per_trade": avg_pnl,
                "avg_daily_pnl": avg_daily_pnl,
                "sharpe_ratio": sharpe,
                "max_drawdown": max_drawdown_pct,
                "max_drawdown_dollars": max_drawdown,
            },
            "covered_calls": {
                "total_trades": len(cc_trades),
                "win_rate": cc_win_rate,
                "avg_pnl": cc_avg_pnl,
                "total_pnl": sum(t.get("pnl", 0) for t in cc_trades),
                "assignments": len([t for t in cc_trades if t.get("assigned", False)]),
            },
            "iron_condors": {
                "total_trades": len(ic_trades),
                "win_rate": ic_win_rate,
                "avg_pnl": ic_avg_pnl,
                "total_pnl": sum(t.get("pnl", 0) for t in ic_trades),
                "max_profit_outcomes": len(
                    [t for t in ic_trades if t.get("outcome") == "max_profit"]
                ),
            },
            "trades": valid_trades,
        }


def main():
    """Run options backtest and save results."""
    logger.info("Starting 6-Month Options Backtest")

    # Initialize backtest
    backtest = OptionsBacktest(
        start_date="2024-06-01",
        end_date="2024-12-01",
        initial_capital=100000.0,
    )

    # Run backtest
    results = backtest.run_backtest(symbols=["SPY", "QQQ"])

    # Save results
    output_dir = project_root / "data" / "backtests"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "options_backtest_6month.json"

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Results saved to {output_file}")

    # Print summary
    print("\n" + "=" * 80)
    print("OPTIONS BACKTEST SUMMARY")
    print("=" * 80)
    print(f"\nPeriod: {results['backtest_period']['start']} to {results['backtest_period']['end']}")
    print(f"Initial Capital: ${results['capital']['initial']:,.2f}")
    print(f"Final Capital: ${results['capital']['final']:,.2f}")
    print(f"\nTotal Trades: {results['overall_metrics']['total_trades']}")
    print(f"Win Rate: {results['overall_metrics']['win_rate']:.1f}%")
    print(f"Total Return: {results['overall_metrics']['total_return']:.2f}%")
    print(f"Sharpe Ratio: {results['overall_metrics']['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {results['overall_metrics']['max_drawdown']:.2f}%")
    print(f"Avg Daily P&L: ${results['overall_metrics']['avg_daily_pnl']:.2f}")

    print("\nCovered Calls:")
    print(f"  Trades: {results['covered_calls']['total_trades']}")
    print(f"  Win Rate: {results['covered_calls']['win_rate']:.1f}%")
    print(f"  Avg P&L: ${results['covered_calls']['avg_pnl']:.2f}")
    print(f"  Total P&L: ${results['covered_calls']['total_pnl']:.2f}")

    print("\nIron Condors:")
    print(f"  Trades: {results['iron_condors']['total_trades']}")
    print(f"  Win Rate: {results['iron_condors']['win_rate']:.1f}%")
    print(f"  Avg P&L: ${results['iron_condors']['avg_pnl']:.2f}")
    print(f"  Total P&L: ${results['iron_condors']['total_pnl']:.2f}")

    print("\n" + "=" * 80)

    return results


if __name__ == "__main__":
    main()
