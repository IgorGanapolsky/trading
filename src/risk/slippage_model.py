"""
Slippage Model for Realistic Backtesting

Models real-world execution costs including:
- Bid-ask spread slippage
- Market impact (price movement from order)
- Latency-based slippage
- Volume-dependent slippage

Critical for preventing overly optimistic backtest results.
Without slippage modeling, backtests can overestimate returns by 20-50%.

Author: Trading System
Created: 2025-12-02
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class SlippageModelType(Enum):
    """Types of slippage models."""

    FIXED = "fixed"  # Fixed percentage per trade
    VOLUME_BASED = "volume_based"  # Scales with trade size vs ADV
    VOLATILITY_BASED = "volatility_based"  # Scales with volatility
    COMPREHENSIVE = "comprehensive"  # Combines all factors


@dataclass
class SlippageResult:
    """Result of slippage calculation."""

    base_price: float
    executed_price: float
    slippage_amount: float
    slippage_pct: float
    components: dict

    @property
    def total_cost(self) -> float:
        """Total slippage cost in dollars per share."""
        return abs(self.executed_price - self.base_price)


class SlippageModel:
    """
    Models realistic execution slippage for backtesting.

    Components:
    1. Bid-Ask Spread: Half-spread cost on each side
    2. Market Impact: Price movement from order pressure
    3. Latency: Price drift during execution delay
    4. Volatility: Higher slippage in volatile conditions

    Args:
        model_type: Type of slippage model to use
        base_spread_bps: Base bid-ask spread in basis points (default: 5 bps for liquid ETFs)
        market_impact_bps: Market impact coefficient in basis points
        latency_ms: Assumed execution latency in milliseconds
        volatility_multiplier: How much volatility affects slippage
    """

    # Typical spreads by asset class (in basis points)
    ASSET_SPREADS = {
        "SPY": 1,  # Very liquid
        "QQQ": 1,
        "IWM": 2,
        "VOO": 2,
        "VTI": 2,
        "BND": 3,
        "LARGE_CAP": 5,  # Default for large caps
        "MID_CAP": 10,
        "SMALL_CAP": 20,
        "MICRO_CAP": 50,
        "OPTIONS": 100,
    }

    def __init__(
        self,
        model_type: SlippageModelType = SlippageModelType.COMPREHENSIVE,
        base_spread_bps: float = 5.0,
        market_impact_bps: float = 10.0,
        latency_ms: float = 100.0,
        volatility_multiplier: float = 1.5,
    ):
        self.model_type = model_type
        self.base_spread_bps = base_spread_bps
        self.market_impact_bps = market_impact_bps
        self.latency_ms = latency_ms
        self.volatility_multiplier = volatility_multiplier

        logger.info(
            f"SlippageModel initialized: {model_type.value}, "
            f"base_spread={base_spread_bps}bps, impact={market_impact_bps}bps"
        )

    def calculate_slippage(
        self,
        price: float,
        quantity: float,
        side: str,  # "buy" or "sell"
        symbol: Optional[str] = None,
        volume: Optional[float] = None,  # Average daily volume
        volatility: Optional[float] = None,  # Daily volatility (e.g., 0.02 = 2%)
        order_type: str = "market",
    ) -> SlippageResult:
        """
        Calculate slippage for a trade.

        Args:
            price: Base price (mid-market or last trade)
            quantity: Number of shares
            side: "buy" or "sell"
            symbol: Ticker symbol (for asset-specific spreads)
            volume: Average daily volume for market impact
            volatility: Daily volatility for vol-based slippage
            order_type: "market" or "limit"

        Returns:
            SlippageResult with execution price and breakdown
        """
        if self.model_type == SlippageModelType.FIXED:
            return self._fixed_slippage(price, quantity, side, symbol)
        elif self.model_type == SlippageModelType.VOLUME_BASED:
            return self._volume_based_slippage(price, quantity, side, symbol, volume)
        elif self.model_type == SlippageModelType.VOLATILITY_BASED:
            return self._volatility_based_slippage(
                price, quantity, side, symbol, volatility
            )
        else:  # COMPREHENSIVE
            return self._comprehensive_slippage(
                price, quantity, side, symbol, volume, volatility, order_type
            )

    def _fixed_slippage(
        self,
        price: float,
        quantity: float,
        side: str,
        symbol: Optional[str],
    ) -> SlippageResult:
        """Fixed percentage slippage."""
        # Get symbol-specific spread or use default
        spread_bps = self._get_spread_bps(symbol)

        # Half spread on entry, half on exit
        slippage_pct = spread_bps / 10000  # Convert bps to decimal

        # Direction: buy = pay more, sell = receive less
        direction = 1 if side.lower() == "buy" else -1
        slippage_amount = price * slippage_pct * direction
        executed_price = price + slippage_amount

        return SlippageResult(
            base_price=price,
            executed_price=executed_price,
            slippage_amount=slippage_amount,
            slippage_pct=slippage_pct * 100,
            components={"spread": spread_bps},
        )

    def _volume_based_slippage(
        self,
        price: float,
        quantity: float,
        side: str,
        symbol: Optional[str],
        volume: Optional[float],
    ) -> SlippageResult:
        """Slippage that scales with order size relative to volume."""
        spread_bps = self._get_spread_bps(symbol)

        # Market impact: sqrt of (order_size / ADV)
        # Higher participation = higher impact
        impact_bps = 0.0
        if volume and volume > 0:
            notional = price * quantity
            adv_notional = price * volume
            participation_rate = notional / adv_notional

            # Square root market impact model (empirically validated)
            # Impact ≈ σ * √(V/ADV) where σ is volatility proxy
            impact_bps = self.market_impact_bps * np.sqrt(participation_rate) * 100

        total_bps = spread_bps + impact_bps
        slippage_pct = total_bps / 10000

        direction = 1 if side.lower() == "buy" else -1
        slippage_amount = price * slippage_pct * direction
        executed_price = price + slippage_amount

        return SlippageResult(
            base_price=price,
            executed_price=executed_price,
            slippage_amount=slippage_amount,
            slippage_pct=slippage_pct * 100,
            components={
                "spread": spread_bps,
                "market_impact": impact_bps,
                "participation_rate": participation_rate if volume else 0,
            },
        )

    def _volatility_based_slippage(
        self,
        price: float,
        quantity: float,
        side: str,
        symbol: Optional[str],
        volatility: Optional[float],
    ) -> SlippageResult:
        """Slippage that scales with volatility."""
        spread_bps = self._get_spread_bps(symbol)

        # Higher volatility = wider effective spread
        vol_adjustment = 1.0
        if volatility and volatility > 0:
            # Typical daily vol is ~1-2% for stocks
            # Scale slippage: 2x vol = 1.5x slippage
            baseline_vol = 0.015  # 1.5% daily vol as baseline
            vol_adjustment = 1 + (volatility / baseline_vol - 1) * self.volatility_multiplier
            vol_adjustment = max(0.5, min(3.0, vol_adjustment))  # Cap between 0.5x-3x

        adjusted_spread_bps = spread_bps * vol_adjustment
        slippage_pct = adjusted_spread_bps / 10000

        direction = 1 if side.lower() == "buy" else -1
        slippage_amount = price * slippage_pct * direction
        executed_price = price + slippage_amount

        return SlippageResult(
            base_price=price,
            executed_price=executed_price,
            slippage_amount=slippage_amount,
            slippage_pct=slippage_pct * 100,
            components={
                "spread": spread_bps,
                "volatility_adjustment": vol_adjustment,
                "adjusted_spread": adjusted_spread_bps,
            },
        )

    def _comprehensive_slippage(
        self,
        price: float,
        quantity: float,
        side: str,
        symbol: Optional[str],
        volume: Optional[float],
        volatility: Optional[float],
        order_type: str,
    ) -> SlippageResult:
        """
        Comprehensive slippage model combining all factors.

        Total Slippage = Spread + Market Impact + Latency + Volatility Adjustment
        """
        # 1. Base spread
        spread_bps = self._get_spread_bps(symbol)

        # 2. Market impact (volume-based)
        impact_bps = 0.0
        participation_rate = 0.0
        if volume and volume > 0:
            notional = price * quantity
            adv_notional = price * volume
            participation_rate = min(notional / adv_notional, 0.1)  # Cap at 10% of ADV

            # Square-root market impact
            impact_bps = self.market_impact_bps * np.sqrt(participation_rate) * 100

        # 3. Latency cost
        # Price can move during execution delay
        latency_bps = 0.0
        if volatility and volatility > 0:
            # Estimate price movement during latency window
            # Using intraday volatility ≈ daily_vol / sqrt(trading_minutes)
            trading_minutes = 390  # 6.5 hours
            latency_minutes = self.latency_ms / 60000
            intraday_vol = volatility / np.sqrt(trading_minutes)
            latency_bps = intraday_vol * np.sqrt(latency_minutes) * 10000

        # 4. Volatility adjustment
        vol_multiplier = 1.0
        if volatility and volatility > 0:
            baseline_vol = 0.015
            vol_multiplier = 1 + (volatility / baseline_vol - 1) * 0.5
            vol_multiplier = max(0.5, min(2.0, vol_multiplier))

        # 5. Order type adjustment
        order_multiplier = 1.0 if order_type == "market" else 0.5  # Limit orders have less slippage

        # Combine all components
        total_bps = (spread_bps + impact_bps + latency_bps) * vol_multiplier * order_multiplier
        slippage_pct = total_bps / 10000

        direction = 1 if side.lower() == "buy" else -1
        slippage_amount = price * slippage_pct * direction
        executed_price = price + slippage_amount

        return SlippageResult(
            base_price=price,
            executed_price=executed_price,
            slippage_amount=slippage_amount,
            slippage_pct=slippage_pct * 100,
            components={
                "spread_bps": spread_bps,
                "market_impact_bps": impact_bps,
                "latency_bps": latency_bps,
                "volatility_multiplier": vol_multiplier,
                "order_multiplier": order_multiplier,
                "participation_rate": participation_rate,
                "total_bps": total_bps,
            },
        )

    def _get_spread_bps(self, symbol: Optional[str]) -> float:
        """Get bid-ask spread for a symbol."""
        if symbol and symbol.upper() in self.ASSET_SPREADS:
            return self.ASSET_SPREADS[symbol.upper()]
        return self.base_spread_bps

    def estimate_round_trip_cost(
        self,
        price: float,
        quantity: float,
        symbol: Optional[str] = None,
        volume: Optional[float] = None,
        volatility: Optional[float] = None,
    ) -> float:
        """
        Estimate total round-trip cost (entry + exit).

        Args:
            price: Trade price
            quantity: Number of shares
            symbol: Ticker symbol
            volume: Average daily volume
            volatility: Daily volatility

        Returns:
            Total round-trip slippage cost as percentage
        """
        entry = self.calculate_slippage(
            price, quantity, "buy", symbol, volume, volatility
        )
        exit_slip = self.calculate_slippage(
            price, quantity, "sell", symbol, volume, volatility
        )

        return entry.slippage_pct + exit_slip.slippage_pct


# Convenience functions
def get_default_slippage_model() -> SlippageModel:
    """Get default slippage model for backtesting."""
    return SlippageModel(
        model_type=SlippageModelType.COMPREHENSIVE,
        base_spread_bps=5.0,
        market_impact_bps=10.0,
        latency_ms=100.0,
    )


def apply_slippage(
    price: float,
    quantity: float,
    side: str,
    symbol: Optional[str] = None,
) -> float:
    """Quick slippage application for simple use cases."""
    model = get_default_slippage_model()
    result = model.calculate_slippage(price, quantity, side, symbol)
    return result.executed_price


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("SLIPPAGE MODEL DEMO")
    print("=" * 80)

    model = SlippageModel()

    # Test scenarios
    scenarios = [
        {"symbol": "SPY", "price": 450.0, "quantity": 100, "volume": 80_000_000},
        {"symbol": "QQQ", "price": 380.0, "quantity": 50, "volume": 50_000_000},
        {"symbol": "AAPL", "price": 175.0, "quantity": 200, "volume": 60_000_000},
        {"symbol": "TSLA", "price": 250.0, "quantity": 100, "volume": 100_000_000, "volatility": 0.04},
    ]

    print("\nSlippage Analysis:")
    print("-" * 80)

    for s in scenarios:
        result = model.calculate_slippage(
            price=s["price"],
            quantity=s["quantity"],
            side="buy",
            symbol=s["symbol"],
            volume=s.get("volume"),
            volatility=s.get("volatility", 0.02),
        )

        round_trip = model.estimate_round_trip_cost(
            price=s["price"],
            quantity=s["quantity"],
            symbol=s["symbol"],
            volume=s.get("volume"),
            volatility=s.get("volatility", 0.02),
        )

        print(f"\n{s['symbol']}:")
        print(f"  Base Price: ${s['price']:.2f}")
        print(f"  Executed Price: ${result.executed_price:.4f}")
        print(f"  Slippage: {result.slippage_pct:.4f}% (${result.slippage_amount:.4f})")
        print(f"  Round-Trip Cost: {round_trip:.4f}%")
        print(f"  Components: {result.components}")
