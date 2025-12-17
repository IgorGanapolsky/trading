#!/usr/bin/env python3
"""
HONEST EDGE TEST - Strip away all complexity and find if ANY edge exists.

This script tests pure MACD crossover with ZERO:
- No RL gates
- No sentiment analysis
- No LLM councils
- No complex filters

If this loses money, the base signal is broken.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.technical_indicators import calculate_macd


def fetch_prices(symbol: str, days: int = 365) -> pd.DataFrame:
    """Fetch historical prices from yfinance."""
    end = datetime.now()
    start = end - timedelta(days=days)

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, end=end)

    if df.empty:
        raise ValueError(f"No data for {symbol}")

    return df


def run_pure_macd_backtest(
    symbol: str,
    initial_capital: float = 10000.0,
    position_size_pct: float = 0.10,  # 10% per trade
    days: int = 365,
) -> dict:
    """
    Pure MACD crossover strategy:
    - BUY when MACD histogram goes positive (MACD crosses above signal)
    - SELL when MACD histogram goes negative (MACD crosses below signal)

    No other filters. No complexity. Just the signal.
    """
    print(f"\n{'='*60}")
    print(f"HONEST EDGE TEST: {symbol}")
    print(f"{'='*60}")

    # Fetch data
    df = fetch_prices(symbol, days)
    prices = df['Close']
    print(f"Data: {len(prices)} days from {prices.index[0].date()} to {prices.index[-1].date()}")

    # Need at least 35 days for MACD (26 slow + 9 signal)
    if len(prices) < 35:
        raise ValueError("Not enough data for MACD calculation")

    # Initialize
    capital = initial_capital
    position = 0  # shares held
    entry_price = 0.0

    trades = []
    equity_curve = []

    prev_histogram = None

    # Walk through each day starting from day 35
    for i in range(35, len(prices)):
        current_price = prices.iloc[i]
        price_series = prices.iloc[:i+1]

        # Calculate MACD
        macd_val, signal_line, histogram = calculate_macd(price_series)

        # Track equity
        equity = capital + (position * current_price)
        equity_curve.append({
            'date': prices.index[i],
            'equity': equity,
            'price': current_price,
            'macd': macd_val,
            'signal': signal_line,
            'histogram': histogram,
        })

        # Trading logic - pure MACD crossover
        if prev_histogram is not None:
            # BUY signal: histogram crosses from negative to positive
            if prev_histogram <= 0 and histogram > 0 and position == 0:
                shares_to_buy = int((capital * position_size_pct) / current_price)
                if shares_to_buy > 0:
                    cost = shares_to_buy * current_price
                    capital -= cost
                    position = shares_to_buy
                    entry_price = current_price
                    trades.append({
                        'date': prices.index[i],
                        'action': 'BUY',
                        'price': current_price,
                        'shares': shares_to_buy,
                        'histogram': histogram,
                    })

            # SELL signal: histogram crosses from positive to negative
            elif prev_histogram >= 0 and histogram < 0 and position > 0:
                proceeds = position * current_price
                pnl = (current_price - entry_price) * position
                pnl_pct = (current_price - entry_price) / entry_price * 100
                capital += proceeds
                trades.append({
                    'date': prices.index[i],
                    'action': 'SELL',
                    'price': current_price,
                    'shares': position,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'histogram': histogram,
                })
                position = 0
                entry_price = 0.0

        prev_histogram = histogram

    # Close any open position at end
    if position > 0:
        final_price = prices.iloc[-1]
        proceeds = position * final_price
        pnl = (final_price - entry_price) * position
        pnl_pct = (final_price - entry_price) / entry_price * 100
        capital += proceeds
        trades.append({
            'date': prices.index[-1],
            'action': 'SELL (END)',
            'price': final_price,
            'shares': position,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
        })
        position = 0

    # Calculate metrics
    final_equity = capital
    total_return = (final_equity - initial_capital) / initial_capital * 100

    # Buy and hold comparison
    buy_hold_shares = int(initial_capital / prices.iloc[35])
    buy_hold_final = buy_hold_shares * prices.iloc[-1]
    buy_hold_return = (buy_hold_final - initial_capital) / initial_capital * 100

    # Win/loss stats
    sell_trades = [t for t in trades if t['action'].startswith('SELL')]
    wins = [t for t in sell_trades if t.get('pnl', 0) > 0]
    losses = [t for t in sell_trades if t.get('pnl', 0) <= 0]
    win_rate = len(wins) / len(sell_trades) * 100 if sell_trades else 0

    # Max drawdown
    equity_values = [e['equity'] for e in equity_curve]
    peak = equity_values[0]
    max_dd = 0
    for eq in equity_values:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # Sharpe ratio (simplified - daily returns)
    if len(equity_curve) > 1:
        returns = pd.Series([
            (equity_curve[i]['equity'] - equity_curve[i-1]['equity']) / equity_curve[i-1]['equity']
            for i in range(1, len(equity_curve))
        ])
        sharpe = (returns.mean() / returns.std()) * (252 ** 0.5) if returns.std() > 0 else 0
    else:
        sharpe = 0

    results = {
        'symbol': symbol,
        'initial_capital': initial_capital,
        'final_equity': final_equity,
        'total_return_pct': total_return,
        'buy_hold_return_pct': buy_hold_return,
        'alpha_vs_hold': total_return - buy_hold_return,
        'total_trades': len(sell_trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate_pct': win_rate,
        'max_drawdown_pct': max_dd,
        'sharpe_ratio': sharpe,
        'trades': trades,
        'equity_curve': equity_curve,
    }

    return results


def print_results(results: dict) -> None:
    """Print formatted results."""
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")

    print("\n📊 PERFORMANCE:")
    print(f"   Initial:      ${results['initial_capital']:,.2f}")
    print(f"   Final:        ${results['final_equity']:,.2f}")
    print(f"   Return:       {results['total_return_pct']:+.2f}%")
    print(f"   Buy & Hold:   {results['buy_hold_return_pct']:+.2f}%")
    print(f"   Alpha:        {results['alpha_vs_hold']:+.2f}% {'✅' if results['alpha_vs_hold'] > 0 else '❌'}")

    print("\n📈 TRADE STATS:")
    print(f"   Total Trades: {results['total_trades']}")
    print(f"   Wins:         {results['wins']}")
    print(f"   Losses:       {results['losses']}")
    print(f"   Win Rate:     {results['win_rate_pct']:.1f}%")

    print("\n⚠️  RISK:")
    print(f"   Max Drawdown: {results['max_drawdown_pct']:.2f}%")
    print(f"   Sharpe Ratio: {results['sharpe_ratio']:.2f}")

    # Verdict
    print(f"\n{'='*60}")
    if results['alpha_vs_hold'] > 0 and results['sharpe_ratio'] > 0.5:
        print("✅ EDGE EXISTS - Strategy beats buy & hold with acceptable risk")
    elif results['total_return_pct'] > 0:
        print("⚠️  MARGINAL - Profitable but doesn't beat buy & hold")
    else:
        print("❌ NO EDGE - Strategy loses money. Base signal is broken.")
    print(f"{'='*60}")

    # Show trades
    print("\n📝 TRADE LOG:")
    for t in results['trades']:
        action = t['action']
        if 'pnl' in t:
            pnl_str = f"P/L: ${t['pnl']:+.2f} ({t['pnl_pct']:+.1f}%)"
        else:
            pnl_str = ""
        print(f"   {t['date'].date()} | {action:10} | ${t['price']:.2f} x {t['shares']} | {pnl_str}")


def main():
    """Run honest edge tests on multiple assets."""

    print("\n" + "="*60)
    print("🔬 HONEST EDGE TEST - Finding if ANY edge exists")
    print("="*60)
    print("\nStrategy: Pure MACD crossover (12/26/9)")
    print("Rules:    BUY when histogram > 0, SELL when histogram < 0")
    print("Filters:  NONE (no RL, no sentiment, no gates)")
    print("="*60)

    # Test multiple assets
    test_assets = [
        ("SPY", 365),      # S&P 500 ETF - 1 year
        ("QQQ", 365),      # Nasdaq ETF - 1 year
        ("ETH-USD", 365),  # Ethereum - 1 year (24/7 market)
    ]

    all_results = []

    for symbol, days in test_assets:
        try:
            results = run_pure_macd_backtest(
                symbol=symbol,
                initial_capital=10000.0,
                position_size_pct=0.10,
                days=days,
            )
            print_results(results)
            all_results.append(results)
        except Exception as e:
            print(f"\n❌ Error testing {symbol}: {e}")

    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY - DOES ANY EDGE EXIST?")
    print("="*60)

    print(f"\n{'Symbol':<10} {'Return':>10} {'vs Hold':>10} {'Win Rate':>10} {'Sharpe':>10} {'Verdict':>10}")
    print("-" * 60)

    any_edge = False
    for r in all_results:
        verdict = "✅ EDGE" if r['alpha_vs_hold'] > 0 and r['sharpe_ratio'] > 0.5 else "❌ NONE"
        if verdict == "✅ EDGE":
            any_edge = True
        print(f"{r['symbol']:<10} {r['total_return_pct']:>+9.1f}% {r['alpha_vs_hold']:>+9.1f}% {r['win_rate_pct']:>9.1f}% {r['sharpe_ratio']:>10.2f} {verdict:>10}")

    print("\n" + "="*60)
    if any_edge:
        print("✅ EDGE FOUND - At least one asset shows profitable alpha")
        print("   → Focus strategy on winning assets")
    else:
        print("❌ NO EDGE FOUND - Pure MACD crossover has no alpha")
        print("   → Need different signal or parameters")
    print("="*60 + "\n")

    return all_results


if __name__ == "__main__":
    results = main()
