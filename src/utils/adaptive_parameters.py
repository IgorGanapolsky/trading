"""
Adaptive / Volatility-Scaled Parameters

Implements dynamic parameter adjustment based on market conditions. Instead of
static thresholds, this system adapts parameters in real-time based on:
1. Rolling volatility
2. Market regime
3. Recent performance
4. Historical parameter effectiveness

This makes the system adaptive to changing market conditions instead of being
optimized for a single historical regime.

Author: Trading System
Created: 2025-12-02
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ParameterConfig:
    """Configuration for a single adaptive parameter."""

    name: str
    base_value: float
    min_value: float
    max_value: float
    volatility_sensitivity: float = 1.0  # How much to scale with volatility
    regime_adjustments: dict[str, float] = field(default_factory=dict)
    description: str = ""

    def get_value(
        self,
        volatility_multiplier: float = 1.0,
        regime: str = "normal",
    ) -> float:
        """Get adjusted parameter value."""
        value = self.base_value

        # Apply volatility scaling
        if self.volatility_sensitivity != 0:
            value *= 1 + (volatility_multiplier - 1) * self.volatility_sensitivity

        # Apply regime adjustment
        regime_adj = self.regime_adjustments.get(regime, 1.0)
        value *= regime_adj

        # Clamp to bounds
        return max(self.min_value, min(self.max_value, value))


@dataclass
class VolatilityContext:
    """Current volatility context for parameter scaling."""

    current_volatility: float  # Annualized volatility
    historical_volatility: float  # Long-term average volatility
    vix_level: float  # Current VIX
    vix_percentile: float  # VIX percentile (0-100)
    volatility_regime: str  # "low", "normal", "high", "extreme"

    @property
    def volatility_multiplier(self) -> float:
        """Calculate volatility multiplier (1.0 = normal volatility)."""
        if self.historical_volatility > 0:
            return self.current_volatility / self.historical_volatility
        return 1.0


@dataclass
class AdaptedParameters:
    """Result of parameter adaptation."""

    timestamp: str
    volatility_context: VolatilityContext
    market_regime: str
    parameters: dict[str, float]
    adjustments_made: list[str]


class AdaptiveParameterManager:
    """
    Manages adaptive parameters that scale with market conditions.

    This replaces static thresholds with dynamic, volatility-scaled values
    that automatically adjust based on current market conditions.

    Key Parameters Managed:
    - Position sizing multipliers
    - Stop loss distances (ATR-based)
    - Signal thresholds
    - Confidence requirements
    """

    # Default parameter configurations
    DEFAULT_PARAMETERS = {
        "position_size_pct": ParameterConfig(
            name="position_size_pct",
            base_value=0.05,  # 5% base position size
            min_value=0.02,  # 2% minimum
            max_value=0.10,  # 10% maximum
            volatility_sensitivity=-0.5,  # Reduce size when vol is high
            regime_adjustments={
                "bull": 1.1,
                "bear": 0.7,
                "sideways": 0.9,
                "high_volatility": 0.6,
            },
            description="Maximum position size as % of portfolio",
        ),
        "stop_loss_atr_mult": ParameterConfig(
            name="stop_loss_atr_mult",
            base_value=2.0,  # 2 ATR stop loss
            min_value=1.5,
            max_value=4.0,
            volatility_sensitivity=0.3,  # Widen stops in high vol
            regime_adjustments={
                "bull": 1.2,  # Wider stops in uptrend
                "bear": 0.9,  # Tighter stops in downtrend
                "high_volatility": 1.5,  # Much wider in volatile markets
            },
            description="Stop loss distance in ATR multiples",
        ),
        "momentum_threshold": ParameterConfig(
            name="momentum_threshold",
            base_value=0.0,  # Base momentum score threshold
            min_value=-10.0,
            max_value=20.0,
            volatility_sensitivity=-0.2,  # Lower threshold when vol is high (be more selective)
            regime_adjustments={
                "bull": -5.0,  # More permissive in bull market
                "bear": 10.0,  # Much stricter in bear market
            },
            description="Minimum momentum score to generate signal",
        ),
        "rl_confidence_threshold": ParameterConfig(
            name="rl_confidence_threshold",
            base_value=0.6,  # 60% confidence required
            min_value=0.4,
            max_value=0.85,
            volatility_sensitivity=0.2,  # Require higher confidence in high vol
            regime_adjustments={
                "bull": 0.9,  # Slightly lower confidence OK in bull
                "bear": 1.15,  # Require higher confidence in bear
                "high_volatility": 1.2,  # Much higher in volatile markets
            },
            description="Minimum RL confidence to pass gate",
        ),
        "sentiment_weight": ParameterConfig(
            name="sentiment_weight",
            base_value=0.25,  # 25% weight on sentiment
            min_value=0.10,
            max_value=0.40,
            volatility_sensitivity=0.3,  # Weight sentiment more in high vol
            regime_adjustments={
                "bear": 1.3,  # Sentiment matters more in bear market
                "high_volatility": 1.4,  # Pay attention to sentiment in volatile times
            },
            description="Weight given to sentiment in signal blending",
        ),
        "daily_loss_limit_pct": ParameterConfig(
            name="daily_loss_limit_pct",
            base_value=0.02,  # 2% daily loss limit
            min_value=0.01,
            max_value=0.05,
            volatility_sensitivity=-0.3,  # Tighter limits in high vol
            regime_adjustments={
                "bull": 1.2,  # Slightly more tolerance in bull
                "bear": 0.8,  # Tighter in bear
                "high_volatility": 0.6,  # Much tighter in volatile times
            },
            description="Maximum daily loss as % of portfolio",
        ),
        "max_trades_per_day": ParameterConfig(
            name="max_trades_per_day",
            base_value=3.0,
            min_value=1.0,
            max_value=10.0,
            volatility_sensitivity=-0.5,  # Fewer trades in high vol
            regime_adjustments={
                "bear": 0.5,  # Half as many trades in bear market
                "high_volatility": 0.3,  # Very few trades in volatile times
            },
            description="Maximum number of trades per day",
        ),
    }

    # Volatility regime thresholds (based on VIX percentile)
    VOL_REGIME_THRESHOLDS = {
        "low": 20,  # VIX below 20th percentile
        "normal": 60,  # VIX 20-60th percentile
        "high": 85,  # VIX 60-85th percentile
        "extreme": 100,  # VIX above 85th percentile
    }

    def __init__(
        self,
        state_file: str = "data/adaptive_parameters_state.json",
        history_file: str = "data/adaptive_parameters_history.jsonl",
    ):
        self.state_file = Path(state_file)
        self.history_file = Path(history_file)
        self.parameters: dict[str, ParameterConfig] = dict(self.DEFAULT_PARAMETERS)
        self.state = self._load_state()

        # Historical volatility data
        self.historical_vix_mean = float(os.getenv("HISTORICAL_VIX_MEAN", "20.0"))
        self.historical_vix_std = float(os.getenv("HISTORICAL_VIX_STD", "8.0"))
        self.historical_volatility = float(os.getenv("HISTORICAL_VOLATILITY", "0.15"))

        logger.info(
            f"AdaptiveParameterManager initialized with {len(self.parameters)} parameters"
        )

    def get_adapted_parameters(
        self,
        current_volatility: Optional[float] = None,
        vix_level: Optional[float] = None,
        market_regime: Optional[str] = None,
    ) -> AdaptedParameters:
        """
        Get all parameters adapted for current market conditions.

        Args:
            current_volatility: Current annualized volatility (optional)
            vix_level: Current VIX level (optional)
            market_regime: Market regime override (optional)

        Returns:
            AdaptedParameters with all adjusted values
        """
        # Build volatility context
        vol_context = self._build_volatility_context(current_volatility, vix_level)

        # Determine market regime
        if market_regime is None:
            market_regime = self._determine_regime(vol_context)

        # Calculate adapted parameters
        adapted = {}
        adjustments = []

        for name, config in self.parameters.items():
            base_value = config.base_value
            adapted_value = config.get_value(
                volatility_multiplier=vol_context.volatility_multiplier,
                regime=market_regime,
            )

            adapted[name] = adapted_value

            if adapted_value != base_value:
                pct_change = (adapted_value - base_value) / base_value * 100
                adjustments.append(
                    f"{name}: {base_value:.3f} -> {adapted_value:.3f} ({pct_change:+.1f}%)"
                )

        result = AdaptedParameters(
            timestamp=datetime.now().isoformat(),
            volatility_context=vol_context,
            market_regime=market_regime,
            parameters=adapted,
            adjustments_made=adjustments,
        )

        # Log significant adjustments
        if adjustments:
            logger.info(
                f"Parameter adaptation: regime={market_regime}, "
                f"vol_mult={vol_context.volatility_multiplier:.2f}, "
                f"{len(adjustments)} parameters adjusted"
            )

        # Record to history
        self._record_adaptation(result)

        return result

    def get_parameter(
        self,
        name: str,
        current_volatility: Optional[float] = None,
        vix_level: Optional[float] = None,
        market_regime: Optional[str] = None,
    ) -> float:
        """
        Get a single adapted parameter value.

        Args:
            name: Parameter name
            current_volatility: Current annualized volatility (optional)
            vix_level: Current VIX level (optional)
            market_regime: Market regime override (optional)

        Returns:
            Adapted parameter value
        """
        if name not in self.parameters:
            raise ValueError(f"Unknown parameter: {name}")

        vol_context = self._build_volatility_context(current_volatility, vix_level)

        if market_regime is None:
            market_regime = self._determine_regime(vol_context)

        return self.parameters[name].get_value(
            volatility_multiplier=vol_context.volatility_multiplier,
            regime=market_regime,
        )

    def register_parameter(self, config: ParameterConfig) -> None:
        """Register a custom parameter configuration."""
        self.parameters[config.name] = config
        logger.info(f"Registered adaptive parameter: {config.name}")

    def update_base_value(self, name: str, new_base: float) -> None:
        """
        Update the base value of a parameter.

        Use this during re-optimization to update parameter defaults.
        """
        if name not in self.parameters:
            raise ValueError(f"Unknown parameter: {name}")

        old_base = self.parameters[name].base_value
        self.parameters[name].base_value = new_base

        logger.info(f"Updated {name} base value: {old_base:.4f} -> {new_base:.4f}")

        # Record update
        self.state["parameter_updates"] = self.state.get("parameter_updates", [])
        self.state["parameter_updates"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "parameter": name,
                "old_value": old_base,
                "new_value": new_base,
            }
        )
        self._save_state()

    def get_parameter_effectiveness(
        self,
        name: str,
        lookback_days: int = 30,
    ) -> dict[str, Any]:
        """
        Analyze effectiveness of a parameter's adaptations.

        Args:
            name: Parameter name
            lookback_days: Number of days to analyze

        Returns:
            Dict with effectiveness metrics
        """
        history = self._get_parameter_history(name, lookback_days)

        if not history:
            return {"error": "Insufficient history"}

        values = [h["value"] for h in history]
        regimes = [h.get("regime", "unknown") for h in history]

        return {
            "parameter": name,
            "period_days": lookback_days,
            "samples": len(history),
            "mean_value": np.mean(values),
            "std_value": np.std(values),
            "min_value": np.min(values),
            "max_value": np.max(values),
            "regime_distribution": {
                r: regimes.count(r) / len(regimes) for r in set(regimes)
            },
        }

    def _build_volatility_context(
        self,
        current_volatility: Optional[float],
        vix_level: Optional[float],
    ) -> VolatilityContext:
        """Build volatility context from available data."""
        # Fetch VIX if not provided
        if vix_level is None:
            vix_level = self._fetch_vix()

        # Estimate current volatility if not provided
        if current_volatility is None:
            # Use VIX as a proxy (VIX is annualized volatility expectation)
            current_volatility = vix_level / 100 if vix_level else self.historical_volatility

        # Calculate VIX percentile using historical distribution
        vix_percentile = self._calculate_vix_percentile(vix_level or self.historical_vix_mean)

        # Determine volatility regime
        vol_regime = self._classify_vol_regime(vix_percentile)

        return VolatilityContext(
            current_volatility=current_volatility,
            historical_volatility=self.historical_volatility,
            vix_level=vix_level or self.historical_vix_mean,
            vix_percentile=vix_percentile,
            volatility_regime=vol_regime,
        )

    def _determine_regime(self, vol_context: VolatilityContext) -> str:
        """Determine market regime from volatility context."""
        # Priority: volatility regime overrides if extreme
        if vol_context.volatility_regime == "extreme":
            return "high_volatility"
        if vol_context.volatility_regime == "high":
            return "high_volatility"

        # Otherwise, try to detect bull/bear/sideways from market data
        market_trend = self._detect_market_trend()
        if market_trend:
            return market_trend

        # Default based on volatility
        return vol_context.volatility_regime

    def _detect_market_trend(self) -> Optional[str]:
        """Detect current market trend using SPY."""
        try:
            import yfinance as yf

            spy = yf.Ticker("SPY")
            hist = spy.history(period="3mo")

            if hist.empty or len(hist) < 20:
                return None

            # Calculate 20-day and 50-day SMAs
            sma_20 = hist["Close"].tail(20).mean()
            sma_50 = hist["Close"].tail(50).mean() if len(hist) >= 50 else sma_20

            current_price = hist["Close"].iloc[-1]

            # Trend detection
            if current_price > sma_20 > sma_50:
                return "bull"
            elif current_price < sma_20 < sma_50:
                return "bear"
            else:
                return "sideways"

        except Exception as e:
            logger.debug(f"Market trend detection failed: {e}")
            return None

    def _fetch_vix(self) -> Optional[float]:
        """Fetch current VIX level."""
        try:
            import yfinance as yf

            vix = yf.Ticker("^VIX")
            hist = vix.history(period="1d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception as e:
            logger.debug(f"VIX fetch failed: {e}")
        return None

    def _calculate_vix_percentile(self, vix_level: float) -> float:
        """Calculate VIX percentile using historical distribution."""
        from scipy import stats

        # Use normal distribution with historical mean/std
        percentile = stats.norm.cdf(
            vix_level, loc=self.historical_vix_mean, scale=self.historical_vix_std
        )
        return percentile * 100

    def _classify_vol_regime(self, vix_percentile: float) -> str:
        """Classify volatility regime based on VIX percentile."""
        if vix_percentile < self.VOL_REGIME_THRESHOLDS["low"]:
            return "low"
        elif vix_percentile < self.VOL_REGIME_THRESHOLDS["normal"]:
            return "normal"
        elif vix_percentile < self.VOL_REGIME_THRESHOLDS["high"]:
            return "high"
        else:
            return "extreme"

    def _get_parameter_history(
        self, name: str, lookback_days: int
    ) -> list[dict[str, Any]]:
        """Get parameter history from file."""
        history = []
        cutoff = datetime.now() - timedelta(days=lookback_days)

        try:
            if self.history_file.exists():
                with open(self.history_file) as f:
                    for line in f:
                        try:
                            record = json.loads(line)
                            if datetime.fromisoformat(record["timestamp"]) >= cutoff:
                                if name in record.get("parameters", {}):
                                    history.append(
                                        {
                                            "timestamp": record["timestamp"],
                                            "value": record["parameters"][name],
                                            "regime": record.get("market_regime"),
                                        }
                                    )
                        except (json.JSONDecodeError, KeyError):
                            continue
        except Exception as e:
            logger.error(f"Error reading parameter history: {e}")

        return history

    def _record_adaptation(self, result: AdaptedParameters) -> None:
        """Record adaptation to history file."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "a") as f:
                f.write(
                    json.dumps(
                        {
                            "timestamp": result.timestamp,
                            "market_regime": result.market_regime,
                            "vol_multiplier": result.volatility_context.volatility_multiplier,
                            "vix_level": result.volatility_context.vix_level,
                            "parameters": result.parameters,
                        }
                    )
                    + "\n"
                )
        except Exception as e:
            logger.error(f"Error recording adaptation: {e}")

    def _load_state(self) -> dict:
        """Load state from disk."""
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading adaptive parameter state: {e}")
            return {}

    def _save_state(self) -> None:
        """Save state to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving adaptive parameter state: {e}")


# Global instance
_GLOBAL_PARAM_MANAGER: Optional[AdaptiveParameterManager] = None


def get_adaptive_parameter_manager() -> AdaptiveParameterManager:
    """Get or create global adaptive parameter manager."""
    global _GLOBAL_PARAM_MANAGER
    if _GLOBAL_PARAM_MANAGER is None:
        _GLOBAL_PARAM_MANAGER = AdaptiveParameterManager()
    return _GLOBAL_PARAM_MANAGER


def get_adapted_value(
    name: str,
    current_volatility: Optional[float] = None,
    vix_level: Optional[float] = None,
    market_regime: Optional[str] = None,
) -> float:
    """Convenience function to get a single adapted parameter."""
    manager = get_adaptive_parameter_manager()
    return manager.get_parameter(name, current_volatility, vix_level, market_regime)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("=" * 80)
    print("ADAPTIVE PARAMETER MANAGER DEMO")
    print("=" * 80)

    manager = AdaptiveParameterManager()

    # Test different market conditions
    scenarios = [
        ("Normal market", 0.15, 18.0, None),
        ("Bull market, low vol", 0.10, 12.0, "bull"),
        ("Bear market", 0.20, 25.0, "bear"),
        ("High volatility", 0.30, 35.0, None),
        ("Extreme volatility", 0.45, 50.0, None),
    ]

    for name, vol, vix, regime in scenarios:
        print(f"\n--- {name} ---")
        print(f"Volatility: {vol:.0%}, VIX: {vix}")

        result = manager.get_adapted_parameters(
            current_volatility=vol, vix_level=vix, market_regime=regime
        )

        print(f"Detected regime: {result.market_regime}")
        print(f"Vol multiplier: {result.volatility_context.volatility_multiplier:.2f}")
        print("Key parameters:")
        for param in ["position_size_pct", "rl_confidence_threshold", "stop_loss_atr_mult"]:
            value = result.parameters[param]
            base = manager.parameters[param].base_value
            pct = (value - base) / base * 100
            print(f"  {param}: {value:.3f} (base: {base:.3f}, {pct:+.1f}%)")

    print("\n" + "=" * 80)
