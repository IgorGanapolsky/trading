#!/usr/bin/env python3
"""
Fibonacci Support/Resistance Level Calculator (RLP-style)

Inspired by RLP V4.3 TradingView indicator - identifies institutional-grade
support/resistance levels for SPY iron condor strike validation.

Key Concepts:
- Identifies significant price phases (swing high → swing low)
- Applies Fibonacci retracement/extension levels
- Validates iron condor strikes against S/R levels
- Improves win rate by avoiding strikes near major levels

Usage:
    from fibonacci_sr import FibonacciSRCalculator
    calc = FibonacciSRCalculator()
    levels = await calc.get_spy_levels()
    validation = calc.validate_iron_condor_strikes(put_short=580, call_short=610, levels=levels)
"""

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx

# Fibonacci ratios (standard retracement + extensions)
FIBONACCI_RATIOS = {
    "0%": 0.0,
    "23.6%": 0.236,
    "38.2%": 0.382,
    "50%": 0.5,
    "61.8%": 0.618,
    "78.6%": 0.786,
    "100%": 1.0,
    "127.2%": 1.272,
    "161.8%": 1.618,
    "200%": 2.0,
}

# Strike proximity thresholds
SR_DANGER_ZONE_PCT = 0.01  # 1% - strikes within this of S/R are dangerous
SR_WARNING_ZONE_PCT = 0.02  # 2% - strikes within this get warning


@dataclass
class PricePhase:
    """Represents a significant price phase (swing high to swing low or vice versa)."""

    start_date: datetime
    end_date: datetime
    start_price: float
    end_price: float
    is_bullish: bool  # True if price moved up during phase
    duration_days: int
    magnitude_pct: float  # Percentage move

    @property
    def range(self) -> float:
        """Absolute price range of the phase."""
        return abs(self.end_price - self.start_price)


@dataclass
class FibonacciLevel:
    """A calculated Fibonacci level with metadata."""

    ratio_name: str
    ratio: float
    price: float
    level_type: str  # 'support' or 'resistance'
    strength: float  # 0-1, based on historical touches


@dataclass
class StrikeValidation:
    """Result of validating an iron condor strike against S/R levels."""

    strike: float
    is_valid: bool
    quality_score: float  # 0-1, higher is better
    nearest_sr_level: float
    distance_pct: float
    warning: str | None


class FibonacciSRCalculator:
    """
    Calculates Fibonacci-based support/resistance levels for SPY.

    Uses Alpaca API for historical price data and identifies significant
    price phases to project institutional-grade S/R levels.
    """

    def __init__(self):
        self.api_key = os.environ.get("ALPACA_PAPER_TRADING_API_KEY", "")
        self.api_secret = os.environ.get("ALPACA_PAPER_TRADING_API_SECRET", "")
        self.base_url = "https://data.alpaca.markets/v2"
        self._cached_levels: dict[str, list[FibonacciLevel]] | None = None
        self._cache_timestamp: datetime | None = None
        self._cache_ttl = timedelta(hours=4)  # Refresh every 4 hours

    async def get_spy_levels(self, lookback_days: int = 252) -> list[FibonacciLevel]:
        """
        Calculate Fibonacci S/R levels for SPY.

        Args:
            lookback_days: Number of trading days to analyze (default 252 = 1 year)

        Returns:
            List of FibonacciLevel objects sorted by price
        """
        # Check cache
        if self._cached_levels and self._cache_timestamp:
            if datetime.now() - self._cache_timestamp < self._cache_ttl:
                return self._cached_levels.get("SPY", [])

        # Fetch historical data
        bars = await self._fetch_daily_bars("SPY", lookback_days)
        if not bars:
            return []

        # Identify significant price phases
        phases = self._identify_phases(bars)
        if not phases:
            return []

        # Select the most significant phase (highest magnitude)
        primary_phase = max(phases, key=lambda p: p.magnitude_pct)

        # Calculate Fibonacci levels from the primary phase
        levels = self._calculate_fib_levels(primary_phase, bars)

        # Cache results
        self._cached_levels = {"SPY": levels}
        self._cache_timestamp = datetime.now()

        return levels

    async def _fetch_daily_bars(
        self, symbol: str, lookback_days: int
    ) -> list[dict[str, Any]]:
        """Fetch daily OHLC bars from Alpaca."""
        if not self.api_key or not self.api_secret:
            # Return mock data if no API keys
            return self._get_mock_bars()

        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(lookback_days * 1.5))  # Account for weekends

        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
        }

        params = {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
            "timeframe": "1Day",
            "limit": lookback_days,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/stocks/{symbol}/bars",
                    headers=headers,
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("bars", [])
        except Exception:
            return self._get_mock_bars()

    def _get_mock_bars(self) -> list[dict[str, Any]]:
        """Return mock SPY data for testing without API access."""
        import math

        # Approximate SPY price action with realistic swing patterns
        base_price = 560.0
        bars = []

        for i in range(252):  # ~1 year of trading days
            # Create realistic price swings using sine waves
            # Major cycle: ~60 days, Minor cycle: ~20 days
            major_cycle = math.sin(i * 2 * math.pi / 60) * 25  # +/- $25
            minor_cycle = math.sin(i * 2 * math.pi / 20) * 10  # +/- $10

            # Overall uptrend
            trend = i * 0.12  # ~$30 uptrend over year

            price = base_price + trend + major_cycle + minor_cycle

            # Add realistic daily range
            daily_range = abs(major_cycle) * 0.1 + 2  # Higher vol during swings

            bars.append({
                "t": (datetime.now() - timedelta(days=252 - i)).isoformat(),
                "o": price - daily_range * 0.3,
                "h": price + daily_range * 0.5,
                "l": price - daily_range * 0.5,
                "c": price,
                "v": 50000000 + int(abs(major_cycle) * 1000000),
            })
        return bars

    def _identify_phases(
        self, bars: list[dict[str, Any]], min_magnitude_pct: float = 5.0
    ) -> list[PricePhase]:
        """
        Identify significant price phases using swing high/low detection.

        A phase is significant if it has at least min_magnitude_pct price movement.
        """
        if len(bars) < 20:
            return []

        phases = []
        closes = [b["c"] for b in bars]
        highs = [b["h"] for b in bars]
        lows = [b["l"] for b in bars]
        dates = [datetime.fromisoformat(b["t"].replace("Z", "+00:00")) for b in bars]

        # Find swing points (local maxima/minima over 10-day windows)
        swing_points = []
        window = 10

        for i in range(window, len(bars) - window):
            # Check for swing high
            if highs[i] == max(highs[i - window : i + window + 1]):
                swing_points.append(("high", i, highs[i], dates[i]))
            # Check for swing low
            if lows[i] == min(lows[i - window : i + window + 1]):
                swing_points.append(("low", i, lows[i], dates[i]))

        # Remove duplicates (same index)
        seen_indices = set()
        unique_swings = []
        for sp in swing_points:
            if sp[1] not in seen_indices:
                unique_swings.append(sp)
                seen_indices.add(sp[1])

        # Sort by index
        unique_swings.sort(key=lambda x: x[1])

        # Create phases between alternating swing highs and lows
        for i in range(len(unique_swings) - 1):
            current = unique_swings[i]
            next_swing = unique_swings[i + 1]

            # Skip if same type (high-high or low-low)
            if current[0] == next_swing[0]:
                continue

            start_price = current[2]
            end_price = next_swing[2]
            magnitude_pct = abs(end_price - start_price) / start_price * 100

            if magnitude_pct >= min_magnitude_pct:
                duration = (next_swing[3] - current[3]).days
                phases.append(
                    PricePhase(
                        start_date=current[3],
                        end_date=next_swing[3],
                        start_price=start_price,
                        end_price=end_price,
                        is_bullish=end_price > start_price,
                        duration_days=duration,
                        magnitude_pct=magnitude_pct,
                    )
                )

        return phases

    def _calculate_fib_levels(
        self, phase: PricePhase, bars: list[dict[str, Any]]
    ) -> list[FibonacciLevel]:
        """Calculate Fibonacci levels from a price phase."""
        levels = []

        # Determine base and range based on phase direction
        if phase.is_bullish:
            # For bullish phase, retracement goes down from top
            base = phase.start_price  # Swing low
            top = phase.end_price  # Swing high
        else:
            # For bearish phase, retracement goes up from bottom
            base = phase.end_price  # Swing low
            top = phase.start_price  # Swing high

        price_range = top - base

        # Calculate each Fibonacci level
        for name, ratio in FIBONACCI_RATIOS.items():
            price = base + (price_range * ratio)

            # Determine if support or resistance based on current price
            current_price = bars[-1]["c"] if bars else (base + top) / 2
            level_type = "support" if price < current_price else "resistance"

            # Calculate strength based on historical touches
            strength = self._calculate_level_strength(price, bars)

            levels.append(
                FibonacciLevel(
                    ratio_name=name,
                    ratio=ratio,
                    price=round(price, 2),
                    level_type=level_type,
                    strength=strength,
                )
            )

        # Sort by price
        levels.sort(key=lambda x: x.price)
        return levels

    def _calculate_level_strength(
        self, level_price: float, bars: list[dict[str, Any]], tolerance_pct: float = 0.5
    ) -> float:
        """
        Calculate S/R level strength based on historical price touches.

        A "touch" is when price came within tolerance_pct of the level.
        More touches = stronger level.
        """
        touches = 0
        tolerance = level_price * tolerance_pct / 100

        for bar in bars:
            high = bar["h"]
            low = bar["l"]

            # Check if price touched the level
            if low - tolerance <= level_price <= high + tolerance:
                touches += 1

        # Normalize to 0-1 (cap at 10 touches for max strength)
        return min(touches / 10, 1.0)

    def validate_iron_condor_strikes(
        self,
        put_short: float,
        call_short: float,
        levels: list[FibonacciLevel],
    ) -> dict[str, StrikeValidation]:
        """
        Validate iron condor short strikes against S/R levels.

        Returns validation result for both put and call short strikes.
        """
        results = {}

        # Handle empty levels - return valid by default
        if not levels:
            for strike, strike_type in [(put_short, "put"), (call_short, "call")]:
                results[strike_type] = StrikeValidation(
                    strike=strike,
                    is_valid=True,
                    quality_score=0.5,  # Neutral quality when no S/R data
                    nearest_sr_level=0.0,
                    distance_pct=100.0,
                    warning="No Fibonacci S/R data available",
                )
            return results

        for strike, strike_type in [(put_short, "put"), (call_short, "call")]:
            # Find nearest S/R level
            nearest_level = min(levels, key=lambda l: abs(l.price - strike))
            distance = abs(nearest_level.price - strike)
            distance_pct = distance / strike * 100

            # Determine validity and quality
            warning = None
            if distance_pct < SR_DANGER_ZONE_PCT * 100:
                is_valid = False
                quality_score = 0.0
                warning = f"Strike ${strike} is {distance_pct:.1f}% from {nearest_level.ratio_name} S/R at ${nearest_level.price}"
            elif distance_pct < SR_WARNING_ZONE_PCT * 100:
                is_valid = True
                quality_score = 0.5
                warning = f"Strike ${strike} is close to {nearest_level.ratio_name} S/R at ${nearest_level.price}"
            else:
                is_valid = True
                # Quality increases with distance from S/R
                quality_score = min(distance_pct / 5, 1.0)  # Max quality at 5%+ distance

            results[strike_type] = StrikeValidation(
                strike=strike,
                is_valid=is_valid,
                quality_score=quality_score,
                nearest_sr_level=nearest_level.price,
                distance_pct=distance_pct,
                warning=warning,
            )

        return results

    def get_optimal_strike_zones(
        self, current_price: float, levels: list[FibonacciLevel]
    ) -> dict[str, tuple[float, float]]:
        """
        Get optimal strike zones for iron condor based on S/R levels.

        Returns price ranges where short strikes would be well-positioned
        (between S/R levels, not on them).
        """
        # Sort levels by price
        sorted_levels = sorted(levels, key=lambda l: l.price)

        # Find support levels below current price
        supports = [l for l in sorted_levels if l.price < current_price]
        # Find resistance levels above current price
        resistances = [l for l in sorted_levels if l.price > current_price]

        put_zone = (0.0, 0.0)
        call_zone = (0.0, 0.0)

        # Optimal put zone: between 2nd and 3rd support levels
        if len(supports) >= 3:
            put_zone = (supports[-3].price, supports[-2].price)
        elif len(supports) >= 2:
            put_zone = (supports[-2].price * 0.98, supports[-1].price)

        # Optimal call zone: between 2nd and 3rd resistance levels
        if len(resistances) >= 3:
            call_zone = (resistances[1].price, resistances[2].price)
        elif len(resistances) >= 2:
            call_zone = (resistances[0].price, resistances[1].price * 1.02)

        return {"put": put_zone, "call": call_zone}


async def main():
    """Demo the Fibonacci S/R calculator."""
    calc = FibonacciSRCalculator()

    print("Calculating SPY Fibonacci S/R levels...")
    levels = await calc.get_spy_levels()

    print("\n=== SPY Fibonacci Support/Resistance Levels ===")
    for level in levels:
        print(
            f"  {level.ratio_name:>8}: ${level.price:>7.2f} "
            f"({level.level_type:>10}, strength: {level.strength:.2f})"
        )

    # Example iron condor validation
    print("\n=== Iron Condor Strike Validation ===")
    put_short = 580.0
    call_short = 610.0

    validation = calc.validate_iron_condor_strikes(put_short, call_short, levels)

    for strike_type, result in validation.items():
        status = "✅ VALID" if result.is_valid else "❌ INVALID"
        print(f"\n{strike_type.upper()} ${result.strike}: {status}")
        print(f"  Quality Score: {result.quality_score:.2f}")
        print(f"  Nearest S/R: ${result.nearest_sr_level} ({result.distance_pct:.1f}% away)")
        if result.warning:
            print(f"  ⚠️  {result.warning}")

    # Get optimal zones
    print("\n=== Optimal Strike Zones ===")
    current_price = levels[len(levels) // 2].price if levels else 595.0
    zones = calc.get_optimal_strike_zones(current_price, levels)
    print(f"  PUT zone:  ${zones['put'][0]:.2f} - ${zones['put'][1]:.2f}")
    print(f"  CALL zone: ${zones['call'][0]:.2f} - ${zones['call'][1]:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
