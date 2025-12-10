"""
VIX Monitoring and Volatility Regime Detection

Comprehensive VIX analysis system for options trading strategy selection:
1. Real-time VIX data fetching via Alpaca/yfinance
2. Historical VIX percentile calculation
3. VIX term structure analysis (VX futures curve)
4. Contango/backwardation detection
5. VVIX (volatility of VIX) monitoring
6. Volatility regime classification
7. Position sizing recommendations
8. Strategy recommendations based on VIX regime

Author: Claude (CTO)
Created: 2025-12-10
"""

import json
import logging
import os
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np
import yfinance as yf
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

logger = logging.getLogger(__name__)


class VolatilityRegime(Enum):
    """
    Volatility regimes based on VIX levels and historical context.

    Regimes guide options strategy selection:
    - EXTREME_LOW: Aggressive premium selling, high confidence
    - LOW: Premium selling with larger positions
    - NORMAL: Standard strategies, balanced approach
    - ELEVATED: Reduce position sizes, cautious
    - HIGH: Buy volatility, hedge existing positions
    - EXTREME: Crisis mode, capital preservation priority
    """
    EXTREME_LOW = "extreme_low"    # VIX < 12
    LOW = "low"                    # VIX 12-15
    NORMAL = "normal"              # VIX 15-20
    ELEVATED = "elevated"          # VIX 20-25
    HIGH = "high"                  # VIX 25-35
    EXTREME = "extreme"            # VIX > 35


class TermStructureState(Enum):
    """VIX futures term structure state"""
    CONTANGO = "contango"              # Normal: VX2 > VX1 (decay works in our favor)
    BACKWARDATION = "backwardation"    # Fear: VX1 > VX2 (expect volatility spike)
    FLAT = "flat"                      # Neutral


class VIXMonitor:
    """
    VIX Monitoring and Analysis System

    Fetches real-time VIX data, calculates historical percentiles,
    monitors term structure, and provides volatility regime classification.
    """

    # VIX regime thresholds
    REGIME_THRESHOLDS = {
        VolatilityRegime.EXTREME_LOW: (0, 12),
        VolatilityRegime.LOW: (12, 15),
        VolatilityRegime.NORMAL: (15, 20),
        VolatilityRegime.ELEVATED: (20, 25),
        VolatilityRegime.HIGH: (25, 35),
        VolatilityRegime.EXTREME: (35, 100),
    }

    # Historical data storage
    VIX_HISTORY_FILE = "/home/user/trading/data/vix_history.json"

    def __init__(self, use_alpaca: bool = True):
        """
        Initialize VIX Monitor.

        Args:
            use_alpaca: If True, use Alpaca API for VIX data (fallback to yfinance)
        """
        self.use_alpaca = use_alpaca

        # Initialize Alpaca client if enabled
        if use_alpaca:
            try:
                api_key = os.getenv("ALPACA_API_KEY")
                secret_key = os.getenv("ALPACA_SECRET_KEY")

                if api_key and secret_key:
                    self.alpaca_client = StockHistoricalDataClient(
                        api_key=api_key,
                        secret_key=secret_key
                    )
                    logger.info("Alpaca client initialized for VIX data")
                else:
                    logger.warning("Alpaca credentials missing, falling back to yfinance")
                    self.alpaca_client = None
            except Exception as e:
                logger.warning(f"Alpaca initialization failed: {e}, using yfinance")
                self.alpaca_client = None
        else:
            self.alpaca_client = None

        # Ensure data directory exists
        Path(self.VIX_HISTORY_FILE).parent.mkdir(parents=True, exist_ok=True)

        # Load historical VIX data
        self.vix_history = self._load_vix_history()

        logger.info("VIXMonitor initialized successfully")

    def get_current_vix(self) -> float:
        """
        Fetch real-time VIX value.

        Tries Alpaca first, falls back to yfinance if unavailable.

        Returns:
            Current VIX value

        Raises:
            RuntimeError: If unable to fetch VIX from any source
        """
        try:
            # Try Alpaca first
            if self.alpaca_client:
                try:
                    request = StockBarsRequest(
                        symbol_or_symbols="VIX",
                        timeframe=TimeFrame.Day,
                        start=datetime.now() - timedelta(days=2),
                        end=datetime.now()
                    )
                    bars = self.alpaca_client.get_stock_bars(request)

                    if "VIX" in bars.data and len(bars.data["VIX"]) > 0:
                        latest_bar = bars.data["VIX"][-1]
                        vix_value = float(latest_bar.close)
                        logger.info(f"Current VIX (Alpaca): {vix_value:.2f}")
                        return vix_value
                except Exception as e:
                    logger.warning(f"Alpaca VIX fetch failed: {e}, trying yfinance")

            # Fallback to yfinance
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period="1d")

            if vix_data.empty:
                raise RuntimeError("VIX data is empty from yfinance")

            vix_value = float(vix_data['Close'].iloc[-1])
            logger.info(f"Current VIX (yfinance): {vix_value:.2f}")

            # Store in history
            self._update_vix_history(vix_value)

            return vix_value

        except Exception as e:
            logger.error(f"Failed to fetch VIX: {e}")
            raise RuntimeError(f"Unable to fetch VIX data: {e}")

    def get_vix_percentile(self, lookback_days: int = 252) -> float:
        """
        Calculate VIX percentile over historical period.

        Args:
            lookback_days: Number of trading days to look back (default: 252 = 1 year)

        Returns:
            VIX percentile (0-100)
        """
        try:
            current_vix = self.get_current_vix()

            # Fetch historical VIX data
            vix = yf.Ticker("^VIX")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=int(lookback_days * 1.4))  # Account for weekends

            hist = vix.history(start=start_date, end=end_date)

            if hist.empty or len(hist) < 30:
                logger.warning(f"Insufficient VIX history: {len(hist)} days")
                return 50.0  # Default to median

            # Calculate percentile
            historical_closes = hist['Close'].values
            percentile = (np.sum(historical_closes < current_vix) / len(historical_closes)) * 100

            logger.info(
                f"VIX Percentile: {percentile:.1f}% "
                f"(Current: {current_vix:.2f}, {lookback_days}-day lookback)"
            )

            return float(percentile)

        except Exception as e:
            logger.error(f"Failed to calculate VIX percentile: {e}")
            return 50.0  # Default to median on error

    def get_vix_term_structure(self) -> dict[str, float]:
        """
        Get VIX futures term structure (VX1, VX2, VX3, etc.).

        VIX futures represent expected VIX at different maturities.

        Returns:
            Dict with VX1, VX2, VX3 values and term structure slope

        Note:
            VIX futures data may require special data feed.
            Currently using proxy calculation via VIX and VXV.
        """
        try:
            # Fetch VIX (30-day) and VXV (3-month) as proxies
            vix_ticker = yf.Ticker("^VIX")
            vxv_ticker = yf.Ticker("^VXV")

            vix_data = vix_ticker.history(period="1d")
            vxv_data = vxv_ticker.history(period="1d")

            if vix_data.empty or vxv_data.empty:
                raise RuntimeError("Unable to fetch VIX term structure data")

            vix_30d = float(vix_data['Close'].iloc[-1])
            vxv_3m = float(vxv_data['Close'].iloc[-1])

            # Approximate term structure
            # VX1 ≈ VIX, VX2 interpolated, VX3 ≈ VXV
            vx1 = vix_30d
            vx2 = (vix_30d + vxv_3m) / 2  # Linear interpolation
            vx3 = vxv_3m

            # Calculate slope (indicates contango/backwardation)
            slope_1_2 = vx2 - vx1
            slope_2_3 = vx3 - vx2
            overall_slope = vx3 - vx1

            term_structure = {
                "vx1": vx1,
                "vx2": vx2,
                "vx3": vx3,
                "slope_1_2": slope_1_2,
                "slope_2_3": slope_2_3,
                "overall_slope": overall_slope,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                f"VIX Term Structure: VX1={vx1:.2f}, VX2={vx2:.2f}, VX3={vx3:.2f}, "
                f"Slope={overall_slope:.2f}"
            )

            return term_structure

        except Exception as e:
            logger.error(f"Failed to fetch VIX term structure: {e}")
            return {
                "vx1": 0.0,
                "vx2": 0.0,
                "vx3": 0.0,
                "slope_1_2": 0.0,
                "slope_2_3": 0.0,
                "overall_slope": 0.0,
                "error": str(e),
            }

    def is_contango(self, threshold: float = 0.5) -> bool:
        """
        Check if VIX term structure is in contango.

        Contango: VX2 > VX1 (normal market, volatility expected to decay)

        Args:
            threshold: Minimum slope to confirm contango (default: 0.5)

        Returns:
            True if in contango
        """
        term_structure = self.get_vix_term_structure()
        slope = term_structure.get("overall_slope", 0.0)

        is_contango_state = slope > threshold

        logger.info(
            f"Term structure: {'CONTANGO' if is_contango_state else 'NOT CONTANGO'} "
            f"(slope: {slope:.2f})"
        )

        return is_contango_state

    def is_backwardation(self, threshold: float = -0.5) -> bool:
        """
        Check if VIX term structure is in backwardation.

        Backwardation: VX1 > VX2 (fear mode, expect volatility spike)

        Args:
            threshold: Maximum slope to confirm backwardation (default: -0.5)

        Returns:
            True if in backwardation
        """
        term_structure = self.get_vix_term_structure()
        slope = term_structure.get("overall_slope", 0.0)

        is_backwardation_state = slope < threshold

        logger.info(
            f"Term structure: {'BACKWARDATION' if is_backwardation_state else 'NOT BACKWARDATION'} "
            f"(slope: {slope:.2f})"
        )

        return is_backwardation_state

    def get_term_structure_state(self) -> TermStructureState:
        """
        Get current term structure state classification.

        Returns:
            TermStructureState enum
        """
        if self.is_backwardation():
            return TermStructureState.BACKWARDATION
        elif self.is_contango():
            return TermStructureState.CONTANGO
        else:
            return TermStructureState.FLAT

    def get_vvix(self) -> float:
        """
        Get VVIX (volatility of VIX).

        VVIX measures expected volatility of the VIX itself.
        High VVIX = unstable VIX, expect sudden moves.

        Returns:
            VVIX value (or 0.0 if unavailable)
        """
        try:
            vvix = yf.Ticker("^VVIX")
            vvix_data = vvix.history(period="1d")

            if vvix_data.empty:
                logger.warning("VVIX data unavailable")
                return 0.0

            vvix_value = float(vvix_data['Close'].iloc[-1])
            logger.info(f"Current VVIX: {vvix_value:.2f}")

            return vvix_value

        except Exception as e:
            logger.warning(f"Failed to fetch VVIX: {e}")
            return 0.0

    def get_volatility_regime(self, vix_value: Optional[float] = None) -> VolatilityRegime:
        """
        Classify current volatility regime based on VIX level.

        Args:
            vix_value: VIX value to classify (fetches current if None)

        Returns:
            VolatilityRegime enum
        """
        if vix_value is None:
            vix_value = self.get_current_vix()

        for regime, (low, high) in self.REGIME_THRESHOLDS.items():
            if low <= vix_value < high:
                logger.info(f"Volatility Regime: {regime.value.upper()} (VIX: {vix_value:.2f})")
                return regime

        # Fallback to EXTREME if VIX is extremely high
        return VolatilityRegime.EXTREME

    def calculate_vix_statistics(self, lookback_days: int = 252) -> dict[str, float]:
        """
        Calculate comprehensive VIX statistics.

        Args:
            lookback_days: Historical lookback period

        Returns:
            Dict with mean, std, min, max, current, percentile
        """
        try:
            vix = yf.Ticker("^VIX")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=int(lookback_days * 1.4))

            hist = vix.history(start=start_date, end=end_date)

            if hist.empty:
                raise RuntimeError("No VIX historical data available")

            closes = hist['Close'].values
            current_vix = self.get_current_vix()

            stats = {
                "current": float(current_vix),
                "mean": float(np.mean(closes)),
                "median": float(np.median(closes)),
                "std": float(np.std(closes)),
                "min": float(np.min(closes)),
                "max": float(np.max(closes)),
                "percentile": self.get_vix_percentile(lookback_days),
                "z_score": (current_vix - np.mean(closes)) / np.std(closes),
                "lookback_days": lookback_days,
                "data_points": len(closes),
            }

            logger.info(
                f"VIX Statistics ({lookback_days}d): "
                f"Current={stats['current']:.2f}, Mean={stats['mean']:.2f}, "
                f"Std={stats['std']:.2f}, Percentile={stats['percentile']:.1f}%"
            )

            return stats

        except Exception as e:
            logger.error(f"Failed to calculate VIX statistics: {e}")
            return {
                "current": 0.0,
                "mean": 0.0,
                "median": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "percentile": 50.0,
                "z_score": 0.0,
                "error": str(e),
            }

    def detect_vix_spike(self, threshold_z_score: float = 2.0) -> dict[str, Any]:
        """
        Detect if VIX is spiking (sudden increase above normal).

        Args:
            threshold_z_score: Z-score threshold for spike detection

        Returns:
            Dict with spike status and details
        """
        stats = self.calculate_vix_statistics()
        z_score = stats.get("z_score", 0.0)

        is_spike = z_score > threshold_z_score

        spike_info = {
            "is_spike": is_spike,
            "z_score": z_score,
            "current_vix": stats["current"],
            "mean_vix": stats["mean"],
            "std_vix": stats["std"],
            "severity": self._classify_spike_severity(z_score),
            "timestamp": datetime.now().isoformat(),
        }

        if is_spike:
            logger.warning(
                f"⚠️ VIX SPIKE DETECTED! Z-score: {z_score:.2f}, "
                f"Current: {stats['current']:.2f}, Mean: {stats['mean']:.2f}"
            )
        else:
            logger.info(f"No VIX spike (Z-score: {z_score:.2f})")

        return spike_info

    def calculate_mean_reversion_probability(self) -> float:
        """
        Calculate probability of VIX mean reversion.

        High VIX tends to revert to mean (historically ~16-18).

        Returns:
            Probability (0-1) that VIX will revert lower
        """
        stats = self.calculate_vix_statistics()
        current = stats["current"]
        mean = stats["mean"]
        std = stats["std"]

        if current <= mean:
            # Already below mean, less likely to drop further
            return 0.3

        # Calculate how far above mean (in standard deviations)
        z_score = (current - mean) / std

        # Higher z-score = higher reversion probability
        # Cap at 0.95 (never 100% certain)
        reversion_prob = min(0.95, 0.5 + (z_score * 0.15))

        logger.info(
            f"Mean reversion probability: {reversion_prob*100:.1f}% "
            f"(VIX {current:.2f} vs Mean {mean:.2f}, Z={z_score:.2f})"
        )

        return float(reversion_prob)

    def _classify_spike_severity(self, z_score: float) -> str:
        """Classify VIX spike severity"""
        if z_score < 1.0:
            return "none"
        elif z_score < 2.0:
            return "mild"
        elif z_score < 3.0:
            return "moderate"
        elif z_score < 4.0:
            return "severe"
        else:
            return "extreme"

    def _load_vix_history(self) -> dict[str, Any]:
        """Load VIX history from JSON file"""
        try:
            if os.path.exists(self.VIX_HISTORY_FILE):
                with open(self.VIX_HISTORY_FILE) as f:
                    history = json.load(f)
                    logger.info(f"Loaded VIX history: {len(history.get('daily_values', []))} days")
                    return history
        except Exception as e:
            logger.warning(f"Failed to load VIX history: {e}")

        # Return empty structure
        return {
            "daily_values": [],
            "last_updated": None,
            "metadata": {
                "created": datetime.now().isoformat(),
                "source": "vix_monitor",
            }
        }

    def _update_vix_history(self, vix_value: float) -> None:
        """Update VIX history with new value"""
        try:
            today = datetime.now().date().isoformat()

            # Check if we already have today's value
            daily_values = self.vix_history.get("daily_values", [])

            # Remove today's value if it exists (we'll replace it)
            daily_values = [v for v in daily_values if v.get("date") != today]

            # Add new value
            daily_values.append({
                "date": today,
                "vix": vix_value,
                "timestamp": datetime.now().isoformat(),
            })

            # Keep only last 2 years (504 trading days)
            if len(daily_values) > 504:
                daily_values = daily_values[-504:]

            self.vix_history["daily_values"] = daily_values
            self.vix_history["last_updated"] = datetime.now().isoformat()

            # Save to file
            with open(self.VIX_HISTORY_FILE, 'w') as f:
                json.dump(self.vix_history, f, indent=2)

            logger.debug(f"Updated VIX history: {vix_value:.2f} ({today})")

        except Exception as e:
            logger.error(f"Failed to update VIX history: {e}")

    def export_state(self) -> dict[str, Any]:
        """
        Export current VIX state for system_state.json integration.

        Returns:
            Dict with all VIX metrics for system state
        """
        try:
            current_vix = self.get_current_vix()
            regime = self.get_volatility_regime(current_vix)
            percentile = self.get_vix_percentile()
            stats = self.calculate_vix_statistics()
            term_structure = self.get_vix_term_structure()
            spike_info = self.detect_vix_spike()
            vvix = self.get_vvix()

            state = {
                "current_vix": current_vix,
                "volatility_regime": regime.value,
                "vix_percentile": percentile,
                "term_structure": {
                    "state": self.get_term_structure_state().value,
                    "vx1": term_structure.get("vx1", 0.0),
                    "vx2": term_structure.get("vx2", 0.0),
                    "vx3": term_structure.get("vx3", 0.0),
                    "slope": term_structure.get("overall_slope", 0.0),
                },
                "statistics": {
                    "mean": stats["mean"],
                    "std": stats["std"],
                    "z_score": stats["z_score"],
                    "min_1y": stats["min"],
                    "max_1y": stats["max"],
                },
                "vvix": vvix,
                "spike_detected": spike_info["is_spike"],
                "spike_severity": spike_info["severity"],
                "mean_reversion_probability": self.calculate_mean_reversion_probability(),
                "last_updated": datetime.now().isoformat(),
            }

            return state

        except Exception as e:
            logger.error(f"Failed to export VIX state: {e}")
            return {
                "error": str(e),
                "last_updated": datetime.now().isoformat(),
            }


class VIXSignals:
    """
    VIX-based trading signals for options strategies.

    Provides actionable recommendations:
    - When to sell premium (high VIX)
    - When to buy premium (low VIX)
    - Position size multipliers
    - Strategy recommendations
    """

    def __init__(self, vix_monitor: Optional[VIXMonitor] = None):
        """
        Initialize VIX Signals generator.

        Args:
            vix_monitor: VIXMonitor instance (creates new if None)
        """
        self.vix_monitor = vix_monitor or VIXMonitor()
        logger.info("VIXSignals initialized")

    def should_sell_premium(self) -> dict[str, Any]:
        """
        Determine if conditions favor premium selling.

        Sell premium when:
        - VIX is high (> 20) AND
        - VIX is likely to revert lower (mean reversion)

        Returns:
            Dict with recommendation and reasoning
        """
        current_vix = self.vix_monitor.get_current_vix()
        regime = self.vix_monitor.get_volatility_regime(current_vix)
        percentile = self.vix_monitor.get_vix_percentile()
        reversion_prob = self.vix_monitor.calculate_mean_reversion_probability()

        # Premium selling criteria
        should_sell = (
            regime in [VolatilityRegime.ELEVATED, VolatilityRegime.HIGH, VolatilityRegime.EXTREME]
            and percentile > 60
            and reversion_prob > 0.6
        )

        confidence = "HIGH" if reversion_prob > 0.75 else "MEDIUM" if reversion_prob > 0.6 else "LOW"

        recommendation = {
            "should_sell_premium": should_sell,
            "confidence": confidence,
            "current_vix": current_vix,
            "regime": regime.value,
            "percentile": percentile,
            "reversion_probability": reversion_prob,
            "rationale": self._build_sell_rationale(should_sell, current_vix, regime, percentile, reversion_prob),
            "recommended_strategies": self._get_premium_selling_strategies(regime) if should_sell else [],
        }

        logger.info(
            f"Premium Selling Signal: {should_sell} ({confidence} confidence) - "
            f"VIX {current_vix:.2f}, Regime: {regime.value}"
        )

        return recommendation

    def should_buy_premium(self) -> dict[str, Any]:
        """
        Determine if conditions favor premium buying.

        Buy premium when:
        - VIX is low (< 15) AND
        - VIX is likely to expand (backwardation or rising trend)

        Returns:
            Dict with recommendation and reasoning
        """
        current_vix = self.vix_monitor.get_current_vix()
        regime = self.vix_monitor.get_volatility_regime(current_vix)
        percentile = self.vix_monitor.get_vix_percentile()
        term_state = self.vix_monitor.get_term_structure_state()

        # Premium buying criteria
        should_buy = (
            regime in [VolatilityRegime.EXTREME_LOW, VolatilityRegime.LOW]
            and percentile < 40
            and term_state == TermStructureState.BACKWARDATION  # Fear building
        )

        # Also consider buying if VIX extremely low even in contango
        if regime == VolatilityRegime.EXTREME_LOW and percentile < 20:
            should_buy = True

        confidence = "HIGH" if percentile < 20 else "MEDIUM" if percentile < 40 else "LOW"

        recommendation = {
            "should_buy_premium": should_buy,
            "confidence": confidence,
            "current_vix": current_vix,
            "regime": regime.value,
            "percentile": percentile,
            "term_structure": term_state.value,
            "rationale": self._build_buy_rationale(should_buy, current_vix, regime, percentile, term_state),
            "recommended_strategies": self._get_premium_buying_strategies(regime) if should_buy else [],
        }

        logger.info(
            f"Premium Buying Signal: {should_buy} ({confidence} confidence) - "
            f"VIX {current_vix:.2f}, Regime: {regime.value}"
        )

        return recommendation

    def get_position_size_multiplier(self) -> dict[str, Any]:
        """
        Calculate position size multiplier based on VIX regime.

        Lower VIX = larger positions (less risk)
        Higher VIX = smaller positions (more risk)

        Returns:
            Dict with multiplier and reasoning
        """
        regime = self.vix_monitor.get_volatility_regime()
        percentile = self.vix_monitor.get_vix_percentile()

        # Position size multipliers by regime
        multipliers = {
            VolatilityRegime.EXTREME_LOW: 1.5,   # 50% larger positions
            VolatilityRegime.LOW: 1.25,          # 25% larger
            VolatilityRegime.NORMAL: 1.0,        # Standard size
            VolatilityRegime.ELEVATED: 0.75,     # 25% smaller
            VolatilityRegime.HIGH: 0.5,          # 50% smaller
            VolatilityRegime.EXTREME: 0.25,      # 75% smaller
        }

        base_multiplier = multipliers[regime]

        # Fine-tune based on percentile
        if percentile < 10:
            multiplier = base_multiplier * 1.2  # Extra aggressive in extremely low VIX
        elif percentile > 90:
            multiplier = base_multiplier * 0.8  # Extra conservative in extremely high VIX
        else:
            multiplier = base_multiplier

        # Cap at reasonable bounds
        multiplier = max(0.1, min(2.0, multiplier))

        result = {
            "multiplier": multiplier,
            "regime": regime.value,
            "percentile": percentile,
            "guidance": self._get_position_size_guidance(multiplier),
        }

        logger.info(
            f"Position Size Multiplier: {multiplier:.2f}x "
            f"(Regime: {regime.value}, Percentile: {percentile:.1f}%)"
        )

        return result

    def get_strategy_recommendation(self) -> dict[str, Any]:
        """
        Get comprehensive strategy recommendation based on current VIX regime.

        Returns:
            Dict with strategy recommendations, position sizing, and entry/exit rules
        """
        current_vix = self.vix_monitor.get_current_vix()
        regime = self.vix_monitor.get_volatility_regime(current_vix)
        percentile = self.vix_monitor.get_vix_percentile()
        term_state = self.vix_monitor.get_term_structure_state()
        sell_signal = self.should_sell_premium()
        buy_signal = self.should_buy_premium()
        position_size = self.get_position_size_multiplier()

        recommendation = {
            "primary_action": self._get_primary_action(sell_signal, buy_signal),
            "regime": regime.value,
            "current_vix": current_vix,
            "percentile": percentile,
            "term_structure": term_state.value,
            "position_size_multiplier": position_size["multiplier"],
            "recommended_strategies": self._get_all_strategy_recommendations(regime, sell_signal, buy_signal),
            "risk_level": self._get_risk_level(regime),
            "entry_rules": self._get_entry_rules(regime),
            "exit_rules": self._get_exit_rules(regime),
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            f"Strategy Recommendation: {recommendation['primary_action']} "
            f"(Regime: {regime.value}, VIX: {current_vix:.2f})"
        )

        return recommendation

    # ==================== Helper Methods ====================

    def _build_sell_rationale(
        self, should_sell: bool, vix: float, regime: VolatilityRegime,
        percentile: float, reversion_prob: float
    ) -> str:
        """Build rationale for premium selling recommendation"""
        if should_sell:
            return (
                f"VIX at {vix:.2f} ({regime.value}, {percentile:.0f}th percentile) with "
                f"{reversion_prob*100:.0f}% mean reversion probability. "
                f"Options are expensive - SELL PREMIUM to collect high credit and benefit from VIX decay."
            )
        else:
            return (
                f"VIX at {vix:.2f} ({regime.value}, {percentile:.0f}th percentile) does not favor premium selling. "
                f"Wait for VIX > 20 with high reversion probability."
            )

    def _build_buy_rationale(
        self, should_buy: bool, vix: float, regime: VolatilityRegime,
        percentile: float, term_state: TermStructureState
    ) -> str:
        """Build rationale for premium buying recommendation"""
        if should_buy:
            return (
                f"VIX at {vix:.2f} ({regime.value}, {percentile:.0f}th percentile) with "
                f"term structure in {term_state.value}. Options are cheap - BUY PREMIUM "
                f"to position for potential volatility expansion."
            )
        else:
            return (
                f"VIX at {vix:.2f} ({regime.value}, {percentile:.0f}th percentile) does not favor premium buying. "
                f"Wait for VIX < 15 in low percentile with backwardation."
            )

    def _get_premium_selling_strategies(self, regime: VolatilityRegime) -> list[str]:
        """Get recommended premium selling strategies by regime"""
        if regime == VolatilityRegime.EXTREME:
            return ["Credit Spreads (defined risk)", "Iron Condors (wide)", "Cash-Secured Puts"]
        elif regime == VolatilityRegime.HIGH:
            return ["Iron Condors", "Credit Spreads", "Covered Calls", "Short Strangles"]
        elif regime == VolatilityRegime.ELEVATED:
            return ["Iron Condors", "Bull Put Spreads", "Bear Call Spreads"]
        else:
            return []

    def _get_premium_buying_strategies(self, regime: VolatilityRegime) -> list[str]:
        """Get recommended premium buying strategies by regime"""
        if regime == VolatilityRegime.EXTREME_LOW:
            return ["Long Straddles", "Long Strangles", "Debit Spreads", "Long Calls/Puts"]
        elif regime == VolatilityRegime.LOW:
            return ["Debit Spreads", "Long Calls (bullish)", "Long Puts (bearish)"]
        else:
            return []

    def _get_position_size_guidance(self, multiplier: float) -> str:
        """Get human-readable position sizing guidance"""
        if multiplier >= 1.5:
            return "AGGRESSIVE: Take larger positions (1.5-2x normal)"
        elif multiplier >= 1.1:
            return "MODERATELY AGGRESSIVE: Slightly larger positions (1.1-1.5x normal)"
        elif multiplier >= 0.9:
            return "STANDARD: Normal position sizing"
        elif multiplier >= 0.5:
            return "CONSERVATIVE: Reduce position sizes (50-90% of normal)"
        else:
            return "VERY CONSERVATIVE: Minimal positions (10-50% of normal)"

    def _get_primary_action(self, sell_signal: dict, buy_signal: dict) -> str:
        """Determine primary trading action"""
        if sell_signal["should_sell_premium"]:
            return "SELL_PREMIUM"
        elif buy_signal["should_buy_premium"]:
            return "BUY_PREMIUM"
        else:
            return "WAIT"

    def _get_all_strategy_recommendations(
        self, regime: VolatilityRegime, sell_signal: dict, buy_signal: dict
    ) -> list[dict[str, str]]:
        """Get comprehensive strategy recommendations"""
        strategies = []

        if sell_signal["should_sell_premium"]:
            for strat in sell_signal["recommended_strategies"]:
                strategies.append({
                    "strategy": strat,
                    "action": "SELL",
                    "priority": "HIGH" if regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME] else "MEDIUM"
                })

        if buy_signal["should_buy_premium"]:
            for strat in buy_signal["recommended_strategies"]:
                strategies.append({
                    "strategy": strat,
                    "action": "BUY",
                    "priority": "HIGH" if regime == VolatilityRegime.EXTREME_LOW else "MEDIUM"
                })

        if not strategies:
            strategies.append({
                "strategy": "WAIT - No clear edge",
                "action": "WAIT",
                "priority": "N/A"
            })

        return strategies

    def _get_risk_level(self, regime: VolatilityRegime) -> str:
        """Get current risk level"""
        risk_map = {
            VolatilityRegime.EXTREME_LOW: "LOW",
            VolatilityRegime.LOW: "LOW-MEDIUM",
            VolatilityRegime.NORMAL: "MEDIUM",
            VolatilityRegime.ELEVATED: "MEDIUM-HIGH",
            VolatilityRegime.HIGH: "HIGH",
            VolatilityRegime.EXTREME: "EXTREME",
        }
        return risk_map.get(regime, "MEDIUM")

    def _get_entry_rules(self, regime: VolatilityRegime) -> list[str]:
        """Get entry rules based on regime"""
        if regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]:
            return [
                "Wait for VIX to stabilize (no further spikes)",
                "Use limit orders (wide bid-ask spreads)",
                "Enter credit spreads (defined risk)",
                "Target 30-45 DTE",
            ]
        elif regime in [VolatilityRegime.EXTREME_LOW, VolatilityRegime.LOW]:
            return [
                "Enter on quiet days (no catalyst upcoming)",
                "Use debit spreads to limit cost",
                "Target 45-60 DTE for vol expansion",
                "Consider calendar spreads",
            ]
        else:
            return [
                "Standard entry rules apply",
                "30-45 DTE for premium selling",
                "45-60 DTE for debit strategies",
            ]

    def _get_exit_rules(self, regime: VolatilityRegime) -> list[str]:
        """Get exit rules based on regime"""
        if regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]:
            return [
                "Take profits quickly (50% of max profit)",
                "Exit by 21 DTE to avoid gamma risk",
                "Close if VIX spikes another 20%+",
                "Use stop-loss at 2x credit received",
            ]
        elif regime in [VolatilityRegime.EXTREME_LOW, VolatilityRegime.LOW]:
            return [
                "Exit when VIX expands 20%+ (take profit)",
                "Hold longer for vol expansion (50-75% profit target)",
                "Stop-loss at 50% of debit paid",
            ]
        else:
            return [
                "Standard exit: 50% max profit or 21 DTE",
                "Stop-loss: 2x credit or 50% debit",
            ]


# Convenience functions
def get_vix_monitor() -> VIXMonitor:
    """Get VIXMonitor instance"""
    return VIXMonitor()


def get_vix_signals() -> VIXSignals:
    """Get VIXSignals instance"""
    return VIXSignals()


if __name__ == "__main__":
    """
    Example usage and testing.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("\n" + "="*80)
    print("VIX MONITORING AND VOLATILITY REGIME DETECTION")
    print("="*80)

    # Initialize monitor
    monitor = VIXMonitor()

    print("\n--- Current VIX Metrics ---")
    current_vix = monitor.get_current_vix()
    print(f"Current VIX: {current_vix:.2f}")

    regime = monitor.get_volatility_regime()
    print(f"Volatility Regime: {regime.value.upper()}")

    percentile = monitor.get_vix_percentile()
    print(f"VIX Percentile (1Y): {percentile:.1f}%")

    print("\n--- VIX Statistics (1 Year) ---")
    stats = monitor.calculate_vix_statistics()
    print(f"Mean: {stats['mean']:.2f}")
    print(f"Std Dev: {stats['std']:.2f}")
    print(f"Min: {stats['min']:.2f}")
    print(f"Max: {stats['max']:.2f}")
    print(f"Z-Score: {stats['z_score']:.2f}")

    print("\n--- VIX Term Structure ---")
    term = monitor.get_vix_term_structure()
    print(f"VX1 (Front Month): {term['vx1']:.2f}")
    print(f"VX2 (Second Month): {term['vx2']:.2f}")
    print(f"VX3 (Third Month): {term['vx3']:.2f}")
    print(f"Slope: {term['overall_slope']:.2f}")

    ts_state = monitor.get_term_structure_state()
    print(f"Term Structure State: {ts_state.value.upper()}")

    print("\n--- VVIX (Volatility of VIX) ---")
    vvix = monitor.get_vvix()
    print(f"VVIX: {vvix:.2f}")

    print("\n--- VIX Spike Detection ---")
    spike = monitor.detect_vix_spike()
    print(f"Spike Detected: {spike['is_spike']}")
    print(f"Spike Severity: {spike['severity'].upper()}")
    print(f"Z-Score: {spike['z_score']:.2f}")

    print("\n--- Mean Reversion Analysis ---")
    reversion_prob = monitor.calculate_mean_reversion_probability()
    print(f"Mean Reversion Probability: {reversion_prob*100:.1f}%")

    print("\n" + "="*80)
    print("VIX TRADING SIGNALS")
    print("="*80)

    signals = VIXSignals(monitor)

    print("\n--- Premium Selling Signal ---")
    sell_signal = signals.should_sell_premium()
    print(f"Should Sell Premium: {sell_signal['should_sell_premium']}")
    print(f"Confidence: {sell_signal['confidence']}")
    print(f"Rationale: {sell_signal['rationale']}")
    if sell_signal['recommended_strategies']:
        print("Recommended Strategies:")
        for strat in sell_signal['recommended_strategies']:
            print(f"  - {strat}")

    print("\n--- Premium Buying Signal ---")
    buy_signal = signals.should_buy_premium()
    print(f"Should Buy Premium: {buy_signal['should_buy_premium']}")
    print(f"Confidence: {buy_signal['confidence']}")
    print(f"Rationale: {buy_signal['rationale']}")
    if buy_signal['recommended_strategies']:
        print("Recommended Strategies:")
        for strat in buy_signal['recommended_strategies']:
            print(f"  - {strat}")

    print("\n--- Position Sizing ---")
    position_size = signals.get_position_size_multiplier()
    print(f"Position Size Multiplier: {position_size['multiplier']:.2f}x")
    print(f"Guidance: {position_size['guidance']}")

    print("\n--- Comprehensive Strategy Recommendation ---")
    recommendation = signals.get_strategy_recommendation()
    print(f"Primary Action: {recommendation['primary_action']}")
    print(f"Risk Level: {recommendation['risk_level']}")
    print(f"Position Size Multiplier: {recommendation['position_size_multiplier']:.2f}x")

    print("\nRecommended Strategies:")
    for strat in recommendation['recommended_strategies']:
        print(f"  - [{strat['priority']}] {strat['action']}: {strat['strategy']}")

    print("\nEntry Rules:")
    for rule in recommendation['entry_rules']:
        print(f"  - {rule}")

    print("\nExit Rules:")
    for rule in recommendation['exit_rules']:
        print(f"  - {rule}")

    print("\n" + "="*80)
    print("VIX MONITORING SYSTEM READY")
    print("="*80)
    print("\nExport state for system_state.json:")
    state = monitor.export_state()
    print(json.dumps(state, indent=2))
