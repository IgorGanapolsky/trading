#!/usr/bin/env python3
"""
Options Backtest - Comprehensive Strategy Analysis

This script demonstrates the world-class options backtesting engine with
multiple strategy examples:

Strategies Tested:
1. Covered Calls (0.30 delta, 30-45 DTE)
2. Iron Condors (0.16 delta wings, 45 DTE)
3. Credit Spreads (Put spreads, 0.20 delta, 45 DTE)
4. Cash-Secured Puts (0.30 delta, 30 DTE)

Features:
- Full Black-Scholes pricing with Greeks
- Realistic commission modeling
- Comprehensive performance metrics
- Strategy comparison and optimization

Usage:
    python scripts/run_options_backtest.py
    python scripts/run_options_backtest.py --strategy covered_call
    python scripts/run_options_backtest.py --start 2024-01-01 --end 2024-12-31
"""

import json
import logging
import sys
from argparse import ArgumentParser
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.backtesting.options_backtest import (
    OptionType,
    OptionsBacktestEngine,
    OptionsLeg,
    OptionsPosition,
    StrategyType,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ==============================================================================
# STRATEGY IMPLEMENTATIONS
# ==============================================================================


def covered_call_strategy(symbol: str, date: datetime, hist: pd.DataFrame) -> OptionsPosition | None:
    """
    Covered Call Strategy: Sell OTM calls against stock holdings.

    Target Parameters:
    - Delta: 0.30 (30% probability of assignment)
    - DTE: 30-45 days
    - Strike: 5-10% OTM

    Args:
        symbol: Underlying symbol
        date: Current date
        hist: Historical data up to current date

    Returns:
        OptionsPosition or None
    """
    # Only trade on specific days to avoid overlap
    if date.day not in [1, 15]:
        return None

    current_price = float(hist['Close'].iloc[-1])
    iv = float(hist['IV_Est'].iloc[-1])

    if pd.isna(iv) or iv <= 0:
        iv = 0.20  # Default IV

    # Target 35 DTE
    dte = 35
    expiration = date + timedelta(days=dte)

    # 5% OTM strike for ~0.30 delta
    strike = current_price * 1.05

    # Estimate premium using Black-Scholes
    from src.backtesting.options_backtest import BlackScholesPricer

    pricer = BlackScholesPricer()
    result = pricer.calculate(
        spot=current_price,
        strike=strike,
        time_to_expiry=dte / 365.0,
        risk_free_rate=0.04,
        volatility=iv,
        option_type=OptionType.CALL,
    )

    # Only trade if premium > 0.5% of stock price
    if result['price'] < current_price * 0.005:
        return None

    leg = OptionsLeg(
        option_type=OptionType.CALL,
        strike=strike,
        expiration=expiration,
        quantity=-1,
        entry_premium=result['price'],
        delta=result['delta'],
        gamma=result['gamma'],
        theta=result['theta'],
        vega=result['vega'],
        iv=iv,
    )

    position = OptionsPosition(
        symbol=symbol,
        strategy=StrategyType.COVERED_CALL,
        legs=[leg],
        entry_date=date,
        entry_price=current_price,
    )

    position.calculate_entry_cost()
    return position


def iron_condor_strategy(symbol: str, date: datetime, hist: pd.DataFrame) -> OptionsPosition | None:
    """
    Iron Condor Strategy: Sell OTM put spread + OTM call spread.

    Target Parameters:
    - Short strikes: 0.16 delta (~16% OTM)
    - Long strikes: 0.05 delta (~20% OTM)
    - DTE: 45 days
    - Target credit: 20-30% of width

    Args:
        symbol: Underlying symbol
        date: Current date
        hist: Historical data up to current date

    Returns:
        OptionsPosition or None
    """
    # Only trade weekly
    if date.weekday() != 0:  # Monday
        return None

    current_price = float(hist['Close'].iloc[-1])
    iv = float(hist['IV_Est'].iloc[-1])

    if pd.isna(iv) or iv <= 0:
        iv = 0.20

    # 45 DTE
    dte = 45
    expiration = date + timedelta(days=dte)

    from src.backtesting.options_backtest import BlackScholesPricer

    pricer = BlackScholesPricer()

    # Put spread: 16 delta short, 5 delta long
    short_put_strike = current_price * 0.94  # ~6% OTM
    long_put_strike = current_price * 0.89  # ~11% OTM

    short_put = pricer.calculate(
        spot=current_price,
        strike=short_put_strike,
        time_to_expiry=dte / 365.0,
        risk_free_rate=0.04,
        volatility=iv,
        option_type=OptionType.PUT,
    )

    long_put = pricer.calculate(
        spot=current_price,
        strike=long_put_strike,
        time_to_expiry=dte / 365.0,
        risk_free_rate=0.04,
        volatility=iv,
        option_type=OptionType.PUT,
    )

    # Call spread: 16 delta short, 5 delta long
    short_call_strike = current_price * 1.06
    long_call_strike = current_price * 1.11

    short_call = pricer.calculate(
        spot=current_price,
        strike=short_call_strike,
        time_to_expiry=dte / 365.0,
        risk_free_rate=0.04,
        volatility=iv,
        option_type=OptionType.CALL,
    )

    long_call = pricer.calculate(
        spot=current_price,
        strike=long_call_strike,
        time_to_expiry=dte / 365.0,
        risk_free_rate=0.04,
        volatility=iv,
        option_type=OptionType.CALL,
    )

    # Build legs
    legs = [
        OptionsLeg(
            option_type=OptionType.PUT,
            strike=short_put_strike,
            expiration=expiration,
            quantity=-1,
            entry_premium=short_put['price'],
            delta=short_put['delta'],
            gamma=short_put['gamma'],
            theta=short_put['theta'],
            vega=short_put['vega'],
            iv=iv,
        ),
        OptionsLeg(
            option_type=OptionType.PUT,
            strike=long_put_strike,
            expiration=expiration,
            quantity=1,
            entry_premium=long_put['price'],
            delta=long_put['delta'],
            gamma=long_put['gamma'],
            theta=long_put['theta'],
            vega=long_put['vega'],
            iv=iv,
        ),
        OptionsLeg(
            option_type=OptionType.CALL,
            strike=short_call_strike,
            expiration=expiration,
            quantity=-1,
            entry_premium=short_call['price'],
            delta=short_call['delta'],
            gamma=short_call['gamma'],
            theta=short_call['theta'],
            vega=short_call['vega'],
            iv=iv,
        ),
        OptionsLeg(
            option_type=OptionType.CALL,
            strike=long_call_strike,
            expiration=expiration,
            quantity=1,
            entry_premium=long_call['price'],
            delta=long_call['delta'],
            gamma=long_call['gamma'],
            theta=long_call['theta'],
            vega=long_call['vega'],
            iv=iv,
        ),
    ]

    position = OptionsPosition(
        symbol=symbol,
        strategy=StrategyType.IRON_CONDOR,
        legs=legs,
        entry_date=date,
        entry_price=current_price,
    )

    position.calculate_entry_cost()

    # Only trade if we receive decent credit
    # Credit should be at least 15% of max risk
    max_risk = (long_call_strike - short_call_strike) * 100
    if abs(position.entry_cost) < max_risk * 0.15:
        return None

    return position


def credit_spread_strategy(symbol: str, date: datetime, hist: pd.DataFrame) -> OptionsPosition | None:
    """
    Credit Spread Strategy: Sell OTM put spread for income.

    Target Parameters:
    - Short strike: 0.20 delta
    - Long strike: 0.10 delta
    - DTE: 45 days
    - Width: $5

    Args:
        symbol: Underlying symbol
        date: Current date
        hist: Historical data up to current date

    Returns:
        OptionsPosition or None
    """
    # Trade bi-weekly
    if date.day not in [1, 15]:
        return None

    current_price = float(hist['Close'].iloc[-1])
    iv = float(hist['IV_Est'].iloc[-1])

    if pd.isna(iv) or iv <= 0:
        iv = 0.20

    dte = 45
    expiration = date + timedelta(days=dte)

    from src.backtesting.options_backtest import BlackScholesPricer

    pricer = BlackScholesPricer()

    # Put spread: sell 0.20 delta, buy 0.10 delta
    short_put_strike = current_price * 0.95  # ~5% OTM
    long_put_strike = current_price * 0.90  # ~10% OTM

    short_put = pricer.calculate(
        spot=current_price,
        strike=short_put_strike,
        time_to_expiry=dte / 365.0,
        risk_free_rate=0.04,
        volatility=iv,
        option_type=OptionType.PUT,
    )

    long_put = pricer.calculate(
        spot=current_price,
        strike=long_put_strike,
        time_to_expiry=dte / 365.0,
        risk_free_rate=0.04,
        volatility=iv,
        option_type=OptionType.PUT,
    )

    legs = [
        OptionsLeg(
            option_type=OptionType.PUT,
            strike=short_put_strike,
            expiration=expiration,
            quantity=-1,
            entry_premium=short_put['price'],
            delta=short_put['delta'],
            gamma=short_put['gamma'],
            theta=short_put['theta'],
            vega=short_put['vega'],
            iv=iv,
        ),
        OptionsLeg(
            option_type=OptionType.PUT,
            strike=long_put_strike,
            expiration=expiration,
            quantity=1,
            entry_premium=long_put['price'],
            delta=long_put['delta'],
            gamma=long_put['gamma'],
            theta=long_put['theta'],
            vega=long_put['vega'],
            iv=iv,
        ),
    ]

    position = OptionsPosition(
        symbol=symbol,
        strategy=StrategyType.CREDIT_SPREAD,
        legs=legs,
        entry_date=date,
        entry_price=current_price,
    )

    position.calculate_entry_cost()
    return position


def cash_secured_put_strategy(symbol: str, date: datetime, hist: pd.DataFrame) -> OptionsPosition | None:
    """
    Cash-Secured Put Strategy: Sell OTM puts to acquire stock at discount.

    Target Parameters:
    - Delta: 0.30 (30% probability of assignment)
    - DTE: 30 days
    - Strike: ~5% OTM

    Args:
        symbol: Underlying symbol
        date: Current date
        hist: Historical data up to current date

    Returns:
        OptionsPosition or None
    """
    # Trade twice a month
    if date.day not in [1, 15]:
        return None

    current_price = float(hist['Close'].iloc[-1])
    iv = float(hist['IV_Est'].iloc[-1])

    if pd.isna(iv) or iv <= 0:
        iv = 0.20

    dte = 30
    expiration = date + timedelta(days=dte)

    from src.backtesting.options_backtest import BlackScholesPricer

    pricer = BlackScholesPricer()

    # 5% OTM for ~0.30 delta
    strike = current_price * 0.95

    result = pricer.calculate(
        spot=current_price,
        strike=strike,
        time_to_expiry=dte / 365.0,
        risk_free_rate=0.04,
        volatility=iv,
        option_type=OptionType.PUT,
    )

    # Only trade if premium > 0.5% of stock price
    if result['price'] < current_price * 0.005:
        return None

    leg = OptionsLeg(
        option_type=OptionType.PUT,
        strike=strike,
        expiration=expiration,
        quantity=-1,
        entry_premium=result['price'],
        delta=result['delta'],
        gamma=result['gamma'],
        theta=result['theta'],
        vega=result['vega'],
        iv=iv,
    )

    position = OptionsPosition(
        symbol=symbol,
        strategy=StrategyType.CASH_SECURED_PUT,
        legs=[leg],
        entry_date=date,
        entry_price=current_price,
    )

    position.calculate_entry_cost()
    return position


# ==============================================================================
# MAIN BACKTEST RUNNER
# ==============================================================================


def run_strategy_backtest(
    strategy_name: str,
    start_date: str,
    end_date: str,
    symbols: list[str],
    initial_capital: float = 100000.0,
) -> tuple[BacktestMetrics, OptionsBacktestEngine]:
    """
    Run backtest for a specific strategy.

    Args:
        strategy_name: Name of strategy to test
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        symbols: List of symbols to trade
        initial_capital: Starting capital

    Returns:
        Tuple of (metrics, engine)
    """
    strategies = {
        "covered_call": covered_call_strategy,
        "iron_condor": iron_condor_strategy,
        "credit_spread": credit_spread_strategy,
        "cash_secured_put": cash_secured_put_strategy,
    }

    if strategy_name not in strategies:
        raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(strategies.keys())}")

    logger.info(f"Running backtest for {strategy_name} strategy")

    # Create engine
    engine = OptionsBacktestEngine(
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
    )

    # Run backtest
    metrics = engine.run_backtest(
        strategy=strategies[strategy_name],
        symbols=symbols,
        trade_frequency_days=7,
    )

    return metrics, engine


def run_all_strategies(
    start_date: str,
    end_date: str,
    symbols: list[str],
    initial_capital: float = 100000.0,
) -> dict[str, tuple[BacktestMetrics, OptionsBacktestEngine]]:
    """
    Run backtest for all strategies and compare results.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        symbols: List of symbols to trade
        initial_capital: Starting capital

    Returns:
        Dictionary mapping strategy name to (metrics, engine)
    """
    results = {}

    for strategy_name in ["covered_call", "iron_condor", "credit_spread", "cash_secured_put"]:
        logger.info(f"\n{'='*80}\n")
        logger.info(f"Testing {strategy_name.upper().replace('_', ' ')} Strategy")
        logger.info(f"\n{'='*80}\n")

        try:
            metrics, engine = run_strategy_backtest(
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
                symbols=symbols,
                initial_capital=initial_capital,
            )
            results[strategy_name] = (metrics, engine)

        except Exception as e:
            logger.error(f"Failed to run {strategy_name} backtest: {e}")

    return results


def print_comparison_report(results: dict[str, tuple[BacktestMetrics, OptionsBacktestEngine]]) -> None:
    """Print comparison report for all strategies."""
    print("\n" + "=" * 80)
    print("STRATEGY COMPARISON REPORT")
    print("=" * 80)
    print()

    # Create comparison table
    headers = ["Strategy", "Total Return", "Sharpe", "Win Rate", "Max DD", "Avg Trade", "Total Trades"]
    rows = []

    for strategy_name, (metrics, _) in results.items():
        rows.append([
            strategy_name.replace("_", " ").title(),
            f"{metrics.total_return:+.2f}%",
            f"{metrics.sharpe_ratio:.2f}",
            f"{metrics.win_rate:.1f}%",
            f"{metrics.max_drawdown:.2f}%",
            f"${metrics.avg_trade:.2f}",
            str(metrics.total_trades),
        ])

    # Print table
    col_widths = [max(len(str(row[i])) for row in [headers] + rows) + 2 for i in range(len(headers))]

    def print_row(row):
        print("".join(str(cell).ljust(width) for cell, width in zip(row, col_widths)))

    def print_separator():
        print("-" * sum(col_widths))

    print_row(headers)
    print_separator()
    for row in rows:
        print_row(row)
    print_separator()

    # Print winner
    if results:
        best_sharpe = max(results.items(), key=lambda x: x[1][0].sharpe_ratio)
        best_return = max(results.items(), key=lambda x: x[1][0].total_return)
        best_winrate = max(results.items(), key=lambda x: x[1][0].win_rate)

        print()
        print(f"Best Sharpe Ratio: {best_sharpe[0].replace('_', ' ').title()} ({best_sharpe[1][0].sharpe_ratio:.2f})")
        print(f"Best Total Return: {best_return[0].replace('_', ' ').title()} ({best_return[1][0].total_return:+.2f}%)")
        print(f"Best Win Rate: {best_winrate[0].replace('_', ' ').title()} ({best_winrate[1][0].win_rate:.1f}%)")

    print()
    print("=" * 80)


def main():
    """Main entry point for options backtest."""
    parser = ArgumentParser(description="Options Strategy Backtesting")
    parser.add_argument(
        "--strategy",
        type=str,
        choices=["covered_call", "iron_condor", "credit_spread", "cash_secured_put", "all"],
        default="all",
        help="Strategy to backtest (default: all)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default="2024-01-01",
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2024-12-31",
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        nargs="+",
        default=["SPY", "QQQ"],
        help="Symbols to trade (default: SPY QQQ)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100000.0,
        help="Initial capital (default: 100000)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save results to file",
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("OPTIONS BACKTEST - COMPREHENSIVE ANALYSIS")
    logger.info("=" * 80)
    logger.info(f"Period: {args.start} to {args.end}")
    logger.info(f"Symbols: {', '.join(args.symbols)}")
    logger.info(f"Initial Capital: ${args.capital:,.2f}")
    logger.info("=" * 80)

    # Run backtest
    if args.strategy == "all":
        results = run_all_strategies(
            start_date=args.start,
            end_date=args.end,
            symbols=args.symbols,
            initial_capital=args.capital,
        )

        # Print comparison
        print_comparison_report(results)

        # Generate reports for each strategy
        if args.save:
            output_dir = project_root / "reports" / "backtests"
            output_dir.mkdir(parents=True, exist_ok=True)

            for strategy_name, (metrics, engine) in results.items():
                report_path = engine.generate_report(
                    metrics,
                    output_dir=output_dir,
                )
                logger.info(f"{strategy_name} report saved: {report_path}")

                # Save metrics as JSON
                json_path = output_dir / f"options_{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(json_path, "w") as f:
                    json.dump(metrics.to_dict(), f, indent=2, default=str)
                logger.info(f"{strategy_name} metrics saved: {json_path}")

    else:
        metrics, engine = run_strategy_backtest(
            strategy_name=args.strategy,
            start_date=args.start,
            end_date=args.end,
            symbols=args.symbols,
            initial_capital=args.capital,
        )

        # Print results
        print("\n" + "=" * 80)
        print(f"{args.strategy.upper().replace('_', ' ')} STRATEGY RESULTS")
        print("=" * 80)
        print(f"\nTotal Return: {metrics.total_return:+.2f}%")
        print(f"CAGR: {metrics.cagr:+.2f}%")
        print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        print(f"Sortino Ratio: {metrics.sortino_ratio:.2f}")
        print(f"Max Drawdown: {metrics.max_drawdown:.2f}%")
        print(f"\nTotal Trades: {metrics.total_trades}")
        print(f"Win Rate: {metrics.win_rate:.1f}%")
        print(f"Profit Factor: {metrics.profit_factor:.2f}")
        print(f"Avg Trade: ${metrics.avg_trade:.2f}")
        print(f"\nAvg Days in Trade: {metrics.avg_days_in_trade:.1f}")
        print(f"Total Commissions: ${metrics.total_commissions:.2f}")
        print("=" * 80)

        # Generate report
        if args.save:
            report_path = engine.generate_report(metrics)
            logger.info(f"Report saved: {report_path}")

            # Save metrics as JSON
            json_path = report_path.parent / f"options_{args.strategy}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(json_path, "w") as f:
                json.dump(metrics.to_dict(), f, indent=2, default=str)
            logger.info(f"Metrics saved: {json_path}")


if __name__ == "__main__":
    main()
