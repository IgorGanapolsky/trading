"""
REIT Strategy - Smart Income & Growth

Implements a quantitative approach to REIT investing by combining
momentum, yield, and macroeconomic regime detection.

Logic:
1.  **Regime Detection**: Uses Treasury yields (via FredCollector) to classify
    market as 'Rising Rates' (Defensive) or 'Falling/Stable' (Growth).
2.  **Universe Selection**: Dynamic basket of top liquid REITs across sectors.
3.  **Ranking**: Ranks assets by Momentum (3-month return) and Yield.
4.  **Selection**: Buys top 2-3 REITs that match the current regime.

Author: Trading System
Created: December 2025
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from src.core.alpaca_trader import AlpacaTrader
from src.rag.collectors import FredCollector
from src.strategies.registry import StrategyInterface
from src.utils.market_data import get_market_data_provider
from src.utils.technical_indicators import calculate_technical_score

logger = logging.getLogger(__name__)


@dataclass
class ReitSignal:
    symbol: str
    score: float
    dividend_yield: float
    sector: str
    action: str = "hold"
    weight: float = 0.0


class ReitStrategy(StrategyInterface):
    """
    Quantitative REIT strategy focusing on regime-based sector rotation.
    """

    # Liquid REIT Universe by Sector
    SECTOR_MAP = {
        "Growth": ["AMT", "CCI", "DLR", "EQIX", "PLD"],  # Tech, Towers, Industrial
        "Defensive": ["O", "VICI", "PSA", "WELL", "Dlr"],  # Retail, Healthcare, Storage
        "Residential": ["AVB", "EQR", "INVH"],  # Apartments
    }

    def __init__(self, trader: AlpacaTrader | None = None):
        self._name = "reit_smart_income"
        self.trader = trader
        self.market_data = get_market_data_provider()
        self.fred = FredCollector()

        # Configuration
        self.daily_allocation = float(os.getenv("REIT_DAILY_ALLOCATION", "10.0"))
        self.min_yield = float(os.getenv("REIT_MIN_YIELD", "0.03"))
        self.momentum_window = 60  # days

    @property
    def name(self) -> str:
        return self._name

    def get_config(self) -> dict[str, Any]:
        return {
            "daily_allocation": self.daily_allocation,
            "min_yield": self.min_yield,
            "universe_size": sum(len(v) for v in self.SECTOR_MAP.values()),
        }

    def _get_regime(self) -> str:
        """Determine interest rate regime."""
        try:
            # Fetch 10-year yield
            data = self.fred.get_series("DGS10", limit=20)
            if not data or "value" not in data[0]:
                return "Neutral"

            current = float(data[0]["value"])
            past = float(data[-1]["value"])

            if current > past * 1.05:
                return "Rising Rates"  # Bearish for long duration
            elif current < past * 0.95:
                return "Falling Rates"  # Bullish for growth
            else:
                return "Neutral"
        except Exception as e:
            logger.warning(f"Failed to detect rate regime: {e}")
            return "Neutral"

    def generate_signals(self, data: Any = None) -> list[dict[str, Any]]:
        """Generate buy/sell signals for REITs."""
        regime = self._get_regime()
        logger.info(f"REIT Regime Detected: {regime}")

        # Select universe based on regime
        if regime == "Rising Rates":
            universe = self.SECTOR_MAP["Defensive"] + self.SECTOR_MAP["Residential"]
        elif regime == "Falling Rates":
            universe = self.SECTOR_MAP["Growth"] + self.SECTOR_MAP["Defensive"]
        else:
            # Neutral: Mix of best
            universe = [t for cat in self.SECTOR_MAP.values() for t in cat]

        signals = []

        for symbol in universe:
            try:
                # Fetch price data
                bars = self.market_data.get_daily_bars(symbol, lookback_days=100)
                if bars.data.empty:
                    continue

                # Calculate Momentum (Score)
                score, _ = calculate_technical_score(bars.data, symbol)

                # Fetch Yield (Using Yahoo via market provider fallback or direct check)
                # Note: Assuming market_data handles metadata or we calculate rough yield
                # For now, we rely on technical score + regime

                signals.append(
                    {
                        "symbol": symbol,
                        "action": "buy" if score > 0 else "hold",
                        "strength": score,
                        "regime": regime,
                    }
                )

            except Exception as e:
                logger.warning(f"Failed to analyze {symbol}: {e}")

        # Sort by strength
        signals.sort(key=lambda x: x["strength"], reverse=True)
        return signals[:3]  # Top 3

    def execute_daily(self, amount: float = 0.0) -> None:
        """Execute strategy."""
        if not self.trader:
            logger.error("No trader initialized")
            return

        allocation = amount or self.daily_allocation
        if allocation < 2.0:
            logger.info(f"Skipping REIT execution: Allocation ${allocation} too low")
            return

        signals = self.generate_signals()
        if not signals:
            logger.warning("No REIT signals generated")
            return

        # Split allocation among top picks
        per_trade = allocation / len(signals)

        for sig in signals:
            if sig["strength"] > 0:
                logger.info(f"Executing REIT Buy: {sig['symbol']} (${per_trade:.2f})")
                try:
                    self.trader.execute_order(
                        symbol=sig["symbol"],
                        amount_usd=per_trade,
                        side="buy",
                        tier="T1_CORE",  # Treat as core allocation
                    )
                except Exception as e:
                    logger.error(f"Failed to buy {sig['symbol']}: {e}")
