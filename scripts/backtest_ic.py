#!/usr/bin/env python3
"""
Iron Condor Backtester — Validates strategy on historical SPY data.

Uses yfinance for historical prices. Simulates 15-delta $10-wide ICs
with our exact rules: 50% profit target, 100% stop loss, 7 DTE exit.

Usage:
    python scripts/backtest_ic.py                    # Default: 5 years
    python scripts/backtest_ic.py --years 10         # 10 years
    python scripts/backtest_ic.py --years 3 --delta 0.20  # Custom delta
"""

import argparse
import json
import logging
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("backtest")

sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class ICTrade:
    entry_date: str
    expiry_date: str
    spy_price: float
    short_put: float
    short_call: float
    credit: float
    exit_date: str = ""
    exit_reason: str = ""
    pnl: float = 0.0
    dte_at_exit: int = 0
    max_drawdown: float = 0.0


@dataclass
class BacktestResult:
    trades: list[ICTrade] = field(default_factory=list)
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    years: int = 0
    monthly_avg: float = 0.0


def estimate_ic_credit(spy_price: float, delta: float, wing_width: float, dte: int) -> float:
    """Estimate IC net credit from Black-Scholes approximation.

    Uses empirical relationship: credit ≈ spy_price * IV * sqrt(DTE/365) * delta_factor
    Adjusted for $10-wide wings where long legs cost ~40-60% of short leg premium.
    """
    # Approximate IV from VIX historical average (~18% long-term)
    iv = 0.18
    time_factor = math.sqrt(dte / 365)

    # Short option premium approximation (both sides)
    short_put_prem = spy_price * iv * time_factor * delta * 1.2
    short_call_prem = spy_price * iv * time_factor * delta * 1.2

    # Long legs cost: further OTM, roughly 40-60% of short premium for $10 wings
    wing_discount = 0.50
    long_put_cost = short_put_prem * wing_discount
    long_call_cost = short_call_prem * wing_discount

    net_credit = (short_put_prem + short_call_prem) - (long_put_cost + long_call_cost)
    return round(max(net_credit, 0.50), 2)


def get_strikes(spy_price: float, delta: float, wing_width: float) -> tuple[float, float]:
    """Estimate strike prices from delta approximation."""
    # 15-delta ≈ ~5% OTM for 30 DTE
    otm_pct = delta * 0.35  # Empirical: delta-to-OTM% mapping
    short_put = round(spy_price * (1 - otm_pct) / 5) * 5  # Round to $5
    short_call = round(spy_price * (1 + otm_pct) / 5) * 5
    return short_put, short_call


def simulate_ic_pnl(
    entry_price: float,
    prices_during_trade: list[float],
    short_put: float,
    short_call: float,
    credit: float,
    wing_width: float,
    profit_target: float = 0.50,
    stop_loss: float = 1.0,
    exit_dte: int = 7,
    total_dte: int = 30,
) -> tuple[float, str, int, float]:
    """Simulate IC P/L through holding period.

    Returns (pnl, exit_reason, dte_at_exit, max_drawdown).
    """
    max_profit = credit * 100  # Per contract
    max_loss = (wing_width * 100) - max_profit

    max_dd = 0.0

    for day_idx, price in enumerate(prices_during_trade):
        days_held = day_idx + 1
        dte = total_dte - days_held

        # Theta decay: credit decays roughly linearly (simplified)
        theta_decay = (days_held / total_dte) * credit * 100

        # Intrinsic value if breached
        put_intrinsic = max(0, short_put - price) * 100
        call_intrinsic = max(0, price - short_call) * 100
        intrinsic_loss = put_intrinsic + call_intrinsic

        # P/L = theta decay - intrinsic losses
        current_pnl = theta_decay - intrinsic_loss

        # Cap at max profit/loss
        current_pnl = max(-max_loss, min(max_profit, current_pnl))

        max_dd = min(max_dd, current_pnl)

        # Exit checks
        if current_pnl >= max_profit * profit_target:
            return current_pnl, "PROFIT_TARGET", dte, max_dd

        if current_pnl <= -max_profit * stop_loss:
            return current_pnl, "STOP_LOSS", dte, max_dd

        if dte <= exit_dte:
            return current_pnl, "DTE_EXIT", dte, max_dd

    # Held to expiration
    return current_pnl, "EXPIRATION", 0, max_dd


def run_backtest(
    years: int = 5,
    delta: float = 0.15,
    wing_width: float = 10.0,
    target_dte: int = 30,
    profit_target: float = 0.50,
    stop_loss: float = 1.0,
    exit_dte: int = 7,
    max_concurrent: int = 4,
    entry_interval_days: int = 7,
) -> BacktestResult:
    """Run full IC backtest on historical SPY data."""
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance required: pip install yfinance")
        sys.exit(1)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)

    logger.info(f"Downloading SPY data: {start_date.date()} to {end_date.date()}")
    spy = yf.download("SPY", start=start_date, end=end_date, progress=False)

    if spy.empty:
        logger.error("No SPY data returned")
        sys.exit(1)

    # Flatten MultiIndex columns if present
    if hasattr(spy.columns, "levels"):
        spy.columns = [col[0] if isinstance(col, tuple) else col for col in spy.columns]

    prices = spy["Close"].values.tolist()
    dates = [d.strftime("%Y-%m-%d") for d in spy.index]

    logger.info(f"Got {len(prices)} trading days ({dates[0]} to {dates[-1]})")

    trades = []
    open_trades = []
    last_entry_idx = -entry_interval_days  # Allow immediate first entry

    for i in range(target_dte, len(prices) - target_dte):
        # Check exits on open trades
        still_open = []
        for trade_info in open_trades:
            trade, entry_idx = trade_info
            days_since_entry = i - entry_idx
            if days_since_entry > 0:
                trade_prices = prices[entry_idx + 1 : entry_idx + 1 + days_since_entry]
                if trade_prices:
                    pnl, reason, dte_at_exit, max_dd = simulate_ic_pnl(
                        entry_price=prices[entry_idx],
                        prices_during_trade=trade_prices,
                        short_put=trade.short_put,
                        short_call=trade.short_call,
                        credit=trade.credit,
                        wing_width=wing_width,
                        profit_target=profit_target,
                        stop_loss=stop_loss,
                        exit_dte=exit_dte,
                        total_dte=target_dte,
                    )
                    if reason != "":
                        trade.pnl = round(pnl, 2)
                        trade.exit_reason = reason
                        trade.exit_date = dates[i]
                        trade.dte_at_exit = dte_at_exit
                        trade.max_drawdown = round(max_dd, 2)
                        trades.append(trade)
                        continue
            still_open.append(trade_info)
        open_trades = still_open

        # Entry: check if we can open a new IC
        if len(open_trades) < max_concurrent and (i - last_entry_idx) >= entry_interval_days:
            spy_price = prices[i]
            short_put, short_call = get_strikes(spy_price, delta, wing_width)
            credit = estimate_ic_credit(spy_price, delta, wing_width, target_dte)

            trade = ICTrade(
                entry_date=dates[i],
                expiry_date=dates[min(i + target_dte, len(dates) - 1)],
                spy_price=round(spy_price, 2),
                short_put=short_put,
                short_call=short_call,
                credit=credit,
            )
            open_trades.append((trade, i))
            last_entry_idx = i

    # Close any remaining open trades at last price
    for trade, entry_idx in open_trades:
        days = len(prices) - entry_idx - 1
        if days > 0:
            trade_prices = prices[entry_idx + 1 :]
            pnl, reason, dte, max_dd = simulate_ic_pnl(
                entry_price=prices[entry_idx],
                prices_during_trade=trade_prices,
                short_put=trade.short_put,
                short_call=trade.short_call,
                credit=trade.credit,
                wing_width=wing_width,
                profit_target=profit_target,
                stop_loss=stop_loss,
                exit_dte=exit_dte,
                total_dte=target_dte,
            )
            trade.pnl = round(pnl, 2)
            trade.exit_reason = reason or "END_OF_DATA"
            trade.exit_date = dates[-1]
            trade.dte_at_exit = dte
            trade.max_drawdown = round(max_dd, 2)
            trades.append(trade)

    # Calculate statistics
    result = BacktestResult(trades=trades, years=years)

    if not trades:
        logger.warning("No trades generated")
        return result

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]

    result.total_pnl = round(sum(t.pnl for t in trades), 2)
    result.win_rate = round(len(wins) / len(trades) * 100, 1) if trades else 0
    result.avg_win = round(sum(t.pnl for t in wins) / len(wins), 2) if wins else 0
    result.avg_loss = round(sum(t.pnl for t in losses) / len(losses), 2) if losses else 0
    result.monthly_avg = round(result.total_pnl / (years * 12), 2)

    # Profit factor
    gross_profit = sum(t.pnl for t in wins) if wins else 0
    gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0
    result.profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 999.0

    # Sharpe (annualized)
    pnls = [t.pnl for t in trades]
    if len(pnls) > 1:
        mean_pnl = sum(pnls) / len(pnls)
        std_pnl = math.sqrt(sum((p - mean_pnl) ** 2 for p in pnls) / (len(pnls) - 1))
        trades_per_year = len(trades) / years
        result.sharpe = (
            round((mean_pnl / std_pnl) * math.sqrt(trades_per_year), 2) if std_pnl > 0 else 0
        )

    # Max drawdown
    cumulative = []
    running = 0
    for t in trades:
        running += t.pnl
        cumulative.append(running)
    peak = cumulative[0] if cumulative else 0
    max_dd = 0
    for c in cumulative:
        peak = max(peak, c)
        max_dd = max(max_dd, peak - c)
    result.max_drawdown = round(max_dd, 2)

    return result


def print_report(result: BacktestResult, delta: float, wing_width: float):
    """Print backtest results."""
    print("=" * 60)
    print("IRON CONDOR BACKTEST RESULTS")
    print("=" * 60)
    print(f"Period: {result.years} years")
    print(f"Strategy: {delta * 100:.0f}-delta, ${wing_width:.0f}-wide wings")
    print("Rules: 50% profit, 100% stop, 7 DTE exit")
    print()
    print(f"Total trades:    {len(result.trades)}")
    print(f"Win rate:        {result.win_rate:.1f}%")
    print(f"Total P/L:       ${result.total_pnl:+,.2f}")
    print(f"Monthly avg:     ${result.monthly_avg:+,.2f}")
    print(f"Avg win:         ${result.avg_win:+,.2f}")
    print(f"Avg loss:        ${result.avg_loss:+,.2f}")
    print(f"Profit factor:   {result.profit_factor:.2f}")
    print(f"Sharpe ratio:    {result.sharpe:.2f}")
    print(f"Max drawdown:    ${result.max_drawdown:,.2f}")

    # Exit reason breakdown
    reasons = {}
    for t in result.trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
    print("\nExit reasons:")
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
        pct = count / len(result.trades) * 100
        print(f"  {reason}: {count} ({pct:.0f}%)")

    # Monthly P/L by year
    print("\nAnnual P/L:")
    year_pnl = {}
    for t in result.trades:
        year = t.entry_date[:4]
        year_pnl[year] = year_pnl.get(year, 0) + t.pnl
    for year in sorted(year_pnl):
        print(f"  {year}: ${year_pnl[year]:+,.2f}")

    # North Star projection
    print(f"\n{'=' * 60}")
    print("NORTH STAR PROJECTION")
    print(f"{'=' * 60}")
    if result.monthly_avg > 0:
        # Scale from 1 contract to account size
        monthly_per_contract = result.monthly_avg
        contracts_for_6k = (
            math.ceil(6000 / monthly_per_contract) if monthly_per_contract > 0 else 999
        )
        capital_needed = contracts_for_6k * wing_width * 100  # Max risk per contract
        print(f"Monthly avg per contract: ${monthly_per_contract:+,.2f}")
        print(f"Contracts needed for $6K/mo: {contracts_for_6k}")
        print(f"Capital needed (max risk): ${capital_needed:,.0f}")
        print("Current capital: $95,364")
        print(f"Current max contracts: {int(95364 / (wing_width * 100))}")
        current_monthly = int(95364 / (wing_width * 100)) * monthly_per_contract
        print(f"Projected monthly at current capital: ${current_monthly:+,.2f}")
    else:
        print("Strategy is unprofitable — cannot project North Star path")


def save_results(result: BacktestResult, delta: float, wing_width: float):
    """Save backtest results to RAG for ML pipeline."""
    output_dir = Path(__file__).parent.parent / "data" / "rag_knowledge" / "lessons_learned"
    output_dir.mkdir(parents=True, exist_ok=True)

    lesson = f"""# Backtest Results: {delta * 100:.0f}-Delta ${wing_width:.0f}-Wide IC

- **Period**: {result.years} years
- **Total trades**: {len(result.trades)}
- **Win rate**: {result.win_rate:.1f}%
- **Total P/L**: ${result.total_pnl:+,.2f}
- **Monthly avg**: ${result.monthly_avg:+,.2f}/contract
- **Profit factor**: {result.profit_factor:.2f}
- **Sharpe**: {result.sharpe:.2f}
- **Max drawdown**: ${result.max_drawdown:,.2f}

## Key Finding
{"Strategy is PROFITABLE with " + f"{result.win_rate:.0f}% win rate and {result.profit_factor:.1f}x profit factor." if result.total_pnl > 0 else "Strategy is UNPROFITABLE. Review parameters."}

## Generated
{datetime.now().strftime("%Y-%m-%d %H:%M")}
"""
    filename = f"backtest_{delta * 100:.0f}d_{wing_width:.0f}w_{result.years}y_{datetime.now().strftime('%Y%m%d')}.md"
    (output_dir / filename).write_text(lesson)

    # Also save raw trades as JSON for ML training
    trades_file = Path(__file__).parent.parent / "data" / "backtest_trades.json"
    trades_data = {
        "backtest_date": datetime.now().isoformat(),
        "params": {"delta": delta, "wing_width": wing_width, "years": result.years},
        "stats": {
            "total_trades": len(result.trades),
            "win_rate": result.win_rate,
            "total_pnl": result.total_pnl,
            "monthly_avg": result.monthly_avg,
            "profit_factor": result.profit_factor,
            "sharpe": result.sharpe,
            "max_drawdown": result.max_drawdown,
        },
        "trades": [
            {
                "entry_date": t.entry_date,
                "exit_date": t.exit_date,
                "spy_price": t.spy_price,
                "credit": t.credit,
                "pnl": t.pnl,
                "exit_reason": t.exit_reason,
                "dte_at_exit": t.dte_at_exit,
            }
            for t in result.trades
        ],
    }
    trades_file.write_text(json.dumps(trades_data, indent=2))
    logger.info(f"Saved {len(result.trades)} trades to {trades_file}")
    logger.info(f"Saved lesson to {output_dir / filename}")


def main():
    parser = argparse.ArgumentParser(description="IC Backtester")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--delta", type=float, default=0.15)
    parser.add_argument("--wing-width", type=float, default=10.0)
    parser.add_argument("--max-concurrent", type=int, default=4)
    parser.add_argument("--entry-interval", type=int, default=7, help="Days between entries")
    args = parser.parse_args()

    result = run_backtest(
        years=args.years,
        delta=args.delta,
        wing_width=args.wing_width,
        max_concurrent=args.max_concurrent,
        entry_interval_days=args.entry_interval,
    )

    print_report(result, args.delta, args.wing_width)
    save_results(result, args.delta, args.wing_width)


if __name__ == "__main__":
    main()
