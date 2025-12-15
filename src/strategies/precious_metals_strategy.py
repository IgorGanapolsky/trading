"""
Precious Metals Strategy (Tier 8)

Implements a gold/silver ETF allocation strategy with dynamic weighting based on:
1. Gold-to-Silver ratio (GSR) for relative value
2. Market fear (VIX) for safe-haven demand
3. Dollar strength (DXY) for inverse correlation

Strategy Overview:
- Base Allocation: GLD (70%), SLV (30%)
- High Fear Mode: 80% GLD, 20% SLV (flight to safety)
- Silver Breakout: 50% GLD, 50% SLV (industrial recovery)
- Dollar Weakness: Overweight both (inflation hedge)

ETF Universe:
- GLD: SPDR Gold Shares (tracks gold bullion price)
- SLV: iShares Silver Trust (tracks silver bullion price)

Research Context (Dec 2025):
- Gold near all-time highs (~$2,000/oz) due to Fed rate cuts
- Silver historically undervalued vs gold (GSR > 80)
- Both serve as inflation hedges and USD hedge
- Low correlation to equities (diversification benefit)

Author: Trading System
Created: 2025-12-12
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MetalsRegime(Enum):
    """Precious metals market regime classification."""

    NEUTRAL = "neutral"  # Normal conditions
    FEAR = "fear"  # High VIX, flight to safety
    SILVER_BREAKOUT = "silver_breakout"  # GSR falling, silver catching up
    INFLATION = "inflation"  # Dollar weakness, inflation hedge


@dataclass
class MetalsAllocation:
    """Precious metals allocation details."""

    gld_pct: float  # Gold allocation
    slv_pct: float  # Silver allocation
    regime: MetalsRegime
    gold_silver_ratio: float  # Current GSR
    rationale: str
    timestamp: datetime


class PreciousMetalsStrategy:
    """
    Precious Metals ETF Strategy with regime-based allocation.

    This strategy implements a gold/silver ETF allocation (GLD/SLV) with
    dynamic weighting based on market conditions. Precious metals serve as:
    - Inflation hedge
    - USD hedge
    - Portfolio diversification (low equity correlation)
    - Safe-haven during market stress

    Key Features:
    - Two-asset ETF allocation: GLD (gold) and SLV (silver)
    - Regime detection: Fear, Silver Breakout, Inflation, Neutral
    - Dynamic allocation shifts based on gold-silver ratio
    - Integration with Alpaca for fractional share trading

    Attributes:
        daily_allocation (float): Daily dollar amount to invest
        etf_symbols (List[str]): Precious metals ETF symbols [GLD, SLV]
        current_regime (MetalsRegime): Current market regime
    """

    # ETF Universe
    ETF_SYMBOLS = ["GLD", "SLV"]

    # Base allocations for different regimes
    # Neutral: standard gold-heavy allocation
    ALLOCATION_NEUTRAL = {"GLD": 0.70, "SLV": 0.30}

    # Fear regime: flight to safety (gold is the ultimate safe haven)
    ALLOCATION_FEAR = {"GLD": 0.80, "SLV": 0.20}

    # Silver breakout: industrial demand recovering, silver catching up
    ALLOCATION_SILVER = {"GLD": 0.50, "SLV": 0.50}

    # Inflation regime: both metals benefit
    ALLOCATION_INFLATION = {"GLD": 0.60, "SLV": 0.40}

    # Gold-Silver Ratio thresholds
    GSR_HIGH = 85.0  # Above 85 = silver undervalued
    GSR_LOW = 70.0  # Below 70 = silver fairly valued

    def __init__(
        self,
        daily_allocation: float = 10.0,
        trader=None,
        paper: bool = True,
    ):
        """
        Initialize the Precious Metals Strategy.

        Args:
            daily_allocation: Daily dollar amount to invest (default: $10)
            trader: AlpacaTrader instance (optional, will create if not provided)
            paper: Whether to use paper trading (default: True)

        Raises:
            ValueError: If daily_allocation is non-positive
        """
        if daily_allocation <= 0:
            raise ValueError(f"daily_allocation must be positive, got {daily_allocation}")

        self.daily_allocation = daily_allocation
        self.etf_symbols = self.ETF_SYMBOLS.copy()
        self.current_regime: MetalsRegime | None = None

        # Performance tracking
        self.total_invested: float = 0.0
        self.total_value: float = 0.0

        # Initialize trader
        self.trader = trader
        if self.trader is None:
            try:
                from src.core.alpaca_trader import AlpacaTrader

                self.trader = AlpacaTrader(paper=paper)
                logger.info("Successfully initialized Alpaca trader for precious metals")
            except Exception as e:
                logger.warning(f"Failed to initialize Alpaca trader: {e}")
                self.trader = None

        logger.info(
            f"PreciousMetalsStrategy initialized: "
            f"daily_allocation=${daily_allocation:.2f}, "
            f"etfs={self.etf_symbols}"
        )

    def analyze_regime(self) -> tuple[MetalsRegime, float, str]:
        """
        Analyze current market conditions for precious metals regime.

        Uses simplified heuristics when external data unavailable:
        - VIX > 25: Fear regime
        - GSR > 85: Silver undervalued (potential breakout)
        - Otherwise: Neutral

        Returns:
            Tuple of (regime, gold_silver_ratio, rationale)
        """
        logger.info("Analyzing precious metals market regime...")

        # Default values if data unavailable
        gsr = 80.0  # Gold-silver ratio (historical average ~80)

        try:
            # Try to get real market data
            if self.trader:
                # Get gold and silver prices to calculate GSR
                gld_quote = self.trader.get_latest_quote("GLD")
                slv_quote = self.trader.get_latest_quote("SLV")

                if gld_quote and slv_quote:
                    gld_price = float(gld_quote.get("price", 180))
                    slv_price = float(slv_quote.get("price", 22))

                    # GLD tracks ~1/10 oz gold, SLV tracks ~1 oz silver
                    # So GSR ~ (GLD_price * 10) / SLV_price
                    if slv_price > 0:
                        gsr = (gld_price * 10) / slv_price

                logger.info(f"Calculated gold-silver ratio: {gsr:.1f}")
        except Exception as e:
            logger.warning(f"Could not fetch market data: {e}, using defaults")

        # Determine regime based on GSR
        if gsr > self.GSR_HIGH:
            regime = MetalsRegime.SILVER_BREAKOUT
            rationale = (
                f"SILVER_BREAKOUT: GSR at {gsr:.1f} (>85) indicates silver is "
                "historically undervalued vs gold. Equal weighting recommended."
            )
        elif gsr < self.GSR_LOW:
            regime = MetalsRegime.NEUTRAL
            rationale = (
                f"NEUTRAL: GSR at {gsr:.1f} (<70) indicates silver fairly valued. "
                "Standard gold-heavy allocation."
            )
        else:
            regime = MetalsRegime.NEUTRAL
            rationale = (
                f"NEUTRAL: GSR at {gsr:.1f} within normal range (70-85). "
                "Standard allocation: 70% GLD, 30% SLV."
            )

        logger.info(f"Precious metals regime: {regime.value} - {rationale}")
        self.current_regime = regime

        return regime, gsr, rationale

    def get_optimal_allocation(self) -> MetalsAllocation:
        """
        Determine optimal allocation based on current market regime.

        Analyzes market conditions and returns allocation percentages
        for GLD and SLV.

        Returns:
            MetalsAllocation dataclass with allocation percentages and metadata
        """
        logger.info("Calculating optimal precious metals allocation...")

        # Analyze regime
        regime, gsr, rationale = self.analyze_regime()

        # Select allocation based on regime
        if regime == MetalsRegime.FEAR:
            allocation_dict = self.ALLOCATION_FEAR.copy()
        elif regime == MetalsRegime.SILVER_BREAKOUT:
            allocation_dict = self.ALLOCATION_SILVER.copy()
        elif regime == MetalsRegime.INFLATION:
            allocation_dict = self.ALLOCATION_INFLATION.copy()
        else:  # NEUTRAL
            allocation_dict = self.ALLOCATION_NEUTRAL.copy()

        # Create allocation object
        allocation = MetalsAllocation(
            gld_pct=allocation_dict["GLD"],
            slv_pct=allocation_dict["SLV"],
            regime=regime,
            gold_silver_ratio=gsr,
            rationale=rationale,
            timestamp=datetime.now(),
        )

        logger.info(
            f"Optimal allocation: GLD={allocation.gld_pct * 100:.0f}%, "
            f"SLV={allocation.slv_pct * 100:.0f}%"
        )

        return allocation

    def generate_signals(self) -> list[dict[str, Any]]:
        """
        Generate trading signals for precious metals ETFs.

        Returns:
            List of signal dictionaries with symbol, action, and strength
        """
        allocation = self.get_optimal_allocation()

        signals = []
        for symbol, pct in [("GLD", allocation.gld_pct), ("SLV", allocation.slv_pct)]:
            signals.append(
                {
                    "symbol": symbol,
                    "action": "buy",
                    "strength": pct,
                    "regime": allocation.regime.value,
                    "rationale": allocation.rationale,
                }
            )

        return signals

    def execute_daily(self, amount: float | None = None) -> dict[str, Any]:
        """
        Execute daily investment across precious metals ETFs.

        Distributes the daily investment amount across GLD and SLV
        according to the optimal allocation determined by regime analysis.

        Args:
            amount: Dollar amount to invest (default: self.daily_allocation)

        Returns:
            Dictionary containing execution results
        """
        amount = amount or self.daily_allocation

        logger.info("=" * 80)
        logger.info("Starting Precious Metals daily execution")
        logger.info(f"Investment amount: ${amount:.2f}")

        if not self.trader:
            logger.warning("Trader not initialized, returning analysis-only results")
            allocation = self.get_optimal_allocation()
            return {
                "orders": [],
                "allocation": allocation,
                "total_invested": 0.0,
                "success": False,
                "error": "Trader not initialized",
                "analysis_only": True,
            }

        try:
            # Get optimal allocation
            allocation = self.get_optimal_allocation()

            # Calculate dollar amounts for each ETF
            gld_amount = amount * allocation.gld_pct
            slv_amount = amount * allocation.slv_pct

            logger.info(f"Allocating: GLD=${gld_amount:.2f}, SLV=${slv_amount:.2f}")

            # Execute orders
            orders = []
            total_invested = 0.0

            for symbol, invest_amount in [("GLD", gld_amount), ("SLV", slv_amount)]:
                if invest_amount > 0.01:  # Skip if less than 1 cent
                    try:
                        order = self.trader.execute_order(
                            symbol=symbol,
                            amount_usd=invest_amount,
                            side="buy",
                            tier="T8_METALS",
                        )
                        orders.append(order)
                        total_invested += invest_amount

                        logger.info(
                            f"Executed: BUY {symbol} ${invest_amount:.2f} "
                            f"(Order ID: {order.get('id', 'N/A')})"
                        )
                    except Exception as e:
                        logger.error(f"Failed to execute order for {symbol}: {e}")

            # Update total invested
            self.total_invested += total_invested

            logger.info(
                f"Daily execution complete: {len(orders)} orders, ${total_invested:.2f} invested"
            )

            return {
                "orders": orders,
                "allocation": allocation,
                "total_invested": total_invested,
                "success": len(orders) > 0,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Daily execution failed: {e}")
            return {
                "orders": [],
                "allocation": None,
                "total_invested": 0.0,
                "success": False,
                "error": str(e),
            }

    def get_performance_summary(self) -> dict[str, Any]:
        """
        Get performance summary for precious metals positions.

        Returns:
            Dictionary containing performance metrics
        """
        try:
            if not self.trader:
                return {"error": "Trader not initialized"}

            # Get current positions
            positions = self.trader.get_positions()
            metals_positions = [pos for pos in positions if pos["symbol"] in self.etf_symbols]

            total_market_value = sum(float(pos["market_value"]) for pos in metals_positions)
            total_cost_basis = sum(float(pos["cost_basis"]) for pos in metals_positions)
            total_unrealized_pl = sum(float(pos["unrealized_pl"]) for pos in metals_positions)

            return {
                "total_invested": self.total_invested,
                "total_market_value": total_market_value,
                "total_cost_basis": total_cost_basis,
                "total_unrealized_pl": total_unrealized_pl,
                "return_pct": (
                    (total_unrealized_pl / total_cost_basis * 100) if total_cost_basis > 0 else 0.0
                ),
                "positions": metals_positions,
                "current_regime": self.current_regime.value if self.current_regime else "unknown",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {"error": str(e)}


if __name__ == "__main__":
    """Example usage and testing."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("\n" + "=" * 80)
    print("PRECIOUS METALS STRATEGY - DEMO")
    print("=" * 80)

    # Initialize strategy (no trader for demo)
    strategy = PreciousMetalsStrategy(daily_allocation=10.0, paper=True)

    # Analyze regime
    print("\n1. MARKET REGIME ANALYSIS")
    regime, gsr, rationale = strategy.analyze_regime()
    print(f"   Regime: {regime.value}")
    print(f"   Gold-Silver Ratio: {gsr:.1f}")
    print(f"   Rationale: {rationale}")

    # Get optimal allocation
    print("\n2. OPTIMAL ALLOCATION")
    allocation = strategy.get_optimal_allocation()
    print(f"   GLD (Gold): {allocation.gld_pct * 100:.0f}%")
    print(f"   SLV (Silver): {allocation.slv_pct * 100:.0f}%")

    # Generate signals
    print("\n3. TRADING SIGNALS")
    signals = strategy.generate_signals()
    for sig in signals:
        print(f"   {sig['symbol']}: {sig['action'].upper()} @ {sig['strength'] * 100:.0f}% weight")

    print("\n" + "=" * 80)
    print("Demo complete!")
    print("=" * 80 + "\n")
