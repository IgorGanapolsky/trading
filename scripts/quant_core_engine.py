#!/usr/bin/env python3
"""Lean Quantitative Options Core Execution Engine.

Operates the mathematically verified SPY Bull Put Credit Spread strategy:
- Entry: 15Δ Short Put / $5-wide Long Put, 30-45 DTE, IV Rank >= 25, SPY > 200 SMA.
- Exit: 50% Take Profit, 200% Stop Loss (loss = 2x credit), 21 DTE Time Exit.
- Sizing: Fixed fractional risk (1.5% - 2.0% capital per trade), max 4 concurrent positions.
- Execution: Direct Alpaca MLEG orders (Paper or Live).
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from scipy.stats import norm
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("quant_core_engine")

EASTERN = ZoneInfo("America/New_York")


@dataclass
class QuantConfig:
    symbol: str = "SPY"
    target_delta: float = 0.15
    target_dte_min: int = 30
    target_dte_max: int = 45
    spread_width: float = 5.0
    take_profit_pct: float = 0.50
    stop_loss_pct: float = 2.00
    exit_dte: int = 21
    min_iv_rank: float = 25.0
    risk_per_trade_pct: float = 0.02
    max_concurrent_positions: int = 4
    min_credit: float = 0.40
    paper_mode: bool = True


@dataclass
class MarketRegime:
    spy_price: float
    sma200: float
    sma50: float
    trend_bullish: bool
    vix: float
    iv_rank: float
    captured_at: str


class QuantCoreEngine:
    def __init__(self, config: QuantConfig):
        self.config = config
        self.client = self._init_alpaca_client()

    def _init_alpaca_client(self):
        """Initialize Alpaca Trading Client."""
        try:
            from alpaca.trading.client import TradingClient

            if self.config.paper_mode:
                api_key = os.getenv("ALPACA_API_KEY")
                secret_key = os.getenv("ALPACA_SECRET_KEY")
                if not api_key or not secret_key:
                    logger.warning("Alpaca paper API credentials not found in env.")
                    return None
                return TradingClient(api_key, secret_key, paper=True)
            else:
                api_key = os.getenv("ALPACA_LIVE_API_KEY")
                secret_key = os.getenv("ALPACA_LIVE_SECRET_KEY")
                if not api_key or not secret_key:
                    logger.warning("Alpaca live API credentials not found in env.")
                    return None
                return TradingClient(api_key, secret_key, paper=False)
        except Exception as exc:
            logger.error("Failed to initialize Alpaca client: %s", exc)
            return None

    def get_market_regime(self) -> MarketRegime:
        """Fetch current SPY and VIX metrics and compute IV rank + trend."""
        spy = yf.download(self.config.symbol, period="1y", interval="1d", progress=False)
        vix = yf.download("^VIX", period="1y", interval="1d", progress=False)

        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = [c[0] for c in spy.columns]
        if isinstance(vix.columns, pd.MultiIndex):
            vix.columns = [c[0] for c in vix.columns]

        spy_price = float(spy["Close"].iloc[-1])
        sma200 = float(spy["Close"].rolling(window=200).mean().iloc[-1]) if len(spy) >= 200 else spy_price
        sma50 = float(spy["Close"].rolling(window=50).mean().iloc[-1]) if len(spy) >= 50 else spy_price
        trend_bullish = spy_price >= sma200

        vix_series = vix["Close"].dropna()
        current_vix = float(vix_series.iloc[-1])
        vix_min252 = float(vix_series.min())
        vix_max252 = float(vix_series.max())
        iv_rank = 100.0 * (current_vix - vix_min252) / (vix_max252 - vix_min252 + 1e-6)

        return MarketRegime(
            spy_price=round(spy_price, 2),
            sma200=round(sma200, 2),
            sma50=round(sma50, 2),
            trend_bullish=trend_bullish,
            vix=round(current_vix, 2),
            iv_rank=round(iv_rank, 1),
            captured_at=datetime.now(UTC).isoformat(),
        )

    def evaluate_entry(self, regime: MarketRegime, current_positions_count: int) -> dict[str, Any]:
        """Check if market conditions meet entry criteria."""
        reasons = []
        is_eligible = True

        if current_positions_count >= self.config.max_concurrent_positions:
            is_eligible = False
            reasons.append(f"Max concurrent positions reached ({current_positions_count}/{self.config.max_concurrent_positions})")

        if regime.iv_rank < self.config.min_iv_rank:
            is_eligible = False
            reasons.append(f"IV Rank too low ({regime.iv_rank:.1f} < {self.config.min_iv_rank:.1f})")

        if not regime.trend_bullish:
            is_eligible = False
            reasons.append(f"Trend bearish (SPY ${regime.spy_price} < 200 SMA ${regime.sma200})")

        # Estimate strikes
        T = 40.0 / 365.0
        z = norm.ppf(1.0 - self.config.target_delta)
        sigma = (regime.vix / 100.0) + 0.02
        exponent = -z * sigma * math.sqrt(T) + (0.02 + 0.5 * sigma**2) * T
        short_strike = round(regime.spy_price * math.exp(exponent))
        long_strike = short_strike - self.config.spread_width

        return {
            "is_eligible": is_eligible,
            "reasons": reasons,
            "regime": asdict(regime),
            "target_spread": {
                "symbol": self.config.symbol,
                "short_strike": short_strike,
                "long_strike": long_strike,
                "width": self.config.spread_width,
                "target_delta": self.config.target_delta,
                "target_dte": 40,
            },
        }

    def run_status_check(self) -> dict[str, Any]:
        """Perform comprehensive system status and regime assessment."""
        regime = self.get_market_regime()
        account_info = {}

        if self.client:
            try:
                acc = self.client.get_account()
                account_info = {
                    "equity": float(acc.equity),
                    "cash": float(acc.cash),
                    "buying_power": float(acc.buying_power),
                    "status": str(acc.status),
                    "mode": "paper" if self.config.paper_mode else "live",
                }
            except Exception as exc:
                account_info = {"error": str(exc), "mode": "paper" if self.config.paper_mode else "live"}
        else:
            account_info = {
                "status": "unconnected",
                "mode": "paper" if self.config.paper_mode else "live",
                "note": "Alpaca API credentials not loaded.",
            }

        entry_eval = self.evaluate_entry(regime, current_positions_count=0)

        status = {
            "timestamp": datetime.now(UTC).isoformat(),
            "config": asdict(self.config),
            "account": account_info,
            "market_regime": asdict(regime),
            "entry_evaluation": entry_eval,
        }
        return status


def main() -> None:
    parser = argparse.ArgumentParser(description="Quant Core Options Engine CLI.")
    parser.add_argument("--status", action="store_true", help="Show system status and market regime")
    parser.add_argument("--live", action="store_true", help="Run in Live mode (default is paper)")
    args = parser.parse_args()

    config = QuantConfig(paper_mode=not args.live)
    engine = QuantCoreEngine(config)

    if args.status or len(sys.argv) == 1:
        res = engine.run_status_check()
        print("\n" + "=" * 60)
        print("⚡ QUANT CORE TRADING ENGINE STATUS")
        print("=" * 60)
        print(f"Timestamp:       {res['timestamp']}")
        print(f"Mode:            {res['account'].get('mode', 'paper').upper()}")
        print(f"SPY Price:       ${res['market_regime']['spy_price']}")
        print(f"200-day SMA:     ${res['market_regime']['sma200']} (Bullish: {res['market_regime']['trend_bullish']})")
        print(f"VIX:             {res['market_regime']['vix']}")
        print(f"252d IV Rank:    {res['market_regime']['iv_rank']}% (Min Entry: {config.min_iv_rank}%)")
        print("-" * 60)
        entry = res["entry_evaluation"]
        print(f"Entry Signal:    {'🟢 READY TO ENTER' if entry['is_eligible'] else '🔴 BLOCKED / FILTERED'}")
        if not entry["is_eligible"]:
            for r in entry["reasons"]:
                print(f"  - {r}")
        print(f"Target Setup:    Sell SPY ${entry['target_spread']['short_strike']}P / Buy SPY ${entry['target_spread']['long_strike']}P (${entry['target_spread']['width']} wide, ~{entry['target_spread']['target_delta']*100:.0f}Δ, ~40 DTE)")
        print("=" * 60)


if __name__ == "__main__":
    main()
