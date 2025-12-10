"""
VIX Volatility Regime Monitor

Real-time VIX monitoring system for volatility regime detection and strategy adaptation.
Provides volatility-based position sizing and strategy recommendations.

Features:
    - Real-time VIX level tracking
    - Volatility regime classification (5 regimes)
    - VIX term structure analysis (contango/backwardation)
    - VIX spike detection (rapid increases)
    - Strategy recommendations per regime
    - Automated alerts on regime changes

VIX Regime Philosophy:
    - Low VIX (< 12): Complacency - aggressive premium selling
    - Normal VIX (12-18): Standard theta strategies
    - Elevated VIX (18-25): Caution - reduce size, widen strikes
    - High VIX (25-35): Fear - defensive positioning
    - Extreme VIX (> 35): Panic - capital preservation first

Author: Trading System
Created: 2025-12-10
"""

import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

# Workaround for yfinance multitasking dependency issue
try:
    import multitasking
except ImportError:
    # Create a dummy multitasking module to satisfy yfinance import
    import types

    multitasking = types.ModuleType("multitasking")
    multitasking.config = {"CPU_CORES": 1}
    multitasking.set_max_threads = lambda x: None
    multitasking.createPool = lambda: None
    multitasking.cpu_count = lambda: 1

    # Add task decorator (just returns the function unchanged)
    def task(func):
        return func

    multitasking.task = task
    sys.modules["multitasking"] = multitasking

logger = logging.getLogger(__name__)


class VIXRegime(Enum):
    """VIX volatility regime classification."""

    LOW = "low"  # 0-12: Complacency
    NORMAL = "normal"  # 12-18: Normal market
    ELEVATED = "elevated"  # 18-25: Caution
    HIGH = "high"  # 25-35: Fear
    EXTREME = "extreme"  # 35+: Panic


class TermStructure(Enum):
    """VIX term structure state."""

    CONTANGO = "contango"  # VIX < VIX3M (normal)
    FLAT = "flat"  # VIX ≈ VIX3M
    BACKWARDATION = "backwardation"  # VIX > VIX3M (warning)


class AlertType(Enum):
    """VIX monitoring alert types."""

    REGIME_CHANGE = "regime_change"
    VIX_SPIKE = "vix_spike"
    TERM_STRUCTURE_INVERSION = "term_structure_inversion"
    EXTREME_VOLATILITY = "extreme_volatility"
    COMPLACENCY_WARNING = "complacency_warning"


@dataclass
class VIXAlert:
    """VIX monitoring alert."""

    alert_type: AlertType
    timestamp: datetime
    message: str
    old_regime: Optional[VIXRegime]
    new_regime: Optional[VIXRegime]
    vix_level: float
    recommended_action: str


@dataclass
class VIXData:
    """Current VIX market data."""

    vix: float  # VIX index level
    vix3m: Optional[float]  # 3-month VIX futures (if available)
    timestamp: datetime
    regime: VIXRegime
    term_structure: TermStructure
    spread: Optional[float]  # VIX3M - VIX (positive = contango)
    change_1d: Optional[float]  # 1-day change
    is_spike: bool  # Rapid increase detected


@dataclass
class StrategyRecommendation:
    """Volatility regime-based strategy recommendation."""

    regime: VIXRegime
    allowed_strategies: list[str]
    position_size_multiplier: float  # Scale from 1.0 (normal)
    strike_width_adjustment: str  # "wider", "normal", "tighter"
    max_portfolio_theta: float  # Maximum negative theta exposure
    defensive_hedging: bool  # Should we hold protective puts?
    recommendation: str  # Human-readable summary


class VIXMonitor:
    """
    Real-time VIX volatility regime monitor.

    Tracks VIX levels, detects regime changes, analyzes term structure,
    and provides strategy recommendations based on current volatility regime.
    """

    # VIX regime thresholds (lower, upper)
    REGIME_THRESHOLDS = {
        VIXRegime.LOW: (0, 12),
        VIXRegime.NORMAL: (12, 18),
        VIXRegime.ELEVATED: (18, 25),
        VIXRegime.HIGH: (25, 35),
        VIXRegime.EXTREME: (35, 100),
    }

    # VIX spike threshold (points in 1 day)
    SPIKE_THRESHOLD = 3.0

    # Term structure thresholds
    BACKWARDATION_THRESHOLD = -0.5  # VIX3M - VIX < -0.5

    # Cache duration in seconds (5 minutes)
    CACHE_DURATION = 300

    def __init__(
        self,
        data_dir: str = "data/monitoring",
        alert_callback: Optional[Callable] = None,
    ):
        """
        Initialize VIX monitor.

        Args:
            data_dir: Directory for storing VIX data and alerts
            alert_callback: Optional callback function for alerts
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.alert_callback = alert_callback
        self.alerts: list[VIXAlert] = []
        self.current_regime: Optional[VIXRegime] = None
        self.vix_history: list[tuple[datetime, float]] = []
        self.last_update: Optional[datetime] = None

        # Caching for VIX data
        self._cached_vix: Optional[float] = None
        self._cached_vix3m: Optional[float] = None
        self._cache_timestamp: Optional[datetime] = None

        # Load historical data if available
        self._load_state()

        logger.info("VIX Monitor initialized")

    def _is_cache_valid(self) -> bool:
        """Check if cached VIX data is still valid."""
        if self._cache_timestamp is None or self._cached_vix is None:
            return False

        age = (datetime.now() - self._cache_timestamp).total_seconds()
        return age < self.CACHE_DURATION

    def get_vix_level(self) -> float:
        """
        Get current VIX level from yfinance (with 5-minute caching).

        Returns:
            Current VIX index level

        Raises:
            Exception: If unable to fetch VIX data
        """
        # Check cache first
        if self._is_cache_valid():
            logger.debug(f"Using cached VIX: {self._cached_vix:.2f}")
            return self._cached_vix

        try:
            import yfinance as yf

            # Fetch latest VIX data using download (more reliable)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)

            vix_data = yf.download(
                "^VIX",
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
            )

            if vix_data.empty:
                raise ValueError("No VIX data returned from yfinance")

            vix_level = float(vix_data["Close"].iloc[-1])

            # Update cache
            self._cached_vix = vix_level
            self._cache_timestamp = datetime.now()

            logger.info(f"VIX level fetched: {vix_level:.2f}")
            return vix_level

        except Exception as e:
            logger.error(f"Failed to fetch VIX level: {e}")

            # Try fallback to last known cached value (even if stale)
            if self._cached_vix is not None:
                logger.warning(f"Using stale cached VIX: {self._cached_vix:.2f}")
                return self._cached_vix

            # Try fallback to history
            if self.vix_history:
                last_vix = self.vix_history[-1][1]
                logger.warning(f"Using last known VIX from history: {last_vix:.2f}")
                return last_vix

            raise

    def get_vix3m_level(self) -> Optional[float]:
        """
        Get 3-month VIX futures level (VIX3M) from yfinance (with caching).

        Returns:
            VIX3M level or None if unavailable
        """
        # Check cache first
        if self._is_cache_valid() and self._cached_vix3m is not None:
            logger.debug(f"Using cached VIX3M: {self._cached_vix3m:.2f}")
            return self._cached_vix3m

        try:
            import yfinance as yf

            # VIX3M is available as ^VIX3M on Yahoo Finance
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)

            vix3m_data = yf.download(
                "^VIX3M",
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
            )

            if vix3m_data.empty:
                logger.debug("VIX3M data not available")
                return None

            vix3m_level = float(vix3m_data["Close"].iloc[-1])

            # Update cache
            self._cached_vix3m = vix3m_level

            logger.info(f"VIX3M level fetched: {vix3m_level:.2f}")
            return vix3m_level

        except Exception as e:
            logger.debug(f"Could not fetch VIX3M: {e}")
            # Return cached value if available (even if stale)
            if self._cached_vix3m is not None:
                logger.debug(f"Using stale cached VIX3M: {self._cached_vix3m:.2f}")
                return self._cached_vix3m
            return None

    def get_vix_regime(self, vix_level: Optional[float] = None) -> VIXRegime:
        """
        Determine current VIX regime.

        Args:
            vix_level: VIX level (fetches current if not provided)

        Returns:
            Current VIX regime classification
        """
        if vix_level is None:
            vix_level = self.get_vix_level()

        for regime, (lower, upper) in self.REGIME_THRESHOLDS.items():
            if lower <= vix_level < upper:
                return regime

        # Fallback to extreme if somehow outside all ranges
        return VIXRegime.EXTREME

    def get_vix_term_structure(
        self, vix: Optional[float] = None, vix3m: Optional[float] = None
    ) -> TermStructure:
        """
        Analyze VIX term structure.

        Contango (VIX < VIX3M): Normal market condition
        Backwardation (VIX > VIX3M): Warning signal - near-term fear

        Args:
            vix: Current VIX level (fetches if not provided)
            vix3m: 3-month VIX level (fetches if not provided)

        Returns:
            Term structure state
        """
        if vix is None:
            vix = self.get_vix_level()

        if vix3m is None:
            vix3m = self.get_vix3m_level()

        if vix3m is None:
            logger.warning("VIX3M unavailable, cannot determine term structure")
            return TermStructure.FLAT

        spread = vix3m - vix

        if spread < self.BACKWARDATION_THRESHOLD:
            return TermStructure.BACKWARDATION
        elif spread > 0.5:
            return TermStructure.CONTANGO
        else:
            return TermStructure.FLAT

    def is_vix_spike(self, current_vix: Optional[float] = None) -> bool:
        """
        Detect VIX spike (sudden large increase).

        A spike is defined as VIX increasing by more than SPIKE_THRESHOLD
        points in a single day.

        Args:
            current_vix: Current VIX level (fetches if not provided)

        Returns:
            True if VIX spike detected
        """
        if current_vix is None:
            current_vix = self.get_vix_level()

        # Need at least 1 historical data point
        if len(self.vix_history) < 1:
            return False

        # Get most recent previous VIX level (within last 24 hours)
        now = datetime.now()
        yesterday = now - timedelta(days=1)

        recent_vix = None
        for timestamp, vix_val in reversed(self.vix_history):
            if timestamp >= yesterday:
                recent_vix = vix_val
                break

        if recent_vix is None:
            return False

        change = current_vix - recent_vix

        is_spike = change >= self.SPIKE_THRESHOLD

        if is_spike:
            logger.warning(
                f"VIX SPIKE DETECTED: {recent_vix:.2f} → {current_vix:.2f} (+{change:.2f})"
            )

        return is_spike

    def get_vix_change_1d(self, current_vix: float) -> Optional[float]:
        """
        Calculate 1-day VIX change.

        Args:
            current_vix: Current VIX level

        Returns:
            1-day change in VIX points, or None if insufficient history
        """
        if len(self.vix_history) < 1:
            return None

        now = datetime.now()
        yesterday = now - timedelta(days=1)

        # Find most recent VIX from ~24 hours ago
        for timestamp, vix_val in reversed(self.vix_history):
            if timestamp >= yesterday:
                return current_vix - vix_val

        return None

    def get_current_vix_data(self) -> VIXData:
        """
        Get complete current VIX data snapshot.

        Returns:
            VIXData with all current metrics
        """
        vix = self.get_vix_level()
        vix3m = self.get_vix3m_level()
        regime = self.get_vix_regime(vix)
        term_structure = self.get_vix_term_structure(vix, vix3m)
        spread = (vix3m - vix) if vix3m else None
        change_1d = self.get_vix_change_1d(vix)
        is_spike = self.is_vix_spike(vix)

        # Record in history
        now = datetime.now()
        self.vix_history.append((now, vix))
        self.last_update = now

        # Keep history manageable (30 days max)
        cutoff = now - timedelta(days=30)
        self.vix_history = [(ts, val) for ts, val in self.vix_history if ts >= cutoff]

        # Check for regime change
        if self.current_regime and regime != self.current_regime:
            self._handle_regime_change(self.current_regime, regime, vix)

        self.current_regime = regime

        # Check for alerts
        self._check_alerts(vix, regime, term_structure, is_spike)

        return VIXData(
            vix=vix,
            vix3m=vix3m,
            timestamp=now,
            regime=regime,
            term_structure=term_structure,
            spread=spread,
            change_1d=change_1d,
            is_spike=is_spike,
        )

    def get_current_vix(self) -> float:
        """
        Convenience method: Get current VIX level.

        Returns:
            Current VIX index level

        Raises:
            Exception: If unable to fetch VIX data
        """
        return self.get_vix_level()

    def get_vix_percentile(self, lookback_days: int = 252) -> Optional[float]:
        """
        Calculate where current VIX sits relative to historical range.

        Args:
            lookback_days: Historical lookback period (default 252 = 1 year)

        Returns:
            Percentile rank (0-100) where current VIX sits, or None if insufficient data
        """
        try:
            import yfinance as yf

            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days + 30)  # Extra buffer

            vix_data = yf.download(
                "^VIX",
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
            )

            if vix_data.empty:
                logger.warning("No historical VIX data for percentile calculation")
                return None

            closes = vix_data["Close"].dropna()
            if len(closes) < 30:
                return None

            current_vix = self.get_vix_level()

            # Calculate percentile rank
            percentile = (closes < current_vix).mean() * 100

            logger.info(
                f"VIX Percentile: {percentile:.1f}% ({current_vix:.2f} vs {lookback_days}-day range)"
            )

            return round(percentile, 1)

        except Exception as e:
            logger.error(f"Failed to calculate VIX percentile: {e}")
            return None

    def get_volatility_regime(self) -> str:
        """
        Get current volatility regime as simple string classification.

        Returns one of:
            - "very_low": VIX < 12
            - "low": VIX 12-16
            - "normal": VIX 16-20
            - "elevated": VIX 20-25
            - "high": VIX 25-30
            - "extreme": VIX > 30

        Returns:
            Volatility regime string
        """
        vix = self.get_vix_level()

        if vix < 12:
            return "very_low"
        elif vix < 16:
            return "low"
        elif vix < 20:
            return "normal"
        elif vix < 25:
            return "elevated"
        elif vix < 30:
            return "high"
        else:
            return "extreme"

    def should_sell_premium(self) -> bool:
        """
        Determine if conditions are favorable for selling premium (theta strategies).

        Returns True if:
        - VIX is elevated (20+) AND term structure is in contango
        - This indicates high implied volatility with expectation of mean reversion

        Returns:
            True if favorable to sell premium (credit spreads, iron condors, etc.)
        """
        try:
            vix = self.get_vix_level()
            vix3m = self.get_vix3m_level()

            # Need elevated VIX for premium
            if vix < 20:
                return False

            # Check term structure (contango = VIX3M > VIX)
            if vix3m is not None:
                spread = vix3m - vix
                is_contango = spread > 0.5

                if is_contango:
                    logger.info(
                        f"SELL PREMIUM: VIX {vix:.2f} elevated + contango (spread: {spread:.2f})"
                    )
                    return True

            # Fallback: VIX very elevated (>25) even without term structure data
            if vix >= 25:
                logger.info(f"SELL PREMIUM: VIX {vix:.2f} very elevated")
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking sell premium conditions: {e}")
            return False

    def should_buy_premium(self) -> bool:
        """
        Determine if conditions are favorable for buying premium (long volatility).

        Returns True if:
        - VIX is very low (<15) AND term structure shows backwardation
        - This indicates volatility is cheap and market expects near-term spike

        Returns:
            True if favorable to buy premium (long straddles, strangles, etc.)
        """
        try:
            vix = self.get_vix_level()
            vix3m = self.get_vix3m_level()

            # VIX must be low for premium to be cheap
            if vix >= 15:
                return False

            # Check for backwardation (VIX > VIX3M = warning signal)
            if vix3m is not None:
                spread = vix3m - vix
                is_backwardation = spread < -0.5

                if is_backwardation:
                    logger.info(
                        f"BUY PREMIUM: VIX {vix:.2f} very low + backwardation (spread: {spread:.2f})"
                    )
                    return True

            # Fallback: VIX extremely low (<12) even without term structure
            if vix < 12:
                logger.info(f"BUY PREMIUM: VIX {vix:.2f} extremely low (complacency)")
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking buy premium conditions: {e}")
            return False

    def get_options_strategy_recommendation(self) -> dict:
        """
        Get options strategy recommendation based on current VIX regime.

        Returns dictionary with:
            - regime: Current volatility regime
            - vix_level: Current VIX value
            - recommendation: Strategy recommendation string
            - strategies: List of recommended strategies
            - sizing: Position size multiplier

        Returns:
            Dictionary with strategy recommendation
        """
        regime = self.get_volatility_regime()
        vix = self.get_vix_level()

        recommendations = {
            "very_low": {
                "recommendation": "Buy straddles/strangles - volatility extremely cheap. "
                "Market complacency creates opportunity for long volatility positions.",
                "strategies": ["long_straddle", "long_strangle", "calendar_spread"],
                "sizing": 1.0,
            },
            "low": {
                "recommendation": "Buy straddles/strangles - volatility cheap. "
                "Consider ATM or slightly OTM long positions to capture potential volatility expansion.",
                "strategies": ["long_straddle", "long_strangle", "debit_spread"],
                "sizing": 1.0,
            },
            "normal": {
                "recommendation": "Iron condors - neutral volatility regime. "
                "Sell premium on both sides with defined risk. Target 1-2 standard deviations.",
                "strategies": ["iron_condor", "iron_butterfly", "credit_spread"],
                "sizing": 1.0,
            },
            "elevated": {
                "recommendation": "Sell puts/credit spreads - elevated premium available. "
                "Focus on bullish strategies with IV above historical average.",
                "strategies": [
                    "cash_secured_put",
                    "bull_put_spread",
                    "short_strangle",
                ],
                "sizing": 1.2,
            },
            "high": {
                "recommendation": "Sell puts/credit spreads - high premium, wide strikes. "
                "Increase position size but widen strikes for safety. Consider further OTM.",
                "strategies": [
                    "bull_put_spread",
                    "cash_secured_put",
                    "short_strangle_wide",
                ],
                "sizing": 1.5,
            },
            "extreme": {
                "recommendation": "Sell strangles - extreme premium, hedge delta exposure. "
                "MAX premium available but use WIDE strikes and hedge directional risk. "
                "Consider protective long positions.",
                "strategies": [
                    "short_strangle_wide",
                    "iron_condor_wide",
                    "covered_strangle",
                ],
                "sizing": 1.8,
            },
        }

        rec = recommendations[regime]

        return {
            "regime": regime,
            "vix_level": round(vix, 2),
            "recommendation": rec["recommendation"],
            "strategies": rec["strategies"],
            "sizing": rec["sizing"],
            "sell_premium": self.should_sell_premium(),
            "buy_premium": self.should_buy_premium(),
        }

    def get_strategy_recommendation(
        self, regime: Optional[VIXRegime] = None
    ) -> StrategyRecommendation:
        """
        Get strategy recommendation for current VIX regime.

        Args:
            regime: VIX regime (uses current if not provided)

        Returns:
            Strategy recommendation with position sizing and tactics
        """
        if regime is None:
            regime = self.get_vix_regime()

        recommendations = {
            VIXRegime.LOW: StrategyRecommendation(
                regime=VIXRegime.LOW,
                allowed_strategies=[
                    "iron_condor",
                    "credit_spread",
                    "short_strangle",
                    "covered_call",
                    "cash_secured_put",
                ],
                position_size_multiplier=1.5,  # Aggressive sizing
                strike_width_adjustment="tighter",
                max_portfolio_theta=-500.0,  # Aggressive theta
                defensive_hedging=False,
                recommendation=(
                    "VIX LOW (complacency): Aggressively sell premium. "
                    "Iron condors with tight strikes, credit spreads, strangles. "
                    "Increase position size 1.5x. No hedging needed."
                ),
            ),
            VIXRegime.NORMAL: StrategyRecommendation(
                regime=VIXRegime.NORMAL,
                allowed_strategies=[
                    "iron_condor",
                    "credit_spread",
                    "short_strangle",
                    "covered_call",
                    "calendar_spread",
                ],
                position_size_multiplier=1.0,  # Normal sizing
                strike_width_adjustment="normal",
                max_portfolio_theta=-300.0,  # Standard theta
                defensive_hedging=False,
                recommendation=(
                    "VIX NORMAL: Standard theta strategies. "
                    "Iron condors, credit spreads at normal strikes. "
                    "Standard position sizing. Balanced risk/reward."
                ),
            ),
            VIXRegime.ELEVATED: StrategyRecommendation(
                regime=VIXRegime.ELEVATED,
                allowed_strategies=[
                    "iron_condor",
                    "credit_spread",
                    "calendar_spread",
                ],
                position_size_multiplier=0.7,  # Reduced sizing
                strike_width_adjustment="wider",
                max_portfolio_theta=-150.0,  # Reduced theta
                defensive_hedging=True,
                recommendation=(
                    "VIX ELEVATED (caution): Reduce position size to 70%. "
                    "Widen strikes for more room. Consider protective hedges. "
                    "Fewer iron condors, more credit spreads."
                ),
            ),
            VIXRegime.HIGH: StrategyRecommendation(
                regime=VIXRegime.HIGH,
                allowed_strategies=[
                    "long_put",
                    "put_spread",
                    "calendar_spread",
                ],
                position_size_multiplier=0.4,  # Heavily reduced
                strike_width_adjustment="wider",
                max_portfolio_theta=-50.0,  # Minimal theta
                defensive_hedging=True,
                recommendation=(
                    "VIX HIGH (fear): Defensive mode. Reduce size to 40%. "
                    "NO naked short options. Long puts for protection. "
                    "Consider cash or waiting for better entry."
                ),
            ),
            VIXRegime.EXTREME: StrategyRecommendation(
                regime=VIXRegime.EXTREME,
                allowed_strategies=[
                    "long_put",
                    "long_call",
                    "cash",
                ],
                position_size_multiplier=0.2,  # Minimal exposure
                strike_width_adjustment="wider",
                max_portfolio_theta=0.0,  # No negative theta
                defensive_hedging=True,
                recommendation=(
                    "VIX EXTREME (panic): CAPITAL PRESERVATION MODE. "
                    "Reduce exposure to 20%. Cash is a position. "
                    "Only long volatility or defensive positions. "
                    "Wait for regime change before aggressive deployment."
                ),
            ),
        }

        return recommendations[regime]

    def _handle_regime_change(
        self, old_regime: VIXRegime, new_regime: VIXRegime, vix_level: float
    ) -> None:
        """Handle VIX regime change and generate alert."""
        alert = VIXAlert(
            alert_type=AlertType.REGIME_CHANGE,
            timestamp=datetime.now(),
            message=f"VIX regime changed: {old_regime.value.upper()} → {new_regime.value.upper()} (VIX: {vix_level:.2f})",
            old_regime=old_regime,
            new_regime=new_regime,
            vix_level=vix_level,
            recommended_action=f"Adjust strategy per {new_regime.value} regime guidelines",
        )

        self.alerts.append(alert)
        logger.warning(f"REGIME CHANGE: {alert.message}")

        if self.alert_callback:
            self.alert_callback(alert)

    def _check_alerts(
        self, vix: float, regime: VIXRegime, term_structure: TermStructure, is_spike: bool
    ) -> None:
        """Check for various alert conditions."""
        now = datetime.now()

        # VIX spike alert
        if is_spike:
            alert = VIXAlert(
                alert_type=AlertType.VIX_SPIKE,
                timestamp=now,
                message=f"VIX SPIKE: Rapid increase to {vix:.2f} (+{self.SPIKE_THRESHOLD}+ points)",
                old_regime=None,
                new_regime=regime,
                vix_level=vix,
                recommended_action="Review all open positions, consider protective hedges",
            )
            self._add_alert(alert)

        # Term structure inversion
        if term_structure == TermStructure.BACKWARDATION:
            alert = VIXAlert(
                alert_type=AlertType.TERM_STRUCTURE_INVERSION,
                timestamp=now,
                message="VIX term structure inverted (backwardation) - near-term fear",
                old_regime=None,
                new_regime=regime,
                vix_level=vix,
                recommended_action="Caution: Market expects near-term volatility. Reduce exposure.",
            )
            self._add_alert(alert)

        # Extreme volatility
        if regime == VIXRegime.EXTREME:
            alert = VIXAlert(
                alert_type=AlertType.EXTREME_VOLATILITY,
                timestamp=now,
                message=f"EXTREME VOLATILITY: VIX at {vix:.2f} - Market panic mode",
                old_regime=None,
                new_regime=regime,
                vix_level=vix,
                recommended_action="CAPITAL PRESERVATION: Move to cash or long volatility only",
            )
            self._add_alert(alert)

        # Complacency warning
        if regime == VIXRegime.LOW and vix < 10:
            alert = VIXAlert(
                alert_type=AlertType.COMPLACENCY_WARNING,
                timestamp=now,
                message=f"COMPLACENCY: VIX at {vix:.2f} - Extreme low volatility",
                old_regime=None,
                new_regime=regime,
                vix_level=vix,
                recommended_action="Opportunity: Sell premium aggressively, but prepare for snapback",
            )
            self._add_alert(alert)

    def _add_alert(self, alert: VIXAlert) -> None:
        """Add alert if not duplicate of recent alert."""
        # Check for duplicate in last hour
        recent_cutoff = alert.timestamp - timedelta(hours=1)

        for existing in self.alerts:
            if existing.alert_type == alert.alert_type and existing.timestamp > recent_cutoff:
                return  # Don't add duplicate

        self.alerts.append(alert)
        logger.warning(f"VIX Alert: {alert.message}")

        if self.alert_callback:
            self.alert_callback(alert)

    def get_recent_alerts(self, hours: int = 24) -> list[VIXAlert]:
        """
        Get recent alerts.

        Args:
            hours: Number of hours to look back

        Returns:
            List of alerts from the last N hours
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        return [alert for alert in self.alerts if alert.timestamp >= cutoff]

    def generate_report(self) -> str:
        """
        Generate comprehensive VIX monitoring report.

        Returns:
            Formatted report string
        """
        try:
            data = self.get_current_vix_data()
            recommendation = self.get_strategy_recommendation(data.regime)
        except Exception as e:
            return f"ERROR: Failed to generate VIX report: {e}"

        report = []
        report.append("=" * 70)
        report.append("VIX VOLATILITY REGIME MONITOR")
        report.append("=" * 70)

        report.append(f"\nTimestamp: {data.timestamp.strftime('%Y-%m-%d %H:%M:%S ET')}")
        report.append(
            f"Last Update: {self.last_update.strftime('%Y-%m-%d %H:%M:%S ET') if self.last_update else 'N/A'}"
        )

        report.append("\n" + "-" * 70)
        report.append("CURRENT VIX LEVELS")
        report.append("-" * 70)

        report.append(f"\nVIX Index:           {data.vix:.2f}")
        if data.vix3m:
            report.append(f"VIX 3-Month:         {data.vix3m:.2f}")
            report.append(f"Spread (VIX3M-VIX):  {data.spread:+.2f}")
        else:
            report.append("VIX 3-Month:         N/A")

        if data.change_1d is not None:
            report.append(f"1-Day Change:        {data.change_1d:+.2f} points")

        report.append("\n" + "-" * 70)
        report.append("VOLATILITY REGIME")
        report.append("-" * 70)

        regime_display = {
            VIXRegime.LOW: "LOW (Complacency)",
            VIXRegime.NORMAL: "NORMAL (Standard)",
            VIXRegime.ELEVATED: "ELEVATED (Caution)",
            VIXRegime.HIGH: "HIGH (Fear)",
            VIXRegime.EXTREME: "EXTREME (Panic)",
        }

        report.append(f"\nCurrent Regime:      {regime_display[data.regime]}")
        report.append(f"Term Structure:      {data.term_structure.value.upper()}")
        report.append(f"VIX Spike Detected:  {'YES ⚠️' if data.is_spike else 'No'}")

        # Show regime thresholds
        report.append("\nRegime Thresholds:")
        for regime, (lower, upper) in self.REGIME_THRESHOLDS.items():
            marker = " <-- CURRENT" if regime == data.regime else ""
            report.append(f"  {regime.value.upper():12} {lower:5.0f} - {upper:5.0f}{marker}")

        report.append("\n" + "-" * 70)
        report.append("STRATEGY RECOMMENDATION")
        report.append("-" * 70)

        report.append(f"\n{recommendation.recommendation}")
        report.append(f"\nAllowed Strategies:  {', '.join(recommendation.allowed_strategies)}")
        report.append(
            f"Position Size:       {recommendation.position_size_multiplier:.1%} of normal"
        )
        report.append(f"Strike Width:        {recommendation.strike_width_adjustment}")
        report.append(f"Max Portfolio Theta: ${recommendation.max_portfolio_theta:.0f}/day")
        report.append(
            f"Defensive Hedging:   {'YES - Required' if recommendation.defensive_hedging else 'No'}"
        )

        # Recent alerts
        recent_alerts = self.get_recent_alerts(hours=24)
        if recent_alerts:
            report.append("\n" + "-" * 70)
            report.append("RECENT ALERTS (24 HOURS)")
            report.append("-" * 70)

            for alert in recent_alerts[-5:]:  # Last 5 alerts
                report.append(
                    f"\n  [{alert.alert_type.value.upper()}] {alert.timestamp.strftime('%H:%M')}"
                )
                report.append(f"    {alert.message}")
                report.append(f"    → {alert.recommended_action}")

        report.append("\n" + "=" * 70)

        return "\n".join(report)

    def _save_state(self) -> None:
        """Save VIX monitoring state to disk."""
        state = {
            "current_regime": self.current_regime.value if self.current_regime else None,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "vix_history": [(dt.isoformat(), vix) for dt, vix in self.vix_history],
            "alerts": [
                {
                    "type": a.alert_type.value,
                    "timestamp": a.timestamp.isoformat(),
                    "message": a.message,
                    "vix_level": a.vix_level,
                }
                for a in self.alerts
            ],
        }

        state_file = self.data_dir / "vix_monitor_state.json"
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)

        logger.debug(f"Saved VIX monitor state to {state_file}")

    def _load_state(self) -> bool:
        """Load VIX monitoring state from disk."""
        state_file = self.data_dir / "vix_monitor_state.json"

        if not state_file.exists():
            return False

        try:
            with open(state_file) as f:
                state = json.load(f)

            # Restore regime
            regime_str = state.get("current_regime")
            if regime_str:
                self.current_regime = VIXRegime(regime_str)

            # Restore last update
            last_update_str = state.get("last_update")
            if last_update_str:
                self.last_update = datetime.fromisoformat(last_update_str)

            # Restore history
            history = state.get("vix_history", [])
            self.vix_history = [(datetime.fromisoformat(dt), vix) for dt, vix in history]

            # Keep only recent history (30 days)
            cutoff = datetime.now() - timedelta(days=30)
            self.vix_history = [(ts, val) for ts, val in self.vix_history if ts >= cutoff]

            logger.info(f"Loaded VIX monitor state: {len(self.vix_history)} historical data points")
            return True

        except Exception as e:
            logger.error(f"Failed to load VIX monitor state: {e}")
            return False

    def save_to_disk(self) -> None:
        """Public method to save state."""
        self._save_state()


# Convenience function for quick VIX checks
def quick_vix_check() -> dict[str, Any]:
    """
    Quick VIX regime check for use in trading scripts.

    Returns:
        Dictionary with VIX level, regime, and strategy recommendation
    """
    monitor = VIXMonitor()

    try:
        data = monitor.get_current_vix_data()
        recommendation = monitor.get_strategy_recommendation(data.regime)

        return {
            "vix": data.vix,
            "regime": data.regime.value,
            "term_structure": data.term_structure.value,
            "is_spike": data.is_spike,
            "position_size_multiplier": recommendation.position_size_multiplier,
            "allowed_strategies": recommendation.allowed_strategies,
            "defensive_hedging_required": recommendation.defensive_hedging,
            "recommendation": recommendation.recommendation,
        }

    except Exception as e:
        logger.error(f"Quick VIX check failed: {e}")
        return {
            "vix": None,
            "regime": "unknown",
            "error": str(e),
            "position_size_multiplier": 0.5,  # Conservative fallback
            "allowed_strategies": ["cash"],
            "defensive_hedging_required": True,
            "recommendation": "Unable to fetch VIX - stay defensive",
        }


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    monitor = VIXMonitor()

    print("\n" + "=" * 70)
    print("VIX MONITOR DEMO")
    print("=" * 70 + "\n")

    # Generate and print report
    report = monitor.generate_report()
    print(report)

    # Save state
    monitor.save_to_disk()

    print("\n✅ VIX monitor demo complete")
