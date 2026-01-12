"""
VIX Circuit Breaker - Real Implementation

Protects against trading during high volatility periods.
Phil Town Rule #1: Don't lose money. This is the safety net.

Restored: January 12, 2026 (was stub since PR #1445)
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """VIX alert levels based on historical percentiles."""

    NORMAL = "normal"  # VIX < 15
    ELEVATED = "elevated"  # VIX 15-20
    HIGH = "high"  # VIX 20-25
    VERY_HIGH = "very_high"  # VIX 25-30
    EXTREME = "extreme"  # VIX 30-40
    SPIKE = "spike"  # VIX > 40


# VIX thresholds for trading decisions
VIX_THRESHOLDS = {
    AlertLevel.NORMAL: 15.0,
    AlertLevel.ELEVATED: 20.0,
    AlertLevel.HIGH: 25.0,
    AlertLevel.VERY_HIGH: 30.0,
    AlertLevel.EXTREME: 40.0,
}

# Position size multipliers based on VIX level
POSITION_MULTIPLIERS = {
    AlertLevel.NORMAL: 1.0,  # Full position
    AlertLevel.ELEVATED: 0.75,  # Reduce 25%
    AlertLevel.HIGH: 0.50,  # Half position
    AlertLevel.VERY_HIGH: 0.25,  # Quarter position
    AlertLevel.EXTREME: 0.0,  # No new positions
    AlertLevel.SPIKE: 0.0,  # HALT trading
}


@dataclass
class VIXStatus:
    """Current VIX status and trading guidance."""

    current_level: float
    alert_level: AlertLevel
    message: str
    position_multiplier: float = 1.0
    halt_trading: bool = False
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class VIXCircuitBreaker:
    """
    VIX-based circuit breaker for risk management.

    Phil Town doesn't trade during high volatility - this enforces that.
    """

    # Cache VIX for 5 minutes to avoid excessive API calls
    CACHE_TTL = timedelta(minutes=5)

    # Halt trading threshold
    HALT_THRESHOLD = 30.0  # VIX > 30 = no new trades

    def __init__(self, halt_threshold: float = 30.0):
        """
        Initialize VIX circuit breaker.

        Args:
            halt_threshold: VIX level above which trading halts (default 30)
        """
        self.halt_threshold = halt_threshold
        self._cached_status: Optional[VIXStatus] = None
        self._cache_time: Optional[datetime] = None

    def _fetch_vix(self) -> float:
        """Fetch current VIX level from market data."""
        try:
            # Try yfinance first
            from src.utils import yfinance_wrapper as yf

            vix = yf.Ticker("^VIX")
            hist = vix.history(period="1d")
            if not hist.empty:
                current_vix = float(hist["Close"].iloc[-1])
                logger.info(f"VIX fetched: {current_vix:.2f}")
                return current_vix
        except Exception as e:
            logger.warning(f"Failed to fetch VIX via yfinance: {e}")

        # Fallback to conservative estimate
        logger.warning("Using fallback VIX estimate of 20.0")
        return 20.0

    def _get_alert_level(self, vix: float) -> AlertLevel:
        """Determine alert level from VIX value."""
        if vix >= 40:
            return AlertLevel.SPIKE
        elif vix >= 30:
            return AlertLevel.EXTREME
        elif vix >= 25:
            return AlertLevel.VERY_HIGH
        elif vix >= 20:
            return AlertLevel.HIGH
        elif vix >= 15:
            return AlertLevel.ELEVATED
        else:
            return AlertLevel.NORMAL

    def get_current_status(self, force_refresh: bool = False) -> VIXStatus:
        """
        Get current VIX status with caching.

        Args:
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            VIXStatus with current level and trading guidance
        """
        now = datetime.now()

        # Check cache
        if (
            not force_refresh
            and self._cached_status
            and self._cache_time
            and (now - self._cache_time) < self.CACHE_TTL
        ):
            return self._cached_status

        # Fetch fresh VIX
        vix_level = self._fetch_vix()
        alert_level = self._get_alert_level(vix_level)
        multiplier = POSITION_MULTIPLIERS.get(alert_level, 1.0)
        halt = vix_level >= self.halt_threshold

        # Generate message
        if halt:
            message = f"⛔ TRADING HALTED: VIX at {vix_level:.1f} exceeds {self.halt_threshold}"
        elif alert_level == AlertLevel.EXTREME:
            message = f"🔴 EXTREME volatility: VIX {vix_level:.1f} - minimal positions only"
        elif alert_level == AlertLevel.VERY_HIGH:
            message = f"🟠 Very high volatility: VIX {vix_level:.1f} - reduce positions 75%"
        elif alert_level == AlertLevel.HIGH:
            message = f"🟡 High volatility: VIX {vix_level:.1f} - reduce positions 50%"
        elif alert_level == AlertLevel.ELEVATED:
            message = f"⚠️ Elevated volatility: VIX {vix_level:.1f} - reduce positions 25%"
        else:
            message = f"✅ Normal volatility: VIX {vix_level:.1f} - full positions allowed"

        status = VIXStatus(
            current_level=vix_level,
            alert_level=alert_level,
            message=message,
            position_multiplier=multiplier,
            halt_trading=halt,
        )

        # Update cache
        self._cached_status = status
        self._cache_time = now

        logger.info(f"VIX Status: {message}")
        return status

    def should_halt_trading(self) -> bool:
        """
        Check if trading should be halted due to VIX.

        Returns:
            True if VIX exceeds halt threshold
        """
        status = self.get_current_status()
        return status.halt_trading

    def get_position_multiplier(self) -> float:
        """
        Get position size multiplier based on current VIX.

        Returns:
            Float between 0.0 and 1.0 for position sizing
        """
        status = self.get_current_status()
        return status.position_multiplier

    def check_trade_allowed(self, symbol: str = None) -> tuple[bool, str]:
        """
        Check if a trade is allowed given current VIX.

        Args:
            symbol: Optional symbol (for logging)

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        status = self.get_current_status()

        if status.halt_trading:
            return False, f"Trading halted: {status.message}"

        if status.position_multiplier == 0:
            return False, f"No new positions: {status.message}"

        return True, status.message
