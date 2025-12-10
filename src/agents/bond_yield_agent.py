"""
Bond Yield Agent

Analyzes yield curves and duration strategies for fixed income allocation.
Integrates with the 4-gate funnel orchestrator as a specialized bond analyst.

Strategies Implemented:
1. Yield Curve Analysis - Buy short duration on inversion, rotate to long on steepening
2. Duration Ladder - 3-tier treasury ladder with dynamic rebalancing
3. Credit Spread Monitor - Adjust corporate bond allocation based on spreads
4. Carry Trade - Capture yield differentials when curve is steep

Author: Trading System
Created: 2025-12-03
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class YieldCurveShape(Enum):
    """Yield curve shape classification."""

    STEEP = "steep"  # Long yields >> short yields (bullish)
    NORMAL = "normal"  # Long yields > short yields
    FLAT = "flat"  # Long yields ≈ short yields (transition)
    INVERTED = "inverted"  # Short yields > long yields (recession risk)


class DurationStrategy(Enum):
    """Duration positioning strategy."""

    BARBELL = "barbell"  # Short + Long, skip intermediate
    BULLET = "bullet"  # Concentrate in intermediate
    LADDER = "ladder"  # Spread across all durations


@dataclass
class YieldCurveSignal:
    """Signal from yield curve analysis."""

    shape: YieldCurveShape
    spread_2_10: float  # 10yr - 2yr spread
    spread_10_30: float  # 30yr - 10yr spread
    recommended_duration: str  # short/intermediate/long
    recommended_strategy: DurationStrategy
    confidence: float
    rationale: str
    timestamp: datetime


@dataclass
class BondAllocationSignal:
    """Bond allocation recommendation."""

    symbol: str
    allocation_pct: float
    is_buy: bool
    strength: float
    category: str  # treasury/corporate_ig/corporate_hy/municipal/tips
    duration: str  # short/intermediate/long
    rationale: str
    indicators: dict


class BondYieldAgent:
    """
    Bond Yield Agent for fixed income analysis.

    Provides yield curve analysis, duration strategy recommendations,
    and bond allocation signals for the trading orchestrator.
    """

    # Yield curve thresholds (in percentage points)
    SPREAD_STEEP_THRESHOLD = 1.5  # Spread > 1.5% = steep
    SPREAD_NORMAL_THRESHOLD = 0.5  # Spread > 0.5% = normal
    SPREAD_FLAT_THRESHOLD = 0.0  # Spread > 0% = flat
    # Below 0% = inverted

    # Credit spread thresholds (High Yield OAS)
    CREDIT_TIGHT_THRESHOLD = 3.5  # < 3.5% = risk-on
    CREDIT_NORMAL_THRESHOLD = 5.0  # < 5.0% = normal
    CREDIT_WIDE_THRESHOLD = 7.0  # > 7.0% = stress

    # Bond allocation limits
    MAX_BOND_ALLOCATION = 0.40  # Max 40% of daily allocation to bonds
    MIN_BOND_ALLOCATION = 0.10  # Min 10% to bonds (always have some ballast)

    # Duration targets by curve shape
    DURATION_TARGETS = {
        YieldCurveShape.STEEP: "long",  # Capture yield on steep curves
        YieldCurveShape.NORMAL: "intermediate",  # Balanced approach
        YieldCurveShape.FLAT: "short",  # Reduce rate risk
        YieldCurveShape.INVERTED: "short",  # Defensive positioning
    }

    def __init__(
        self,
        min_confidence: float = 0.5,
        enable_corporates: bool = True,
        enable_munis: bool = False,
    ):
        """
        Initialize Bond Yield Agent.

        Args:
            min_confidence: Minimum confidence threshold for signals
            enable_corporates: Whether to include corporate bonds
            enable_munis: Whether to include municipal bonds
        """
        self.min_confidence = min_confidence
        self.enable_corporates = enable_corporates
        self.enable_munis = enable_munis

        # Try to initialize FRED collector for yield data
        self.fred_collector = None
        try:
            from src.rag.collectors.fred_collector import FREDCollector

            self.fred_collector = FREDCollector()
            logger.info("BondYieldAgent: FRED collector initialized")
        except Exception as e:
            logger.warning(f"BondYieldAgent: FRED collector unavailable: {e}")

        # Cache for yield data
        self._yield_cache: dict[str, Any] = {}
        self._cache_expiry: datetime | None = None

        logger.info(
            f"BondYieldAgent initialized: min_confidence={min_confidence}, "
            f"corporates={enable_corporates}, munis={enable_munis}"
        )

    def analyze_yield_curve(self) -> YieldCurveSignal:
        """
        Analyze current yield curve shape and generate signal.

        Returns:
            YieldCurveSignal with analysis results
        """
        logger.info("Analyzing yield curve...")

        # Get yield data from FRED or cache
        yield_data = self._get_yield_data()

        # Extract key yields
        yield_2yr = yield_data.get("DGS2", 4.5)  # Default if unavailable
        yield_10yr = yield_data.get("DGS10", 4.5)
        yield_30yr = yield_data.get("DGS30", 4.7)
        spread_direct = yield_data.get("T10Y2Y")

        # Calculate spreads
        if spread_direct is not None:
            spread_2_10 = spread_direct
        else:
            spread_2_10 = yield_10yr - yield_2yr

        spread_10_30 = yield_30yr - yield_10yr

        # Determine curve shape
        if spread_2_10 > self.SPREAD_STEEP_THRESHOLD:
            shape = YieldCurveShape.STEEP
            confidence = min(1.0, 0.6 + (spread_2_10 - self.SPREAD_STEEP_THRESHOLD) * 0.2)
            rationale = (
                f"Steep curve ({spread_2_10:.2f}% spread). Favor long duration to capture yield."
            )
        elif spread_2_10 > self.SPREAD_NORMAL_THRESHOLD:
            shape = YieldCurveShape.NORMAL
            confidence = 0.6 + min(0.2, spread_2_10 * 0.1)
            rationale = f"Normal curve ({spread_2_10:.2f}% spread). Balanced duration approach."
        elif spread_2_10 > self.SPREAD_FLAT_THRESHOLD:
            shape = YieldCurveShape.FLAT
            confidence = 0.5 + min(0.2, (0.5 - spread_2_10) * 0.4)
            rationale = (
                f"Flat curve ({spread_2_10:.2f}% spread). Late cycle - favor short duration."
            )
        else:
            shape = YieldCurveShape.INVERTED
            confidence = min(0.9, 0.7 + abs(spread_2_10) * 0.1)
            rationale = (
                f"INVERTED curve ({spread_2_10:.2f}% spread). "
                "Recession signal - defensive short duration."
            )

        # Determine strategy
        recommended_duration = self.DURATION_TARGETS[shape]

        if shape == YieldCurveShape.STEEP:
            strategy = DurationStrategy.BARBELL  # Capture both ends
        elif shape == YieldCurveShape.INVERTED:
            strategy = DurationStrategy.BULLET  # Concentrate short
        else:
            strategy = DurationStrategy.LADDER  # Default ladder

        signal = YieldCurveSignal(
            shape=shape,
            spread_2_10=spread_2_10,
            spread_10_30=spread_10_30,
            recommended_duration=recommended_duration,
            recommended_strategy=strategy,
            confidence=confidence,
            rationale=rationale,
            timestamp=datetime.now(),
        )

        logger.info(
            f"Yield curve: {shape.value} | Spread: {spread_2_10:.2f}% | "
            f"Recommendation: {recommended_duration} duration"
        )

        return signal

    def generate_bond_signals(self, daily_allocation: float = 10.0) -> list[BondAllocationSignal]:
        """
        Generate bond allocation signals for today's trading.

        Args:
            daily_allocation: Total daily investment amount

        Returns:
            List of BondAllocationSignal objects
        """
        logger.info("Generating bond allocation signals...")

        signals = []

        # Get yield curve signal
        curve_signal = self.analyze_yield_curve()

        # Calculate bond allocation percentage based on market conditions
        bond_pct = self._calculate_bond_allocation_pct(curve_signal)
        bond_amount = daily_allocation * bond_pct

        # Get treasury allocation based on yield curve
        treasury_signals = self._generate_treasury_signals(
            curve_signal,
            bond_amount * 0.6,  # 60% of bonds to treasuries
        )
        signals.extend(treasury_signals)

        # Get corporate allocation if enabled
        if self.enable_corporates:
            corp_signals = self._generate_corporate_signals(
                curve_signal,
                bond_amount * 0.3,  # 30% of bonds to corporates
            )
            signals.extend(corp_signals)

        # TIPS allocation (10% of bonds)
        tips_signal = self._generate_tips_signal(curve_signal, bond_amount * 0.1)
        if tips_signal:
            signals.append(tips_signal)

        # Filter by confidence threshold
        signals = [s for s in signals if s.strength >= self.min_confidence]

        logger.info(
            f"Generated {len(signals)} bond signals (bond allocation: {bond_pct * 100:.0f}%)"
        )
        return signals

    def _calculate_bond_allocation_pct(self, curve_signal: YieldCurveSignal) -> float:
        """Calculate optimal bond allocation percentage."""
        # Base allocation
        base_pct = 0.20  # 20% baseline

        # Adjust based on yield curve
        if curve_signal.shape == YieldCurveShape.INVERTED:
            # Increase bonds during inversion (defensive)
            base_pct += 0.15
        elif curve_signal.shape == YieldCurveShape.FLAT:
            base_pct += 0.05
        elif curve_signal.shape == YieldCurveShape.STEEP:
            # Can take more equity risk with steep curve
            base_pct -= 0.05

        # Environment variable override
        env_max = float(os.getenv("MAX_BOND_ALLOCATION", str(self.MAX_BOND_ALLOCATION)))
        env_min = float(os.getenv("MIN_BOND_ALLOCATION", str(self.MIN_BOND_ALLOCATION)))

        return max(env_min, min(env_max, base_pct))

    def _generate_treasury_signals(
        self, curve_signal: YieldCurveSignal, amount: float
    ) -> list[BondAllocationSignal]:
        """Generate treasury ETF signals based on yield curve."""
        signals = []

        # Treasury allocation by duration
        if curve_signal.recommended_strategy == DurationStrategy.BARBELL:
            # Short + Long, skip intermediate
            allocations = {"SHY": 0.50, "TLT": 0.50}
        elif curve_signal.recommended_strategy == DurationStrategy.BULLET:
            # Concentrate in short duration
            allocations = {"SHY": 0.70, "IEF": 0.30}
        else:  # LADDER
            # Spread across all
            if curve_signal.shape == YieldCurveShape.INVERTED:
                allocations = {"SHY": 0.60, "IEF": 0.30, "TLT": 0.10}
            elif curve_signal.shape == YieldCurveShape.STEEP:
                allocations = {"SHY": 0.20, "IEF": 0.30, "TLT": 0.50}
            else:
                allocations = {"SHY": 0.40, "IEF": 0.40, "TLT": 0.20}

        # Generate signals for each treasury ETF
        duration_map = {"SHY": "short", "IEF": "intermediate", "TLT": "long"}

        for symbol, pct in allocations.items():
            alloc_amount = amount * pct
            if alloc_amount < 0.50:  # Skip if below minimum
                continue

            # Check momentum gate for the ETF
            is_buy, momentum_data = self._check_bond_momentum(symbol)

            signal = BondAllocationSignal(
                symbol=symbol,
                allocation_pct=pct,
                is_buy=is_buy,
                strength=curve_signal.confidence * (0.9 if is_buy else 0.5),
                category="treasury",
                duration=duration_map.get(symbol, "intermediate"),
                rationale=f"{curve_signal.rationale} Momentum: {'OPEN' if is_buy else 'CLOSED'}",
                indicators={
                    "yield_curve_shape": curve_signal.shape.value,
                    "spread_2_10": curve_signal.spread_2_10,
                    "strategy": curve_signal.recommended_strategy.value,
                    "allocation_amount": round(alloc_amount, 2),
                    **momentum_data,
                },
            )
            signals.append(signal)

        return signals

    def _generate_corporate_signals(
        self, curve_signal: YieldCurveSignal, amount: float
    ) -> list[BondAllocationSignal]:
        """Generate corporate bond ETF signals."""
        signals = []

        # Get credit spread environment
        credit_spread = self._get_credit_spread()

        # Determine corporate allocation
        if credit_spread is None or credit_spread < self.CREDIT_TIGHT_THRESHOLD:
            # Tight spreads - risk on, can own more corporates
            allocations = {"LQD": 0.60, "JNK": 0.40}
            credit_env = "tight"
        elif credit_spread < self.CREDIT_NORMAL_THRESHOLD:
            # Normal spreads
            allocations = {"LQD": 0.80, "JNK": 0.20}
            credit_env = "normal"
        elif credit_spread < self.CREDIT_WIDE_THRESHOLD:
            # Wide spreads - reduce risk
            allocations = {"LQD": 0.90, "JNK": 0.10}
            credit_env = "wide"
        else:
            # Very wide - avoid high yield
            allocations = {"LQD": 1.0}
            credit_env = "stress"

        category_map = {"LQD": "corporate_ig", "JNK": "corporate_hy", "HYG": "corporate_hy"}

        for symbol, pct in allocations.items():
            alloc_amount = amount * pct
            if alloc_amount < 0.50:
                continue

            is_buy, momentum_data = self._check_bond_momentum(symbol)

            # Reduce confidence for high yield in stress
            if symbol in ["JNK", "HYG"] and credit_env == "stress":
                strength = 0.3
            else:
                strength = curve_signal.confidence * (0.85 if is_buy else 0.45)

            signal = BondAllocationSignal(
                symbol=symbol,
                allocation_pct=pct,
                is_buy=is_buy and credit_env != "stress",
                strength=strength,
                category=category_map.get(symbol, "corporate_ig"),
                duration="intermediate",
                rationale=f"Credit spreads: {credit_env}. {curve_signal.rationale}",
                indicators={
                    "credit_spread": credit_spread,
                    "credit_environment": credit_env,
                    "allocation_amount": round(alloc_amount, 2),
                    **momentum_data,
                },
            )
            signals.append(signal)

        return signals

    def _generate_tips_signal(
        self, curve_signal: YieldCurveSignal, amount: float
    ) -> BondAllocationSignal | None:
        """Generate TIPS allocation signal."""
        if amount < 0.50:
            return None

        is_buy, momentum_data = self._check_bond_momentum("TIP")

        return BondAllocationSignal(
            symbol="TIP",
            allocation_pct=1.0,
            is_buy=is_buy,
            strength=0.6 * (1.0 if is_buy else 0.6),
            category="tips",
            duration="intermediate",
            rationale="Inflation protection allocation",
            indicators={
                "allocation_amount": round(amount, 2),
                **momentum_data,
            },
        )

    def _get_yield_data(self) -> dict[str, float]:
        """Get yield data from FRED or cache."""
        # Check cache validity
        if self._cache_expiry and datetime.now() < self._cache_expiry and self._yield_cache:
            return self._yield_cache

        yield_data = {}

        if self.fred_collector:
            try:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=7)

                for series in ["DGS2", "DGS10", "DGS30", "T10Y2Y"]:
                    data = self.fred_collector._fetch_series(
                        series,
                        start_date.strftime("%Y-%m-%d"),
                        end_date.strftime("%Y-%m-%d"),
                    )
                    if data and data.get("latest_value") not in (None, "."):
                        try:
                            yield_data[series] = float(data["latest_value"])
                        except (ValueError, TypeError):
                            pass

                # Cache for 1 hour
                self._yield_cache = yield_data
                self._cache_expiry = datetime.now() + timedelta(hours=1)

            except Exception as e:
                logger.warning(f"Error fetching yield data: {e}")

        # Use defaults if no data
        if not yield_data:
            yield_data = {
                "DGS2": 4.2,
                "DGS10": 4.3,
                "DGS30": 4.5,
                "T10Y2Y": 0.1,
            }

        return yield_data

    def _get_credit_spread(self) -> float | None:
        """Get high yield credit spread from FRED."""
        if not self.fred_collector:
            return None

        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)

            data = self.fred_collector._fetch_series(
                "BAMLH0A0HYM2",  # ICE BofA US High Yield OAS
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            )

            if data and data.get("latest_value") not in (None, "."):
                return float(data["latest_value"])

        except Exception as e:
            logger.warning(f"Error fetching credit spread: {e}")

        return None

    def _check_bond_momentum(self, symbol: str) -> tuple[bool, dict]:
        """
        Check if bond ETF passes momentum gate.

        Returns:
            Tuple of (is_momentum_positive, momentum_data)
        """
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="6mo")

            if hist.empty:
                return True, {"momentum_error": "No data"}

            current_price = float(hist["Close"].iloc[-1])
            sma_20 = float(hist["Close"].rolling(20).mean().iloc[-1])
            sma_50 = float(hist["Close"].rolling(50).mean().iloc[-1])

            is_buy = sma_20 >= sma_50

            return is_buy, {
                "current_price": round(current_price, 2),
                "sma_20": round(sma_20, 2),
                "sma_50": round(sma_50, 2),
                "momentum_gate": "OPEN" if is_buy else "CLOSED",
            }

        except Exception as e:
            logger.warning(f"Error checking momentum for {symbol}: {e}")
            return True, {"momentum_error": str(e)}


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    agent = BondYieldAgent()

    print("\n" + "=" * 80)
    print("BOND YIELD AGENT - ANALYSIS")
    print("=" * 80)

    # Yield curve analysis
    curve = agent.analyze_yield_curve()
    print(f"\nYield Curve Shape: {curve.shape.value}")
    print(f"2-10 Spread: {curve.spread_2_10:.2f}%")
    print(f"Strategy: {curve.recommended_strategy.value}")
    print(f"Duration Target: {curve.recommended_duration}")
    print(f"Confidence: {curve.confidence:.2f}")
    print(f"Rationale: {curve.rationale}")

    # Generate signals
    print("\n" + "-" * 80)
    print("BOND ALLOCATION SIGNALS")
    print("-" * 80)

    signals = agent.generate_bond_signals(daily_allocation=10.0)

    for signal in signals:
        action = "BUY" if signal.is_buy else "SKIP"
        print(
            f"\n{action} {signal.symbol} ({signal.category}/{signal.duration})"
            f"\n  Allocation: ${signal.indicators.get('allocation_amount', 0):.2f}"
            f"\n  Strength: {signal.strength:.2f}"
            f"\n  Gate: {signal.indicators.get('momentum_gate', 'N/A')}"
            f"\n  Rationale: {signal.rationale[:60]}..."
        )

    print("\n" + "=" * 80)
