#!/usr/bin/env python3
"""Vectorized 10-Year Historical Options Credit Spread Backtester (2015-2026).

Models Black-Scholes pricing, volatility skew, IV Rank, delta targeting,
take-profit, stop-loss, and DTE-based exit management across all market regimes.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parents[1]


def black_scholes_put_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Calculate European Put price using Black-Scholes formula."""
    if T <= 0 or sigma <= 0:
        return max(0.0, K - S)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    put_price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return max(0.01, put_price)


def black_scholes_put_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Calculate European Put Delta (absolute value between 0 and 1)."""
    if T <= 0 or sigma <= 0:
        return 1.0 if S < K else 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return abs(norm.cdf(d1) - 1.0)


def find_strike_for_delta(
    S: float, target_delta: float, T: float, r: float, sigma: float
) -> float:
    """Find put strike K matching target delta (OTM put, Delta between 0.05 and 0.50)."""
    z = norm.ppf(1.0 - target_delta)
    # K = S * exp(-z * sigma * sqrt(T) + (r + 0.5 * sigma^2) * T)
    exponent = -z * sigma * math.sqrt(T) + (r + 0.5 * sigma**2) * T
    raw_strike = S * math.exp(exponent)
    return round(raw_strike)


@dataclass
class BacktestConfig:
    symbol: str = "SPY"
    start_date: str = "2015-01-01"
    end_date: str = "2026-09-01"
    initial_capital: float = 100000.0
    risk_per_trade_pct: float = 0.02  # 2% of portfolio per trade
    target_delta: float = 0.15
    target_dte: int = 40  # 30-45 DTE target
    spread_width: float = 5.0  # $5 wide
    take_profit_pct: float = 0.50  # 50% max profit
    stop_loss_pct: float = 2.00  # 200% stop loss (loss = 2x credit)
    exit_dte: int = 21  # Close at 21 DTE to avoid gamma risk
    min_iv_rank: float = 20.0  # Minimum IV rank to enter
    require_trend: bool = True  # Require SPY > 200 SMA
    risk_free_rate: float = 0.02
    max_concurrent_trades: int = 4


@dataclass
class TradeRecord:
    trade_id: int
    entry_date: str
    exit_date: str
    spy_entry_price: float
    spy_exit_price: float
    short_strike: float
    long_strike: float
    credit_received: float
    debit_paid_to_close: float
    realized_pnl_per_share: float
    contracts: int
    total_dollar_pnl: float
    hold_days: int
    exit_dte: int
    exit_reason: str
    iv_rank_at_entry: float
    capital_after: float


class HistoricalOptionsBacktester:
    def __init__(self, config: BacktestConfig):
        self.config = config

    def fetch_market_data(self) -> pd.DataFrame:
        """Fetch SPY and VIX historical daily data."""
        spy = yf.download(self.config.symbol, start="2014-01-01", end=self.config.end_date, progress=False)
        vix = yf.download("^VIX", start="2014-01-01", end=self.config.end_date, progress=False)

        # Handle multi-index columns from yfinance
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = [c[0] for c in spy.columns]
        if isinstance(vix.columns, pd.MultiIndex):
            vix.columns = [c[0] for c in vix.columns]

        df = pd.DataFrame(index=spy.index)
        df["SPY_Close"] = spy["Close"]
        df["SPY_High"] = spy["High"]
        df["SPY_Low"] = spy["Low"]
        df["VIX"] = vix["Close"].reindex(spy.index).ffill()

        # Compute 200-day and 50-day SMA
        df["SPY_SMA200"] = df["SPY_Close"].rolling(window=200).mean()
        df["SPY_SMA50"] = df["SPY_Close"].rolling(window=50).mean()

        # Compute 252-day IV Rank from VIX
        vix_min252 = df["VIX"].rolling(window=252).min()
        vix_max252 = df["VIX"].rolling(window=252).max()
        df["IV_Rank"] = 100.0 * (df["VIX"] - vix_min252) / (vix_max252 - vix_min252 + 1e-6)

        # Realized historical volatility (20-day annualized)
        log_ret = np.log(df["SPY_Close"] / df["SPY_Close"].shift(1))
        df["HV20"] = log_ret.rolling(window=20).std() * math.sqrt(252)
        # Option IV proxy (VIX / 100 with skew adjustment: puts trade +2% IV over ATM VIX)
        df["Put_IV"] = (df["VIX"] / 100.0) + 0.02

        df = df.dropna().loc[self.config.start_date :]
        return df

    def run_backtest(self) -> dict[str, Any]:
        df = self.fetch_market_data()
        capital = self.config.initial_capital
        peak_capital = capital
        trades: list[TradeRecord] = []
        open_positions: list[dict[str, Any]] = []
        equity_curve: list[dict[str, Any]] = []

        dates = df.index.tolist()
        trade_counter = 0

        for current_date in dates:
            current_row = df.loc[current_date]
            spy_price = float(current_row["SPY_Close"])
            spy_low = float(current_row["SPY_Low"])
            iv_rank = float(current_row["IV_Rank"])
            put_iv = float(current_row["Put_IV"])
            sma200 = float(current_row["SPY_SMA200"])

            # 1. Evaluate and manage open positions
            remaining_positions = []
            for pos in open_positions:
                days_held = (current_date - pos["entry_date"]).days
                current_dte = pos["initial_dte"] - days_held
                T = max(0.001, current_dte / 365.0)

                # Current put prices
                short_p = black_scholes_put_price(
                    spy_price, pos["short_strike"], T, self.config.risk_free_rate, put_iv
                )
                long_p = black_scholes_put_price(
                    spy_price, pos["long_strike"], T, self.config.risk_free_rate, put_iv
                )
                current_spread_debit = max(0.0, short_p - long_p)

                # Check Exit Conditions
                closed = False
                exit_reason = ""

                # Take Profit check (50% max profit)
                target_debit = pos["initial_credit"] * (1.0 - self.config.take_profit_pct)
                if current_spread_debit <= target_debit:
                    closed = True
                    exit_reason = "TAKE_PROFIT_50%"
                    realized_debit = target_debit

                # Stop Loss check (loss >= 2x initial credit)
                max_stop_debit = pos["initial_credit"] * (1.0 + self.config.stop_loss_pct)
                if not closed and (current_spread_debit >= max_stop_debit or spy_low <= pos["long_strike"]):
                    closed = True
                    exit_reason = "STOP_LOSS_200%"
                    realized_debit = min(self.config.spread_width, max_stop_debit)

                # DTE / Time exit check (21 DTE rule)
                if not closed and current_dte <= self.config.exit_dte:
                    closed = True
                    exit_reason = f"DTE_EXIT_{self.config.exit_dte}DTE"
                    realized_debit = current_spread_debit

                # Expiration check
                if not closed and current_dte <= 0:
                    closed = True
                    exit_reason = "EXPIRATION"
                    realized_debit = max(0.0, pos["short_strike"] - spy_price) - max(
                        0.0, pos["long_strike"] - spy_price
                    )

                if closed:
                    pnl_per_share = pos["initial_credit"] - realized_debit
                    total_pnl = pnl_per_share * 100.0 * pos["contracts"]
                    capital += total_pnl

                    trades.append(
                        TradeRecord(
                            trade_id=pos["trade_id"],
                            entry_date=pos["entry_date"].strftime("%Y-%m-%d"),
                            exit_date=current_date.strftime("%Y-%m-%d"),
                            spy_entry_price=pos["spy_entry_price"],
                            spy_exit_price=spy_price,
                            short_strike=pos["short_strike"],
                            long_strike=pos["long_strike"],
                            credit_received=pos["initial_credit"],
                            debit_paid_to_close=round(realized_debit, 3),
                            realized_pnl_per_share=round(pnl_per_share, 3),
                            contracts=pos["contracts"],
                            total_dollar_pnl=round(total_pnl, 2),
                            hold_days=days_held,
                            exit_dte=current_dte,
                            exit_reason=exit_reason,
                            iv_rank_at_entry=pos["iv_rank"],
                            capital_after=round(capital, 2),
                        )
                    )
                else:
                    remaining_positions.append(pos)

            open_positions = remaining_positions

            # 2. Check Entry Conditions
            # Filter 1: Max concurrent trades
            can_enter = len(open_positions) < self.config.max_concurrent_trades

            # Filter 2: Volatility Rank
            if can_enter and iv_rank < self.config.min_iv_rank:
                can_enter = False

            # Filter 3: Trend Filter (SPY > 200 SMA)
            if can_enter and self.config.require_trend and spy_price < sma200:
                can_enter = False

            # Filter 4: Cadence (enter at most 1 trade per 3 trading days)
            if can_enter and trades:
                last_trade_entry = datetime.strptime(trades[-1].entry_date, "%Y-%m-%d")
                if (current_date - last_trade_entry).days < 3:
                    can_enter = False

            if can_enter:
                # Find strikes for target delta
                T = self.config.target_dte / 365.0
                short_k = find_strike_for_delta(
                    spy_price, self.config.target_delta, T, self.config.risk_free_rate, put_iv
                )
                long_k = short_k - self.config.spread_width

                short_price = black_scholes_put_price(
                    spy_price, short_k, T, self.config.risk_free_rate, put_iv
                )
                long_price = black_scholes_put_price(
                    spy_price, long_k, T, self.config.risk_free_rate, put_iv
                )
                initial_credit = max(0.20, short_price - long_price)

                # Sizing: Fixed fractional risk
                # Max loss per spread = (width - credit) * 100
                max_loss_per_contract = (self.config.spread_width - initial_credit) * 100.0
                dollar_risk_target = capital * self.config.risk_per_trade_pct
                contracts = max(1, int(dollar_risk_target / max_loss_per_contract))
                contracts = min(contracts, 20)  # Safe hard limit

                trade_counter += 1
                open_positions.append(
                    {
                        "trade_id": trade_counter,
                        "entry_date": current_date,
                        "spy_entry_price": spy_price,
                        "short_strike": short_k,
                        "long_strike": long_k,
                        "initial_credit": round(initial_credit, 3),
                        "initial_dte": self.config.target_dte,
                        "contracts": contracts,
                        "iv_rank": round(iv_rank, 1),
                    }
                )

            # Record daily equity
            peak_capital = max(peak_capital, capital)
            drawdown_pct = (peak_capital - capital) / peak_capital * 100.0
            equity_curve.append(
                {
                    "date": current_date.strftime("%Y-%m-%d"),
                    "capital": round(capital, 2),
                    "drawdown_pct": round(drawdown_pct, 2),
                    "open_positions": len(open_positions),
                }
            )

        # Compute comprehensive statistics
        summary = self._compute_statistics(trades, equity_curve)
        return {"summary": summary, "trades": [asdict(t) for t in trades], "equity_curve": equity_curve}

    def _compute_statistics(
        self, trades: list[TradeRecord], equity_curve: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if not trades:
            return {"error": "No trades generated."}

        pnls = [t.total_dollar_pnl for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        total_pnl = sum(pnls)

        n_trades = len(trades)
        n_wins = len(wins)
        n_losses = len(losses)
        win_rate = (n_wins / n_trades) * 100.0 if n_trades > 0 else 0.0

        total_gain = sum(wins) if wins else 0.0
        total_loss = abs(sum(losses)) if losses else 1e-6
        profit_factor = total_gain / total_loss if total_loss > 0 else float("inf")

        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = abs(np.mean(losses)) if losses else 0.0
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")
        expectancy = np.mean(pnls) if pnls else 0.0

        # Drawdown and returns
        initial_cap = self.config.initial_capital
        final_cap = trades[-1].capital_after if trades else initial_cap
        total_return_pct = ((final_cap - initial_cap) / initial_cap) * 100.0

        start_dt = datetime.strptime(trades[0].entry_date, "%Y-%m-%d")
        end_dt = datetime.strptime(trades[-1].exit_date, "%Y-%m-%d")
        years = max(0.5, (end_dt - start_dt).days / 365.25)
        cagr_pct = ((final_cap / initial_cap) ** (1.0 / years) - 1.0) * 100.0

        drawdowns = [e["drawdown_pct"] for e in equity_curve]
        max_drawdown_pct = max(drawdowns) if drawdowns else 0.0

        # Sharpe / Sortino
        eq_series = pd.Series([e["capital"] for e in equity_curve])
        daily_returns = eq_series.pct_change().dropna()
        if len(daily_returns) > 0 and daily_returns.std() > 0:
            sharpe = (daily_returns.mean() / daily_returns.std()) * math.sqrt(252)
            neg_returns = daily_returns[daily_returns < 0]
            downside_std = neg_returns.std() if len(neg_returns) > 0 else 1e-6
            sortino = (daily_returns.mean() / downside_std) * math.sqrt(252)
        else:
            sharpe = 0.0
            sortino = 0.0

        # Regime breakdown (by years)
        regimes: dict[str, dict[str, Any]] = {}
        trade_df = pd.DataFrame([asdict(t) for t in trades])
        trade_df["year"] = pd.to_datetime(trade_df["entry_date"]).dt.year

        for year, group in trade_df.groupby("year"):
            y_pnls = group["total_dollar_pnl"].tolist()
            y_wins = [p for p in y_pnls if p > 0]
            regimes[str(year)] = {
                "trades": len(y_pnls),
                "win_rate_pct": round(len(y_wins) / len(y_pnls) * 100.0, 1),
                "total_pnl": round(sum(y_pnls), 2),
                "avg_trade_pnl": round(float(np.mean(y_pnls)), 2),
            }

        # Exit reasons breakdown
        exit_reasons = trade_df["exit_reason"].value_counts().to_dict()

        return {
            "period": f"{trades[0].entry_date} to {trades[-1].exit_date} ({years:.1f} years)",
            "initial_capital": initial_cap,
            "final_capital": round(final_cap, 2),
            "total_net_pnl": round(total_pnl, 2),
            "total_return_pct": round(total_return_pct, 2),
            "cagr_pct": round(cagr_pct, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "total_trades": n_trades,
            "wins": n_wins,
            "losses": n_losses,
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_win": round(float(avg_win), 2),
            "avg_loss": round(float(avg_loss), 2),
            "win_loss_ratio": round(float(win_loss_ratio), 2),
            "expectancy_per_trade": round(float(expectancy), 2),
            "sharpe_ratio": round(float(sharpe), 2),
            "sortino_ratio": round(float(sortino), 2),
            "exit_reasons": exit_reasons,
            "yearly_performance": regimes,
        }


def run_tournament() -> list[dict[str, Any]]:
    """Run parameter tournament across key delta, IV rank, and management rules."""
    scenarios = [
        {"name": "Conservative 15Δ (50% TP, 200% SL, 21 DTE, IVR>=20)", "delta": 0.15, "tp": 0.50, "sl": 2.00, "exit_dte": 21, "min_ivr": 20.0, "trend": True},
        {"name": "Selective High-IVR 15Δ (50% TP, 200% SL, 21 DTE, IVR>=30)", "delta": 0.15, "tp": 0.50, "sl": 2.00, "exit_dte": 21, "min_ivr": 30.0, "trend": True},
        {"name": "Ultra-Safe 10Δ (50% TP, 200% SL, 21 DTE, IVR>=20)", "delta": 0.10, "tp": 0.50, "sl": 2.00, "exit_dte": 21, "min_ivr": 20.0, "trend": True},
        {"name": "Aggressive 20Δ (50% TP, 200% SL, 21 DTE, IVR>=20)", "delta": 0.20, "tp": 0.50, "sl": 2.00, "exit_dte": 21, "min_ivr": 20.0, "trend": True},
        {"name": "Fast Scalp 15Δ (25% TP, 200% SL, 21 DTE, IVR>=20)", "delta": 0.15, "tp": 0.25, "sl": 2.00, "exit_dte": 21, "min_ivr": 20.0, "trend": True},
        {"name": "No Early Exit 15Δ (50% TP, 200% SL, Hold to Expiry, IVR>=20)", "delta": 0.15, "tp": 0.50, "sl": 2.00, "exit_dte": 0, "min_ivr": 20.0, "trend": True},
        {"name": "Defined-Risk Only 15Δ (50% TP, No Stop Loss, 21 DTE, IVR>=20)", "delta": 0.15, "tp": 0.50, "sl": 10.0, "exit_dte": 21, "min_ivr": 20.0, "trend": True},
    ]

    results = []
    print("\n" + "=" * 80)
    print("🏆 RUNNING QUANTITATIVE PARAMETER TOURNAMENT (2015-2026)")
    print("=" * 80)
    print(f"{'Scenario':<42} | {'Win%':<6} | {'PF':<5} | {'Trades':<6} | {'Expectancy':<10} | {'MaxDD%':<6} | {'Net PnL':<11}")
    print("-" * 80)

    for sc in scenarios:
        cfg = BacktestConfig(
            target_delta=sc["delta"],
            take_profit_pct=sc["tp"],
            stop_loss_pct=sc["sl"],
            exit_dte=sc["exit_dte"],
            min_iv_rank=sc["min_ivr"],
            require_trend=sc["trend"],
        )
        tester = HistoricalOptionsBacktester(cfg)
        res = tester.run_backtest()
        s = res["summary"]
        results.append({"config": sc, "summary": s})
        print(
            f"{sc['name']:<42} | {s['win_rate_pct']:<5.1f}% | {s['profit_factor']:<5.2f} | {s['total_trades']:<6} | ${s['expectancy_per_trade']:<9.2f} | {s['max_drawdown_pct']:<5.1f}% | ${s['total_net_pnl']:<10,.2f}"
        )
    print("=" * 80)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run 10-year historical options credit spread backtest.")
    parser.add_argument("--start", default="2015-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2026-09-01", help="End date (YYYY-MM-DD)")
    parser.add_argument("--capital", type=float, default=100000.0, help="Initial capital ($)")
    parser.add_argument("--risk-pct", type=float, default=0.02, help="Risk per trade as pct of capital")
    parser.add_argument("--min-iv-rank", type=float, default=20.0, help="Minimum IV rank")
    parser.add_argument("--tournament", action="store_true", help="Run multi-scenario parameter tournament")
    parser.add_argument("--output", type=str, default="data/audit/backtest_10yr_results.json")
    args = parser.parse_args()

    if args.tournament:
        tournament_results = run_tournament()
        out_path = REPO_ROOT / "data" / "audit" / "backtest_tournament_results.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(tournament_results, f, indent=2)
        print(f"\n✅ Tournament results saved to: {out_path}")
        return

    config = BacktestConfig(
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        risk_per_trade_pct=args.risk_pct,
        min_iv_rank=args.min_iv_rank,
    )

    print(f"🚀 Starting 10-Year Options Backtest for SPY ({args.start} to {args.end})...")
    tester = HistoricalOptionsBacktester(config)
    results = tester.run_backtest()

    out_path = REPO_ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    summary = results["summary"]
    print("\n" + "=" * 60)
    print("📊 10-YEAR HISTORICAL OPTIONS BACKTEST RESULTS (SPY PUT CREDIT)")
    print("=" * 60)
    print(f"Period:              {summary['period']}")
    print(f"Initial Capital:     ${summary['initial_capital']:,.2f}")
    print(f"Final Capital:       ${summary['final_capital']:,.2f}")
    print(f"Total Net PnL:       ${summary['total_net_pnl']:,.2f} (+{summary['total_return_pct']:.1f}%)")
    print(f"CAGR:                {summary['cagr_pct']:.2f}%")
    print(f"Max Drawdown:        {summary['max_drawdown_pct']:.2f}%")
    print(f"Sharpe Ratio:        {summary['sharpe_ratio']:.2f}")
    print(f"Sortino Ratio:       {summary['sortino_ratio']:.2f}")
    print("-" * 60)
    print(f"Total Trades:        {summary['total_trades']}")
    print(f"Wins / Losses:       {summary['wins']} Wins / {summary['losses']} Losses")
    print(f"Win Rate:            {summary['win_rate_pct']:.2f}%")
    print(f"Profit Factor:       {summary['profit_factor']:.2f}")
    print(f"Avg Win / Avg Loss:  ${summary['avg_win']:,.2f} / ${summary['avg_loss']:,.2f}")
    print(f"Expectancy:          ${summary['expectancy_per_trade']:,.2f} per trade")
    print("=" * 60)
    print("\n📅 Yearly Breakdown:")
    for yr, data in summary["yearly_performance"].items():
        print(f"  {yr}: {data['trades']} trades | WR: {data['win_rate_pct']}% | Net: ${data['total_pnl']:,.2f}")
    print(f"\n✅ Full results saved to: {out_path}")


if __name__ == "__main__":
    main()
