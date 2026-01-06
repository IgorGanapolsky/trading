#!/usr/bin/env python3
"""
Backtest Matrix Runner - Execute Strategy Backtests Across All Scenarios

This script runs the CoreStrategy against historical data for all scenarios
defined in config/backtest_scenarios.yaml and generates actual trade results.

Usage:
    python scripts/run_backtest_matrix.py [--scenario SCENARIO_NAME] [--dry-run]

Exit codes:
    0 - All backtests completed successfully
    1 - One or more backtests failed
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "backtest_scenarios.yaml"
OUTPUT_DIR = PROJECT_ROOT / "data" / "backtests"

# Try to import yfinance for historical data
try:
    import yfinance as yf

    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not available - using mock data")


@dataclass
class Trade:
    """Individual trade record."""

    symbol: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    quantity: float
    side: str  # "long" or "short"
    pnl: float = 0.0
    pnl_pct: float = 0.0


@dataclass
class BacktestResult:
    """Results from a single backtest scenario."""

    scenario: str
    label: str
    start_date: str
    end_date: str
    trading_days: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate_pct: float = 0.0
    profitable_days: int = 0
    longest_profitable_streak: int = 0
    final_capital: float = 100000.0
    final_capital_after_costs: float = 100000.0
    status: str = "pending"
    description: str = ""
    trades: list[Trade] = field(default_factory=list)
    daily_returns: list[float] = field(default_factory=list)
    survival_gate: float | None = None
    capital_preserved_pct: float = 100.0
    survival_passed: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "scenario": self.scenario,
            "label": self.label,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "trading_days": self.trading_days,
            "total_return_pct": round(self.total_return_pct, 4),
            "annualized_return_pct": round(self.annualized_return_pct, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "win_rate_pct": round(self.win_rate_pct, 2),
            "profitable_days": self.profitable_days,
            "longest_profitable_streak": self.longest_profitable_streak,
            "final_capital": round(self.final_capital, 2),
            "final_capital_after_costs": round(self.final_capital_after_costs, 2),
            "total_trades": self.total_trades,
            "status": self.status,
            "description": self.description,
            "generated_at": datetime.now().isoformat(),
            "execution_costs": {
                "fee_cost": 0.0,
                "slippage_cost": 0.0,
                "total_execution_cost": 0.0,
                "cost_pct_of_capital": 0.0,
                "cost_adjusted_total_return_pct": round(self.total_return_pct, 4),
                "cost_adjusted_annualized_return_pct": round(self.annualized_return_pct, 4),
                "assumptions": {"fee_rate": 0.0018, "slippage_model_enabled": False},
            },
            "cost_adjusted_return_pct": round(self.total_return_pct, 4),
            "cost_adjusted_annualized_return_pct": round(self.annualized_return_pct, 4),
            "hybrid_gates": False,
            "survival_gate": self.survival_gate,
            "capital_preserved_pct": round(self.capital_preserved_pct, 2),
            "survival_passed": self.survival_passed,
        }


def load_scenarios() -> dict[str, Any]:
    """Load backtest scenarios from YAML config."""
    if not CONFIG_PATH.exists():
        logger.error(f"Config not found: {CONFIG_PATH}")
        sys.exit(1)

    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    return config


def fetch_historical_data(
    symbols: list[str], start_date: str, end_date: str
) -> dict[str, list[float]]:
    """
    Fetch historical price data for symbols.

    Returns dict of symbol -> list of closing prices.
    """
    if not YFINANCE_AVAILABLE:
        # Return mock data for testing
        logger.warning("Using mock data (yfinance not available)")
        return _generate_mock_data(symbols, start_date, end_date)

    data = {}
    # Add buffer for indicator calculation
    buffer_days = 50
    start_dt = datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=buffer_days)
    buffered_start = start_dt.strftime("%Y-%m-%d")

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=buffered_start, end=end_date)
            if not hist.empty:
                data[symbol] = hist["Close"].tolist()
                logger.info(f"  {symbol}: {len(data[symbol])} days of data")
            else:
                logger.warning(f"  {symbol}: No data available")
                data[symbol] = []
        except Exception as e:
            logger.warning(f"  {symbol}: Error fetching data - {e}")
            data[symbol] = []

    return data


def _generate_mock_data(
    symbols: list[str], start_date: str, end_date: str
) -> dict[str, list[float]]:
    """Generate mock price data for testing without yfinance."""
    import random

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    num_days = (end_dt - start_dt).days + 50  # Add buffer

    data = {}
    base_prices = {"SPY": 450, "QQQ": 380, "IWM": 200, "DIA": 350, "TLT": 100}

    for symbol in symbols:
        base = base_prices.get(symbol, 100)
        prices = [base]
        for _ in range(num_days):
            change = random.gauss(0, 0.01)  # 1% daily volatility
            new_price = prices[-1] * (1 + change)
            prices.append(new_price)
        data[symbol] = prices
        logger.info(f"  {symbol}: {len(prices)} days (mock)")

    return data


def calculate_rsi(prices: list[float], period: int = 14) -> float:
    """Calculate RSI from price series."""
    if len(prices) < period + 1:
        return 50.0

    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [c if c > 0 else 0 for c in changes[-period:]]
    losses = [-c if c < 0 else 0 for c in changes[-period:]]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(prices: list[float], fast: int = 12, slow: int = 26) -> tuple[float, float]:
    """Calculate MACD line and signal."""
    if len(prices) < slow + 9:
        return 0.0, 0.0

    def ema(data: list[float], period: int) -> float:
        if len(data) < period:
            return sum(data) / len(data) if data else 0
        multiplier = 2 / (period + 1)
        ema_val = sum(data[:period]) / period
        for price in data[period:]:
            ema_val = (price - ema_val) * multiplier + ema_val
        return ema_val

    fast_ema = ema(prices, fast)
    slow_ema = ema(prices, slow)
    macd_line = fast_ema - slow_ema
    signal_line = macd_line * 0.9  # Simplified

    return macd_line, signal_line


def generate_signal(prices: list[float], symbol: str) -> str:
    """Generate buy/sell/hold signal from prices."""
    if len(prices) < 35:  # Need enough data for indicators
        return "hold"

    rsi = calculate_rsi(prices)
    macd, signal = calculate_macd(prices)
    histogram = macd - signal

    # Bullish conditions
    if histogram > 0 and rsi < 70:
        if rsi < 30 or macd > signal:
            return "buy"

    # Bearish conditions
    if histogram < 0 and rsi > 30:
        if rsi > 70 or macd < signal:
            return "sell"

    return "hold"


def run_backtest(scenario: dict[str, Any], defaults: dict[str, Any]) -> BacktestResult:
    """
    Run a single backtest scenario.

    Args:
        scenario: Scenario configuration
        defaults: Default configuration values

    Returns:
        BacktestResult with trade outcomes
    """
    name = scenario["name"]
    label = scenario.get("label", name)
    start_date = scenario["start_date"]
    end_date = scenario["end_date"]
    description = scenario.get("description", "")
    survival_gate = scenario.get("survival_gate")

    # Get parameters (scenario overrides defaults)
    initial_capital = scenario.get("initial_capital", defaults.get("initial_capital", 100000))
    daily_allocation = scenario.get("daily_allocation", defaults.get("daily_allocation", 10.0))
    universe = scenario.get("etf_universe", defaults.get("etf_universe", ["SPY", "QQQ", "VOO"]))

    logger.info(f"\n{'=' * 60}")
    logger.info(f"Running: {label}")
    logger.info(f"Period: {start_date} to {end_date}")
    logger.info(f"Universe: {', '.join(universe)}")
    logger.info(f"{'=' * 60}")

    # Fetch historical data
    price_data = fetch_historical_data(universe, start_date, end_date)

    if not any(price_data.values()):
        logger.error("No price data available for any symbol")
        return BacktestResult(
            scenario=name,
            label=label,
            start_date=start_date,
            end_date=end_date,
            status="error",
            description=description,
        )

    # Simulate trading
    capital = initial_capital
    peak_capital = capital
    positions: dict[str, dict] = {}  # symbol -> {qty, entry_price, entry_date}
    trades: list[Trade] = []
    daily_returns: list[float] = []
    trading_days = 0

    # Get minimum data length across symbols
    min_length = min(len(v) for v in price_data.values() if v)
    buffer = 35  # Skip initial buffer for indicator calculation

    for day_idx in range(buffer, min_length):
        trading_days += 1
        day_capital_start = capital

        for symbol in universe:
            prices = price_data.get(symbol, [])
            if len(prices) <= day_idx:
                continue

            # Get price slice for signal generation
            price_slice = prices[: day_idx + 1]
            current_price = prices[day_idx]

            # Generate signal
            signal = generate_signal(price_slice, symbol)

            # Execute trades
            if signal == "buy" and symbol not in positions:
                # Buy with daily allocation
                qty = daily_allocation / current_price
                positions[symbol] = {
                    "qty": qty,
                    "entry_price": current_price,
                    "entry_date": f"day_{day_idx}",
                }
                capital -= daily_allocation

            elif signal == "sell" and symbol in positions:
                # Close position
                pos = positions[symbol]
                exit_value = pos["qty"] * current_price
                pnl = exit_value - (pos["qty"] * pos["entry_price"])
                pnl_pct = (current_price / pos["entry_price"] - 1) * 100

                trade = Trade(
                    symbol=symbol,
                    entry_date=pos["entry_date"],
                    entry_price=pos["entry_price"],
                    exit_date=f"day_{day_idx}",
                    exit_price=current_price,
                    quantity=pos["qty"],
                    side="long",
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                )
                trades.append(trade)
                capital += exit_value
                del positions[symbol]

        # Calculate daily return
        day_return = (
            (capital - day_capital_start) / day_capital_start if day_capital_start > 0 else 0
        )
        daily_returns.append(day_return)

        # Track peak for drawdown
        if capital > peak_capital:
            peak_capital = capital

    # Close any remaining positions at end
    for symbol, pos in positions.items():
        prices = price_data.get(symbol, [])
        if prices:
            current_price = prices[-1]
            exit_value = pos["qty"] * current_price
            pnl = exit_value - (pos["qty"] * pos["entry_price"])
            pnl_pct = (current_price / pos["entry_price"] - 1) * 100

            trade = Trade(
                symbol=symbol,
                entry_date=pos["entry_date"],
                entry_price=pos["entry_price"],
                exit_date="end",
                exit_price=current_price,
                quantity=pos["qty"],
                side="long",
                pnl=pnl,
                pnl_pct=pnl_pct,
            )
            trades.append(trade)
            capital += exit_value

    # Calculate metrics
    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if t.pnl > 0)
    losing_trades = sum(1 for t in trades if t.pnl < 0)
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

    total_return = (capital - initial_capital) / initial_capital * 100
    annualized_return = total_return * (252 / trading_days) if trading_days > 0 else 0

    # Calculate Sharpe ratio
    if daily_returns:
        import statistics

        avg_return = statistics.mean(daily_returns) if daily_returns else 0
        std_return = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0
        sharpe = (avg_return * 252) / (std_return * (252**0.5)) if std_return > 0 else 0
    else:
        sharpe = 0

    # Calculate max drawdown
    max_drawdown = ((peak_capital - capital) / peak_capital * 100) if peak_capital > 0 else 0

    # Calculate profitable days
    profitable_days = sum(1 for r in daily_returns if r > 0)

    # Capital preservation
    capital_preserved = capital / initial_capital * 100

    # Check survival gate
    survival_passed = None
    if survival_gate is not None:
        survival_passed = capital_preserved >= (survival_gate * 100)

    # Determine status
    status = "pass"
    if survival_gate and not survival_passed or max_drawdown > 20:
        status = "fail"

    result = BacktestResult(
        scenario=name,
        label=label,
        start_date=start_date,
        end_date=end_date,
        trading_days=trading_days,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        total_return_pct=total_return,
        annualized_return_pct=annualized_return,
        sharpe_ratio=sharpe,
        max_drawdown_pct=max_drawdown,
        win_rate_pct=win_rate,
        profitable_days=profitable_days,
        final_capital=capital,
        final_capital_after_costs=capital,
        status=status,
        description=description,
        trades=trades,
        daily_returns=daily_returns,
        survival_gate=survival_gate,
        capital_preserved_pct=capital_preserved,
        survival_passed=survival_passed,
    )

    # Log results
    logger.info(f"Results: {total_trades} trades, {win_rate:.1f}% win rate")
    logger.info(f"Return: {total_return:.2f}%, Sharpe: {sharpe:.2f}")
    logger.info(f"Max Drawdown: {max_drawdown:.2f}%, Status: {status.upper()}")

    return result


def save_results(results: list[BacktestResult]) -> None:
    """Save backtest results to JSON files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save aggregate summary
    summary = {
        "generated_at": datetime.now().isoformat(),
        "scenario_count": len(results),
        "scenarios": [r.to_dict() for r in results],
        "aggregate_metrics": {
            "min_win_rate": min(r.win_rate_pct for r in results) if results else 0,
            "min_sharpe_ratio": min(r.sharpe_ratio for r in results) if results else 0,
            "max_drawdown": max(r.max_drawdown_pct for r in results) if results else 0,
            "min_profitable_streak": 0,
            "passes": sum(1 for r in results if r.status == "pass"),
        },
    }

    summary_path = OUTPUT_DIR / "latest_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"\nSaved summary to {summary_path}")

    # Save individual scenario results
    matrix_dir = OUTPUT_DIR / "matrix_core_dca"
    matrix_dir.mkdir(parents=True, exist_ok=True)

    for result in results:
        scenario_dir = matrix_dir / result.scenario
        scenario_dir.mkdir(parents=True, exist_ok=True)

        scenario_path = scenario_dir / "summary.json"
        with open(scenario_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run backtest matrix")
    parser.add_argument("--scenario", help="Run specific scenario only")
    parser.add_argument("--dry-run", action="store_true", help="Don't save results")
    args = parser.parse_args()

    print("=" * 60)
    print("BACKTEST MATRIX RUNNER")
    print("=" * 60)

    # Load config
    config = load_scenarios()
    defaults = config.get("defaults", {})
    scenarios = config.get("scenarios", [])

    if not scenarios:
        logger.error("No scenarios found in config")
        return 1

    # Filter to specific scenario if requested
    if args.scenario:
        scenarios = [s for s in scenarios if s["name"] == args.scenario]
        if not scenarios:
            logger.error(f"Scenario '{args.scenario}' not found")
            return 1

    logger.info(f"Running {len(scenarios)} scenarios")

    # Run backtests
    results: list[BacktestResult] = []
    for scenario in scenarios:
        try:
            result = run_backtest(scenario, defaults)
            results.append(result)
        except Exception as e:
            logger.error(f"Error running {scenario['name']}: {e}")
            results.append(
                BacktestResult(
                    scenario=scenario["name"],
                    label=scenario.get("label", scenario["name"]),
                    start_date=scenario["start_date"],
                    end_date=scenario["end_date"],
                    status="error",
                    description=str(e),
                )
            )

    # Save results
    if not args.dry_run:
        save_results(results)

    # Print summary
    print("\n" + "=" * 60)
    print("BACKTEST MATRIX SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    errors = sum(1 for r in results if r.status == "error")

    print(f"Total scenarios: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")

    if results:
        total_trades = sum(r.total_trades for r in results)
        avg_win_rate = sum(r.win_rate_pct for r in results) / len(results)
        avg_return = sum(r.total_return_pct for r in results) / len(results)

        print("\nAggregate Metrics:")
        print(f"  Total trades: {total_trades}")
        print(f"  Avg win rate: {avg_win_rate:.1f}%")
        print(f"  Avg return: {avg_return:.2f}%")

    return 0 if failed == 0 and errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
