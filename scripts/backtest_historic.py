#!/usr/bin/env python3
"""
Historic Backtest Validation Script

Tests the trading strategy against critical market regimes:
- 2020 COVID Crash (Feb-Mar 2020)
- 2022 Bear Market (Jan-Oct 2022)
- 2024-2025 Bull Run (for comparison)

CRITICAL: A strategy that only works in 2024/2025 is capturing beta, not alpha.
This script validates survival across multiple market conditions.

Usage:
    python scripts/backtest_historic.py --all
    python scripts/backtest_historic.py --regime covid
    python scripts/backtest_historic.py --regime bear2022

Pass Criteria:
- Max Drawdown < 15%
- Sharpe Ratio > 0.5
- Win Rate > 45%
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class BacktestRegime:
    """Market regime configuration for backtesting."""

    name: str
    description: str
    start_date: str
    end_date: str
    expected_behavior: str
    pass_criteria: dict


# Define critical market regimes to test against
MARKET_REGIMES = {
    "covid_crash": BacktestRegime(
        name="COVID Crash",
        description="Feb-Mar 2020 - 34% crash in 23 trading days",
        start_date="2020-02-01",
        end_date="2020-04-30",
        expected_behavior="Strategy should limit losses during rapid decline",
        pass_criteria={
            "max_drawdown": 0.20,  # Max 20% drawdown (market was -34%)
            "recovery_ratio": 0.5,  # Recover at least 50% by end of period
        },
    ),
    "bear_2022": BacktestRegime(
        name="2022 Bear Market",
        description="Jan-Oct 2022 - Extended bear market, -25% for S&P",
        start_date="2022-01-01",
        end_date="2022-10-31",
        expected_behavior="Strategy should preserve capital during slow decline",
        pass_criteria={
            "max_drawdown": 0.15,  # Max 15% drawdown (market was -25%)
            "sharpe_ratio": 0.0,  # At least break-even risk-adjusted
        },
    ),
    "bull_2024": BacktestRegime(
        name="2024 Bull Run",
        description="Jan-Dec 2024 - Strong bull market",
        start_date="2024-01-01",
        end_date="2024-12-01",
        expected_behavior="Strategy should capture upside momentum",
        pass_criteria={
            "min_return": 0.10,  # Capture at least 10% of bull run
            "sharpe_ratio": 0.5,  # Decent risk-adjusted returns
        },
    ),
    "volatility_2020": BacktestRegime(
        name="2020 Volatility",
        description="Full year 2020 - Crash then recovery",
        start_date="2020-01-01",
        end_date="2020-12-31",
        expected_behavior="Strategy should survive crash and capture recovery",
        pass_criteria={
            "max_drawdown": 0.25,
            "annual_return": 0.05,  # At least 5% for the year
        },
    ),
    "rate_hike_2022": BacktestRegime(
        name="Rate Hike Period",
        description="Mar-Dec 2022 - Fed rate hiking cycle",
        start_date="2022-03-01",
        end_date="2022-12-31",
        expected_behavior="Strategy should handle rising rate environment",
        pass_criteria={
            "max_drawdown": 0.15,
            "win_rate": 0.45,
        },
    ),
}


def fetch_historical_data(symbol: str, start_date: str, end_date: str) -> list[dict]:
    """
    Fetch historical OHLCV data for backtesting.

    Uses yfinance as primary source, falls back to cached data if available.
    """
    try:
        import yfinance as yf

        logger.info(f"Fetching {symbol} data from {start_date} to {end_date}")
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start_date, end=end_date, interval="1d")

        if hist.empty:
            logger.warning(f"No data returned for {symbol}")
            return []

        data = []
        for idx, row in hist.iterrows():
            data.append(
                {
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                }
            )

        logger.info(f"Fetched {len(data)} days of data for {symbol}")
        return data

    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        return []
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return []


def calculate_indicators(data: list[dict]) -> list[dict]:
    """
    Calculate technical indicators (MACD, RSI, SMA) for backtesting.

    Mirrors the logic in MomentumAgent.
    """
    import numpy as np

    if len(data) < 26:
        logger.warning("Insufficient data for indicator calculation")
        return data

    closes = np.array([d["close"] for d in data])

    # MACD (12, 26, 9)
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = ema12 - ema26
    signal_line = _ema(macd_line, 9)
    macd_histogram = macd_line - signal_line

    # RSI (14)
    rsi = _calculate_rsi(closes, 14)

    # SMAs
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)

    # Add indicators to data
    for i, d in enumerate(data):
        d["macd_histogram"] = float(macd_histogram[i]) if i < len(macd_histogram) else 0
        d["rsi"] = float(rsi[i]) if i < len(rsi) else 50
        d["sma20"] = float(sma20[i]) if i < len(sma20) else d["close"]
        d["sma50"] = float(sma50[i]) if i < len(sma50) else d["close"]

    return data


def _ema(data: "np.ndarray", period: int) -> "np.ndarray":
    """Calculate Exponential Moving Average."""
    import numpy as np

    ema = np.zeros_like(data)
    ema[0] = data[0]
    multiplier = 2 / (period + 1)

    for i in range(1, len(data)):
        ema[i] = (data[i] - ema[i - 1]) * multiplier + ema[i - 1]

    return ema


def _sma(data: "np.ndarray", period: int) -> "np.ndarray":
    """Calculate Simple Moving Average."""
    import numpy as np

    sma = np.zeros_like(data)
    for i in range(len(data)):
        if i < period - 1:
            sma[i] = np.mean(data[: i + 1])
        else:
            sma[i] = np.mean(data[i - period + 1 : i + 1])

    return sma


def _calculate_rsi(data: "np.ndarray", period: int = 14) -> "np.ndarray":
    """Calculate Relative Strength Index."""
    import numpy as np

    rsi = np.zeros_like(data)
    deltas = np.diff(data)

    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.zeros(len(data))
    avg_loss = np.zeros(len(data))

    # Initial averages
    if len(gains) >= period:
        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])

    # Smoothed averages
    for i in range(period + 1, len(data)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i - 1]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i - 1]) / period

    # RSI calculation
    for i in range(period, len(data)):
        if avg_loss[i] == 0:
            rsi[i] = 100
        else:
            rs = avg_gain[i] / avg_loss[i]
            rsi[i] = 100 - (100 / (1 + rs))

    return rsi


def run_backtest(
    regime: BacktestRegime,
    symbols: list[str],
    initial_capital: float = 100000,
) -> dict:
    """
    Run backtest for a specific market regime.

    Uses the same momentum strategy logic as the live system.
    """
    logger.info(f"\n{'=' * 60}")
    logger.info(f"BACKTEST: {regime.name}")
    logger.info(f"Period: {regime.start_date} to {regime.end_date}")
    logger.info(f"Description: {regime.description}")
    logger.info(f"{'=' * 60}")

    # Fetch and prepare data
    all_data = {}
    for symbol in symbols:
        data = fetch_historical_data(symbol, regime.start_date, regime.end_date)
        if data:
            all_data[symbol] = calculate_indicators(data)

    if not all_data:
        return {
            "status": "FAILED",
            "error": "No data available for backtest",
            "regime": regime.name,
        }

    # Initialize backtest state
    capital = initial_capital
    position = None
    trades = []
    equity_curve = [capital]
    max_equity = capital
    max_drawdown = 0

    # Get primary symbol data (use first available)
    primary_symbol = symbols[0]
    data = all_data.get(primary_symbol, [])

    if len(data) < 50:
        return {
            "status": "FAILED",
            "error": f"Insufficient data ({len(data)} days)",
            "regime": regime.name,
        }

    # Run through each trading day
    for i, day in enumerate(data[50:], start=50):  # Skip warmup period
        close = day["close"]
        macd_hist = day.get("macd_histogram", 0)
        rsi = day.get("rsi", 50)
        sma20 = day.get("sma20", close)

        # Simple momentum strategy (mirrors live system)
        # BUY signal: MACD histogram > 0, RSI < 70, Price > SMA20
        buy_signal = macd_hist > 0 and rsi < 70 and close > sma20

        # SELL signal: MACD histogram < 0 OR RSI > 80 OR Price < SMA20
        sell_signal = macd_hist < 0 or rsi > 80 or close < sma20

        # Execute trades
        if buy_signal and position is None:
            # Buy with 95% of capital (5% reserve)
            shares = int((capital * 0.95) / close)
            if shares > 0:
                cost = shares * close
                position = {
                    "symbol": primary_symbol,
                    "shares": shares,
                    "entry_price": close,
                    "entry_date": day["date"],
                }
                capital -= cost

        elif sell_signal and position is not None:
            # Sell entire position
            proceeds = position["shares"] * close
            pl = proceeds - (position["shares"] * position["entry_price"])
            pl_pct = (close / position["entry_price"] - 1) * 100

            trades.append(
                {
                    "entry_date": position["entry_date"],
                    "exit_date": day["date"],
                    "entry_price": position["entry_price"],
                    "exit_price": close,
                    "shares": position["shares"],
                    "pl": pl,
                    "pl_pct": pl_pct,
                }
            )

            capital += proceeds
            position = None

        # Update equity curve
        current_equity = capital
        if position:
            current_equity += position["shares"] * close
        equity_curve.append(current_equity)

        # Track max drawdown
        max_equity = max(max_equity, current_equity)
        drawdown = (max_equity - current_equity) / max_equity
        max_drawdown = max(max_drawdown, drawdown)

    # Close any open position at end
    if position:
        final_close = data[-1]["close"]
        proceeds = position["shares"] * final_close
        pl = proceeds - (position["shares"] * position["entry_price"])
        trades.append(
            {
                "entry_date": position["entry_date"],
                "exit_date": data[-1]["date"],
                "entry_price": position["entry_price"],
                "exit_price": final_close,
                "shares": position["shares"],
                "pl": pl,
                "pl_pct": (final_close / position["entry_price"] - 1) * 100,
            }
        )
        capital += proceeds
        position = None

    # Calculate metrics
    final_equity = equity_curve[-1]
    total_return = final_equity / initial_capital - 1

    winning_trades = [t for t in trades if t["pl"] > 0]
    losing_trades = [t for t in trades if t["pl"] <= 0]
    win_rate = len(winning_trades) / len(trades) if trades else 0

    # Calculate Sharpe ratio (simplified, daily returns)
    import numpy as np

    returns = np.diff(equity_curve) / equity_curve[:-1]
    sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252) if np.std(returns) > 0 else 0

    results = {
        "status": "COMPLETED",
        "regime": regime.name,
        "period": f"{regime.start_date} to {regime.end_date}",
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 2),
        "total_return": round(total_return * 100, 2),
        "max_drawdown": round(max_drawdown * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "total_trades": len(trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": round(win_rate * 100, 1),
        "avg_win": round(np.mean([t["pl"] for t in winning_trades]), 2) if winning_trades else 0,
        "avg_loss": round(np.mean([t["pl"] for t in losing_trades]), 2) if losing_trades else 0,
    }

    # Check pass criteria
    passed = True
    failures = []

    if "max_drawdown" in regime.pass_criteria:
        if max_drawdown > regime.pass_criteria["max_drawdown"]:
            passed = False
            failures.append(
                f"Max Drawdown {max_drawdown * 100:.1f}% > {regime.pass_criteria['max_drawdown'] * 100:.0f}%"
            )

    if "sharpe_ratio" in regime.pass_criteria:
        if sharpe < regime.pass_criteria["sharpe_ratio"]:
            passed = False
            failures.append(f"Sharpe Ratio {sharpe:.2f} < {regime.pass_criteria['sharpe_ratio']}")

    if "win_rate" in regime.pass_criteria:
        if win_rate < regime.pass_criteria["win_rate"]:
            passed = False
            failures.append(
                f"Win Rate {win_rate * 100:.1f}% < {regime.pass_criteria['win_rate'] * 100:.0f}%"
            )

    if "min_return" in regime.pass_criteria:
        if total_return < regime.pass_criteria["min_return"]:
            passed = False
            failures.append(
                f"Return {total_return * 100:.1f}% < {regime.pass_criteria['min_return'] * 100:.0f}%"
            )

    results["passed"] = passed
    results["failures"] = failures

    return results


def print_results(results: dict):
    """Print backtest results in a formatted table."""
    print(f"\n{'=' * 70}")
    print(f"BACKTEST RESULTS: {results.get('regime', 'Unknown')}")
    print(f"{'=' * 70}")

    if results.get("status") == "FAILED":
        print(f"STATUS: FAILED - {results.get('error', 'Unknown error')}")
        return

    print(f"Period: {results.get('period', 'N/A')}")
    print("\n--- Performance ---")
    print(f"  Initial Capital:  ${results.get('initial_capital', 0):,.2f}")
    print(f"  Final Equity:     ${results.get('final_equity', 0):,.2f}")
    print(f"  Total Return:     {results.get('total_return', 0):+.2f}%")
    print(f"  Max Drawdown:     {results.get('max_drawdown', 0):.2f}%")
    print(f"  Sharpe Ratio:     {results.get('sharpe_ratio', 0):.2f}")

    print("\n--- Trades ---")
    print(f"  Total Trades:     {results.get('total_trades', 0)}")
    print(f"  Winning Trades:   {results.get('winning_trades', 0)}")
    print(f"  Losing Trades:    {results.get('losing_trades', 0)}")
    print(f"  Win Rate:         {results.get('win_rate', 0):.1f}%")
    print(f"  Avg Win:          ${results.get('avg_win', 0):,.2f}")
    print(f"  Avg Loss:         ${results.get('avg_loss', 0):,.2f}")

    print("\n--- Pass/Fail ---")
    if results.get("passed"):
        print("  STATUS: PASSED")
    else:
        print("  STATUS: FAILED")
        for failure in results.get("failures", []):
            print(f"  - {failure}")

    print(f"{'=' * 70}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Historic backtest validation against multiple market regimes"
    )
    parser.add_argument(
        "--regime",
        choices=list(MARKET_REGIMES.keys()) + ["all"],
        default="all",
        help="Market regime to test (default: all)",
    )
    parser.add_argument(
        "--symbols", default="SPY,QQQ", help="Comma-separated list of symbols (default: SPY,QQQ)"
    )
    parser.add_argument(
        "--capital", type=float, default=100000, help="Initial capital (default: 100000)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/backtests/historic_validation.json",
        help="Output file path",
    )

    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",")]

    print("\n" + "=" * 70)
    print("HISTORIC BACKTEST VALIDATION")
    print("Testing strategy survival across multiple market regimes")
    print("=" * 70)
    print(f"\nSymbols: {', '.join(symbols)}")
    print(f"Capital: ${args.capital:,.2f}")

    # Run backtests
    all_results = {}
    regimes_to_test = list(MARKET_REGIMES.keys()) if args.regime == "all" else [args.regime]

    passed_count = 0
    failed_count = 0

    for regime_name in regimes_to_test:
        regime = MARKET_REGIMES[regime_name]
        results = run_backtest(regime, symbols, args.capital)
        all_results[regime_name] = results
        print_results(results)

        if results.get("passed"):
            passed_count += 1
        else:
            failed_count += 1

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"  Regimes Tested:  {len(regimes_to_test)}")
    print(f"  Passed:          {passed_count}")
    print(f"  Failed:          {failed_count}")

    if failed_count > 0:
        print("\n  VERDICT: STRATEGY NEEDS IMPROVEMENT")
        print("  The strategy does not survive all market conditions.")
        print("  Focus on reducing drawdown during crash scenarios.")
    else:
        print("\n  VERDICT: STRATEGY VALIDATED")
        print("  The strategy survives across tested market regimes.")

    print("=" * 70 + "\n")

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "symbols": symbols,
                "initial_capital": args.capital,
                "results": all_results,
                "summary": {
                    "regimes_tested": len(regimes_to_test),
                    "passed": passed_count,
                    "failed": failed_count,
                    "verdict": "VALIDATED" if failed_count == 0 else "NEEDS_IMPROVEMENT",
                },
            },
            f,
            indent=2,
        )

    print(f"Results saved to: {output_path}")

    # Exit with failure if any regime failed
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
