#!/usr/bin/env python3
"""
Crypto Strategy Backtest Comparison: v3.0 vs v4.1

This script backtests two crypto trading strategies over the past 90 days:

v3.0: Fear & Greed Strategy
- Buy when Fear & Greed Index < 25 (Extreme Fear)
- No trend filter (no 50-day MA check)
- No momentum filter (no RSI check)

v4.1: Trend + Momentum Strategy
- Buy ONLY when price > 50-day MA (trend filter)
- AND RSI > 50 (momentum confirmation)
- Fear & Greed for position sizing only

Metrics Compared:
- Total Return (%)
- Max Drawdown (%)
- Win Rate (%)
- Sharpe Ratio
- Number of Trades
- Average Trade P/L

Usage:
    python3 scripts/backtest_crypto_strategy.py
"""

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf


@dataclass
class BacktestConfig:
    """Configuration for backtest run."""

    initial_capital: float = 1000.0
    daily_amount: float = 25.0
    lookback_days: int = 90
    stop_loss_pct: float = 0.07  # 7% stop-loss for crypto
    take_profit_pct: float = 0.10  # 10% take-profit
    symbols: list = None

    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["BTC-USD", "ETH-USD", "SOL-USD"]


@dataclass
class Trade:
    """Single trade record."""

    date: str
    symbol: str
    action: str  # BUY or SELL
    price: float
    quantity: float
    amount: float
    reason: str
    portfolio_value: float


@dataclass
class BacktestResult:
    """Results from a backtest run."""

    strategy_name: str
    strategy_version: str
    initial_capital: float
    final_capital: float
    total_return_pct: float
    max_drawdown_pct: float
    win_rate: float
    sharpe_ratio: float
    num_trades: int
    avg_trade_pl: float
    trades: list
    daily_values: list


class CryptoBacktester:
    """Backtester for crypto trading strategies."""

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.cash = config.initial_capital
        self.positions = {}  # symbol -> {qty, entry_price, entry_date}
        self.trades = []
        self.daily_values = []

    def fetch_historical_data(self) -> dict:
        """
        Fetch historical price data for all crypto symbols.

        Returns:
            Dict of symbol -> DataFrame with OHLCV data
        """
        print(f"📊 Fetching {self.config.lookback_days} days of historical data...")

        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.config.lookback_days + 60)  # Extra buffer for MA

        data = {}
        for symbol in self.config.symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(start=start_date, end=end_date)

                if hist.empty:
                    print(f"   ⚠️  No data for {symbol}")
                    continue

                # Calculate indicators
                hist["MA50"] = hist["Close"].rolling(window=50).mean()
                hist["RSI"] = self._calculate_rsi(hist["Close"])

                data[symbol] = hist
                print(f"   ✅ {symbol}: {len(hist)} bars")

            except Exception as e:
                print(f"   ❌ Failed to fetch {symbol}: {e}")

        return data

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index (RSI)."""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def fetch_fear_greed_historical(self) -> dict:
        """
        Fetch historical Fear & Greed Index data.

        Returns:
            Dict of date -> fear_greed_value
        """
        print("😱 Fetching Fear & Greed Index history...")

        try:
            # API returns last 90 days
            response = requests.get("https://api.alternative.me/fng/?limit=90", timeout=10)
            response.raise_for_status()
            data = response.json()

            fear_greed = {}
            for item in data["data"]:
                # Convert timestamp to date
                date = datetime.fromtimestamp(int(item["timestamp"])).strftime("%Y-%m-%d")
                fear_greed[date] = int(item["value"])

            print(f"   ✅ Fetched {len(fear_greed)} days of Fear & Greed data")
            return fear_greed

        except Exception as e:
            print(f"   ⚠️  Failed to fetch Fear & Greed data: {e}")
            print("   Using simulated data (random values 20-80)")
            # Fallback: simulate Fear & Greed data
            end_date = datetime.now()
            fear_greed = {}
            for i in range(90):
                date = (end_date - timedelta(days=i)).strftime("%Y-%m-%d")
                fear_greed[date] = np.random.randint(20, 80)
            return fear_greed

    def backtest_v3(self, price_data: dict, fear_greed: dict) -> BacktestResult:
        """
        Backtest v3.0 strategy: Buy when Fear & Greed < 25 (no filters).

        Args:
            price_data: Historical price data
            fear_greed: Historical Fear & Greed Index

        Returns:
            BacktestResult object
        """
        print("\n" + "=" * 80)
        print("🔵 BACKTESTING v3.0: Fear & Greed Strategy (No Filters)")
        print("=" * 80)

        # Reset state
        self.cash = self.config.initial_capital
        self.positions = {}
        self.trades = []
        self.daily_values = []

        # Get date range (last 90 days)
        all_dates = sorted(set(price_data["BTC-USD"].index.strftime("%Y-%m-%d")))[-90:]

        for date_str in all_dates:
            date = pd.to_datetime(date_str)

            # Check and manage existing positions (stop-loss/take-profit)
            self._manage_positions_v3(date, price_data)

            # Get Fear & Greed for this date
            fg_value = fear_greed.get(date_str, 50)  # Default to neutral if missing

            # v3.0 RULE: Buy when Fear & Greed < 25 (Extreme Fear)
            if fg_value >= 25:
                # No trade signal
                portfolio_value = self._calculate_portfolio_value(date, price_data)
                self.daily_values.append((date_str, portfolio_value))
                continue

            # Extreme Fear detected - find best crypto
            print(f"\n📅 {date_str}: Fear & Greed = {fg_value} (EXTREME FEAR)")

            # Select best crypto based on 7-day momentum
            best_symbol = self._select_best_crypto(date, price_data)
            if not best_symbol:
                portfolio_value = self._calculate_portfolio_value(date, price_data)
                self.daily_values.append((date_str, portfolio_value))
                continue

            # Check if we have data for this date
            if date not in price_data[best_symbol].index:
                portfolio_value = self._calculate_portfolio_value(date, price_data)
                self.daily_values.append((date_str, portfolio_value))
                continue

            current_price = float(price_data[best_symbol].loc[date, "Close"])

            # Execute buy if we have cash
            if self.cash >= self.config.daily_amount:
                quantity = self.config.daily_amount / current_price

                # Record trade
                trade = Trade(
                    date=date_str,
                    symbol=best_symbol,
                    action="BUY",
                    price=current_price,
                    quantity=quantity,
                    amount=self.config.daily_amount,
                    reason=f"Fear & Greed {fg_value} < 25",
                    portfolio_value=self.cash,
                )
                self.trades.append(trade)

                # Update position
                if best_symbol not in self.positions:
                    self.positions[best_symbol] = {
                        "qty": 0,
                        "cost_basis": 0,
                        "entry_date": date_str,
                    }

                pos = self.positions[best_symbol]
                total_qty = pos["qty"] + quantity
                pos["cost_basis"] = (pos["cost_basis"] * pos["qty"] + current_price * quantity) / total_qty
                pos["qty"] = total_qty
                pos["entry_date"] = date_str

                self.cash -= self.config.daily_amount

                print(f"   🟢 BUY {quantity:.6f} {best_symbol} @ ${current_price:.2f}")

            # Track daily portfolio value
            portfolio_value = self._calculate_portfolio_value(date, price_data)
            self.daily_values.append((date_str, portfolio_value))

        # Close all positions at end of backtest
        self._close_all_positions(all_dates[-1], price_data, "Backtest complete")

        # Calculate metrics
        return self._calculate_metrics("Fear & Greed Strategy", "v3.0")

    def backtest_v4_1(self, price_data: dict, fear_greed: dict) -> BacktestResult:
        """
        Backtest v4.1 strategy: Buy when price > 50-day MA AND RSI > 50.

        Args:
            price_data: Historical price data
            fear_greed: Historical Fear & Greed Index (for sizing only)

        Returns:
            BacktestResult object
        """
        print("\n" + "=" * 80)
        print("🟢 BACKTESTING v4.1: Trend + Momentum Strategy")
        print("=" * 80)

        # Reset state
        self.cash = self.config.initial_capital
        self.positions = {}
        self.trades = []
        self.daily_values = []

        # Get date range (last 90 days)
        all_dates = sorted(set(price_data["BTC-USD"].index.strftime("%Y-%m-%d")))[-90:]

        for date_str in all_dates:
            date = pd.to_datetime(date_str)

            # Check and manage existing positions (stop-loss/take-profit)
            self._manage_positions_v4(date, price_data)

            # v4.1 RULE: Check which cryptos meet filters
            valid_cryptos = {}
            for symbol in self.config.symbols:
                if date not in price_data[symbol].index:
                    continue

                row = price_data[symbol].loc[date]
                price = float(row["Close"])
                ma50 = float(row["MA50"]) if not pd.isna(row["MA50"]) else None
                rsi = float(row["RSI"]) if not pd.isna(row["RSI"]) else None

                if ma50 is None or rsi is None:
                    continue

                # Check v4.1 filters
                above_ma = price > ma50
                rsi_bullish = rsi > 50

                if above_ma and rsi_bullish:
                    # Calculate 7-day momentum
                    week_ago = date - timedelta(days=7)
                    if week_ago in price_data[symbol].index:
                        price_week_ago = float(price_data[symbol].loc[week_ago, "Close"])
                        momentum_7d = ((price - price_week_ago) / price_week_ago) * 100
                    else:
                        momentum_7d = 0

                    valid_cryptos[symbol] = {
                        "price": price,
                        "ma50": ma50,
                        "rsi": rsi,
                        "momentum_7d": momentum_7d,
                    }

            # If no crypto passes filters, skip this day
            if not valid_cryptos:
                portfolio_value = self._calculate_portfolio_value(date, price_data)
                self.daily_values.append((date_str, portfolio_value))
                continue

            # Select best crypto (highest 7-day momentum)
            best_symbol = max(valid_cryptos.keys(), key=lambda s: valid_cryptos[s]["momentum_7d"])
            best_data = valid_cryptos[best_symbol]

            print(
                f"\n📅 {date_str}: {best_symbol} - Price ${best_data['price']:.0f}, "
                f"MA50 ${best_data['ma50']:.0f}, RSI {best_data['rsi']:.0f}"
            )

            # Check Fear & Greed for position sizing
            fg_value = fear_greed.get(date_str, 50)
            size_multiplier = 1.0
            if fg_value <= 25:
                size_multiplier = 1.5
                print(f"   📊 Fear & Greed {fg_value} (Extreme Fear) -> 1.5x position")
            elif fg_value <= 40:
                size_multiplier = 1.25
                print(f"   📊 Fear & Greed {fg_value} (Fear) -> 1.25x position")

            trade_amount = min(self.config.daily_amount * size_multiplier, self.cash)

            # Execute buy if we have cash
            if self.cash >= trade_amount and trade_amount >= 1.0:
                current_price = best_data["price"]
                quantity = trade_amount / current_price

                # Record trade
                trade = Trade(
                    date=date_str,
                    symbol=best_symbol,
                    action="BUY",
                    price=current_price,
                    quantity=quantity,
                    amount=trade_amount,
                    reason=f"Price > MA50 AND RSI > 50 (FG: {fg_value})",
                    portfolio_value=self.cash,
                )
                self.trades.append(trade)

                # Update position
                if best_symbol not in self.positions:
                    self.positions[best_symbol] = {
                        "qty": 0,
                        "cost_basis": 0,
                        "entry_date": date_str,
                    }

                pos = self.positions[best_symbol]
                total_qty = pos["qty"] + quantity
                pos["cost_basis"] = (pos["cost_basis"] * pos["qty"] + current_price * quantity) / total_qty
                pos["qty"] = total_qty
                pos["entry_date"] = date_str

                self.cash -= trade_amount

                print(f"   🟢 BUY {quantity:.6f} {best_symbol} @ ${current_price:.2f}")

            # Track daily portfolio value
            portfolio_value = self._calculate_portfolio_value(date, price_data)
            self.daily_values.append((date_str, portfolio_value))

        # Close all positions at end of backtest
        self._close_all_positions(all_dates[-1], price_data, "Backtest complete")

        # Calculate metrics
        return self._calculate_metrics("Trend + Momentum Strategy", "v4.1")

    def _select_best_crypto(self, date: pd.Timestamp, price_data: dict) -> str | None:
        """Select crypto with highest 7-day momentum."""
        best_symbol = None
        best_momentum = -999

        for symbol in self.config.symbols:
            if date not in price_data[symbol].index:
                continue

            # Calculate 7-day momentum
            week_ago = date - timedelta(days=7)
            if week_ago not in price_data[symbol].index:
                continue

            current_price = float(price_data[symbol].loc[date, "Close"])
            price_week_ago = float(price_data[symbol].loc[week_ago, "Close"])
            momentum = ((current_price - price_week_ago) / price_week_ago) * 100

            if momentum > best_momentum:
                best_momentum = momentum
                best_symbol = symbol

        return best_symbol

    def _manage_positions_v3(self, date: pd.Timestamp, price_data: dict):
        """Manage positions for v3.0 (stop-loss/take-profit)."""
        for symbol in list(self.positions.keys()):
            if date not in price_data[symbol].index:
                continue

            pos = self.positions[symbol]
            if pos["qty"] <= 0:
                continue

            current_price = float(price_data[symbol].loc[date, "Close"])
            cost_basis = pos["cost_basis"]
            pl_pct = ((current_price - cost_basis) / cost_basis)

            # Check stop-loss (7%)
            if pl_pct <= -self.config.stop_loss_pct:
                self._close_position(date.strftime("%Y-%m-%d"), symbol, current_price, "Stop-loss")

            # Check take-profit (10%)
            elif pl_pct >= self.config.take_profit_pct:
                self._close_position(date.strftime("%Y-%m-%d"), symbol, current_price, "Take-profit")

    def _manage_positions_v4(self, date: pd.Timestamp, price_data: dict):
        """Manage positions for v4.1 (stop-loss/take-profit)."""
        # Same as v3 for now
        self._manage_positions_v3(date, price_data)

    def _close_position(self, date_str: str, symbol: str, price: float, reason: str):
        """Close a position."""
        pos = self.positions[symbol]
        if pos["qty"] <= 0:
            return

        amount = pos["qty"] * price
        pl = amount - (pos["qty"] * pos["cost_basis"])

        trade = Trade(
            date=date_str,
            symbol=symbol,
            action="SELL",
            price=price,
            quantity=pos["qty"],
            amount=amount,
            reason=reason,
            portfolio_value=self.cash + amount,
        )
        self.trades.append(trade)

        self.cash += amount
        print(f"   🔴 SELL {pos['qty']:.6f} {symbol} @ ${price:.2f} ({reason}, P/L: ${pl:.2f})")

        # Clear position
        self.positions[symbol] = {"qty": 0, "cost_basis": 0, "entry_date": date_str}

    def _close_all_positions(self, date_str: str, price_data: dict, reason: str):
        """Close all open positions at end of backtest."""
        date = pd.to_datetime(date_str)

        for symbol in list(self.positions.keys()):
            pos = self.positions[symbol]
            if pos["qty"] <= 0:
                continue

            if date not in price_data[symbol].index:
                # Use last available price
                last_date = price_data[symbol].index[-1]
                current_price = float(price_data[symbol].loc[last_date, "Close"])
            else:
                current_price = float(price_data[symbol].loc[date, "Close"])

            self._close_position(date_str, symbol, current_price, reason)

    def _calculate_portfolio_value(self, date: pd.Timestamp, price_data: dict) -> float:
        """Calculate total portfolio value (cash + positions)."""
        total = self.cash

        for symbol, pos in self.positions.items():
            if pos["qty"] <= 0:
                continue

            if date not in price_data[symbol].index:
                # Use last available price
                last_date = price_data[symbol].index[price_data[symbol].index <= date][-1]
                current_price = float(price_data[symbol].loc[last_date, "Close"])
            else:
                current_price = float(price_data[symbol].loc[date, "Close"])

            total += pos["qty"] * current_price

        return total

    def _calculate_metrics(self, strategy_name: str, version: str) -> BacktestResult:
        """Calculate performance metrics from backtest."""
        final_capital = self.cash

        # Total return
        total_return_pct = ((final_capital - self.config.initial_capital) / self.config.initial_capital) * 100

        # Max drawdown
        peak = self.config.initial_capital
        max_dd = 0
        for _, value in self.daily_values:
            if value > peak:
                peak = value
            dd = ((peak - value) / peak) * 100
            if dd > max_dd:
                max_dd = dd

        # Win rate (count profitable trades)
        buy_trades = [t for t in self.trades if t.action == "BUY"]
        sell_trades = [t for t in self.trades if t.action == "SELL"]

        # Match buys with sells
        profitable_trades = 0
        total_trade_pl = 0
        for sell in sell_trades:
            # Find corresponding buy (simple matching by symbol)
            buys = [t for t in buy_trades if t.symbol == sell.symbol and t.date <= sell.date]
            if buys:
                buy = buys[-1]  # Use most recent buy
                pl = (sell.price - buy.price) * sell.quantity
                total_trade_pl += pl
                if pl > 0:
                    profitable_trades += 1

        num_closed_trades = len(sell_trades)
        win_rate = (profitable_trades / num_closed_trades * 100) if num_closed_trades > 0 else 0
        avg_trade_pl = (total_trade_pl / num_closed_trades) if num_closed_trades > 0 else 0

        # Sharpe ratio
        if len(self.daily_values) > 1:
            values = [v for _, v in self.daily_values]
            returns = pd.Series(values).pct_change().dropna()
            if len(returns) > 0 and returns.std() > 0:
                sharpe = (returns.mean() / returns.std()) * np.sqrt(252)  # Annualized
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0

        return BacktestResult(
            strategy_name=strategy_name,
            strategy_version=version,
            initial_capital=self.config.initial_capital,
            final_capital=final_capital,
            total_return_pct=total_return_pct,
            max_drawdown_pct=max_dd,
            win_rate=win_rate,
            sharpe_ratio=sharpe,
            num_trades=len(buy_trades),
            avg_trade_pl=avg_trade_pl,
            trades=self.trades,
            daily_values=self.daily_values,
        )


def print_comparison_table(result_v3: BacktestResult, result_v4: BacktestResult):
    """Print comparison table of backtest results."""
    print("\n" + "=" * 100)
    print("📊 BACKTEST COMPARISON: v3.0 vs v4.1")
    print("=" * 100)

    # Build comparison table
    print(f"\n{'Metric':<30} {'v3.0 (Fear & Greed)':<25} {'v4.1 (Trend + Momentum)':<25} {'Winner':<15}")
    print("-" * 100)

    # Initial capital
    print(f"{'Initial Capital':<30} ${result_v3.initial_capital:>8,.2f}{' '*16} ${result_v4.initial_capital:>8,.2f}{' '*16} {'—':<15}")

    # Final capital
    v3_final = result_v3.final_capital
    v4_final = result_v4.final_capital
    winner = "v4.1 ✓" if v4_final > v3_final else "v3.0 ✓" if v3_final > v4_final else "Tie"
    print(f"{'Final Capital':<30} ${v3_final:>8,.2f}{' '*16} ${v4_final:>8,.2f}{' '*16} {winner:<15}")

    # Total return
    v3_ret = result_v3.total_return_pct
    v4_ret = result_v4.total_return_pct
    winner = "v4.1 ✓" if v4_ret > v3_ret else "v3.0 ✓" if v3_ret > v4_ret else "Tie"
    print(f"{'Total Return':<30} {v3_ret:>8.2f}%{' '*16} {v4_ret:>8.2f}%{' '*16} {winner:<15}")

    # Max drawdown (lower is better)
    v3_dd = result_v3.max_drawdown_pct
    v4_dd = result_v4.max_drawdown_pct
    winner = "v4.1 ✓" if v4_dd < v3_dd else "v3.0 ✓" if v3_dd < v4_dd else "Tie"
    print(f"{'Max Drawdown':<30} {v3_dd:>8.2f}%{' '*16} {v4_dd:>8.2f}%{' '*16} {winner:<15}")

    # Win rate
    v3_wr = result_v3.win_rate
    v4_wr = result_v4.win_rate
    winner = "v4.1 ✓" if v4_wr > v3_wr else "v3.0 ✓" if v3_wr > v4_wr else "Tie"
    print(f"{'Win Rate':<30} {v3_wr:>8.1f}%{' '*16} {v4_wr:>8.1f}%{' '*16} {winner:<15}")

    # Sharpe ratio
    v3_sharpe = result_v3.sharpe_ratio
    v4_sharpe = result_v4.sharpe_ratio
    winner = "v4.1 ✓" if v4_sharpe > v3_sharpe else "v3.0 ✓" if v3_sharpe > v4_sharpe else "Tie"
    print(f"{'Sharpe Ratio':<30} {v3_sharpe:>8.2f}{' '*16} {v4_sharpe:>8.2f}{' '*16} {winner:<15}")

    # Number of trades
    v3_trades = result_v3.num_trades
    v4_trades = result_v4.num_trades
    print(f"{'Number of Trades':<30} {v3_trades:>8}{' '*16} {v4_trades:>8}{' '*16} {'—':<15}")

    # Average trade P/L
    v3_avg = result_v3.avg_trade_pl
    v4_avg = result_v4.avg_trade_pl
    winner = "v4.1 ✓" if v4_avg > v3_avg else "v3.0 ✓" if v3_avg > v4_avg else "Tie"
    print(f"{'Avg Trade P/L':<30} ${v3_avg:>8.2f}{' '*16} ${v4_avg:>8.2f}{' '*16} {winner:<15}")

    print("-" * 100)

    # Overall winner
    v3_wins = sum(
        [
            v3_final > v4_final,
            v3_ret > v4_ret,
            v3_dd < v4_dd,
            v3_wr > v4_wr,
            v3_sharpe > v4_sharpe,
            v3_avg > v4_avg,
        ]
    )
    v4_wins = sum(
        [
            v4_final > v3_final,
            v4_ret > v3_ret,
            v4_dd < v3_dd,
            v4_wr > v3_wr,
            v4_sharpe > v3_sharpe,
            v4_avg > v3_avg,
        ]
    )

    print(f"\n{'OVERALL WINNER:':<30} v3.0 ({v3_wins} metrics){' '*8} v4.1 ({v4_wins} metrics){' '*8}", end="")
    if v4_wins > v3_wins:
        print("🏆 v4.1 WINS!")
    elif v3_wins > v4_wins:
        print("🏆 v3.0 WINS!")
    else:
        print("🤝 TIE!")

    print("=" * 100)


def save_results(result_v3: BacktestResult, result_v4: BacktestResult, output_dir: Path):
    """Save backtest results to JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save v3.0 results
    v3_file = output_dir / "backtest_v3.0_results.json"
    with open(v3_file, "w") as f:
        json.dump(
            {
                "strategy": result_v3.strategy_name,
                "version": result_v3.strategy_version,
                "initial_capital": result_v3.initial_capital,
                "final_capital": result_v3.final_capital,
                "total_return_pct": result_v3.total_return_pct,
                "max_drawdown_pct": result_v3.max_drawdown_pct,
                "win_rate": result_v3.win_rate,
                "sharpe_ratio": result_v3.sharpe_ratio,
                "num_trades": result_v3.num_trades,
                "avg_trade_pl": result_v3.avg_trade_pl,
                "trades": [
                    {
                        "date": t.date,
                        "symbol": t.symbol,
                        "action": t.action,
                        "price": t.price,
                        "quantity": t.quantity,
                        "amount": t.amount,
                        "reason": t.reason,
                    }
                    for t in result_v3.trades
                ],
            },
            f,
            indent=2,
        )

    # Save v4.1 results
    v4_file = output_dir / "backtest_v4.1_results.json"
    with open(v4_file, "w") as f:
        json.dump(
            {
                "strategy": result_v4.strategy_name,
                "version": result_v4.strategy_version,
                "initial_capital": result_v4.initial_capital,
                "final_capital": result_v4.final_capital,
                "total_return_pct": result_v4.total_return_pct,
                "max_drawdown_pct": result_v4.max_drawdown_pct,
                "win_rate": result_v4.win_rate,
                "sharpe_ratio": result_v4.sharpe_ratio,
                "num_trades": result_v4.num_trades,
                "avg_trade_pl": result_v4.avg_trade_pl,
                "trades": [
                    {
                        "date": t.date,
                        "symbol": t.symbol,
                        "action": t.action,
                        "price": t.price,
                        "quantity": t.quantity,
                        "amount": t.amount,
                        "reason": t.reason,
                    }
                    for t in result_v4.trades
                ],
            },
            f,
            indent=2,
        )

    print(f"\n💾 Results saved:")
    print(f"   - {v3_file}")
    print(f"   - {v4_file}")


def main():
    """Main entry point."""
    print("=" * 100)
    print("🚀 CRYPTO STRATEGY BACKTEST: v3.0 (Fear & Greed) vs v4.1 (Trend + Momentum)")
    print("=" * 100)

    # Configuration
    config = BacktestConfig(
        initial_capital=1000.0,
        daily_amount=25.0,
        lookback_days=90,
        stop_loss_pct=0.07,
        take_profit_pct=0.10,
    )

    print(f"\n⚙️  Configuration:")
    print(f"   - Initial Capital: ${config.initial_capital:,.2f}")
    print(f"   - Daily Amount: ${config.daily_amount:,.2f}")
    print(f"   - Lookback Period: {config.lookback_days} days")
    print(f"   - Stop Loss: {config.stop_loss_pct * 100:.0f}%")
    print(f"   - Take Profit: {config.take_profit_pct * 100:.0f}%")
    print(f"   - Symbols: {', '.join(config.symbols)}")

    # Create backtester
    backtester = CryptoBacktester(config)

    # Fetch data
    price_data = backtester.fetch_historical_data()
    if not price_data:
        print("❌ Failed to fetch price data. Exiting.")
        sys.exit(1)

    fear_greed = backtester.fetch_fear_greed_historical()

    # Run backtests
    result_v3 = backtester.backtest_v3(price_data, fear_greed)
    result_v4 = backtester.backtest_v4_1(price_data, fear_greed)

    # Print comparison
    print_comparison_table(result_v3, result_v4)

    # Save results
    output_dir = Path("data/backtests")
    save_results(result_v3, result_v4, output_dir)

    print("\n✅ Backtest complete!")


if __name__ == "__main__":
    main()
