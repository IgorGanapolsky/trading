"""
Market Regime Adaptation

Implements regime-specific playbooks for dynamic strategy adjustment.
"""

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime types."""

    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"


class RegimeAdaptation:
    """Adapts strategy based on detected market regime."""

    def __init__(self):
        self.regime_playbooks = {
            MarketRegime.BULL: {
                "position_sizing_multiplier": 1.2,  # Increase sizing in bull markets
                "stop_loss_pct": 3.0,  # Wider stops
                "take_profit_pct": 5.0,  # Higher targets
                "entry_aggressiveness": "high",  # More aggressive entries
                "preferred_strategies": ["momentum", "breakout"],
            },
            MarketRegime.BEAR: {
                "position_sizing_multiplier": 0.5,  # Reduce sizing in bear markets
                "stop_loss_pct": 2.0,  # Tighter stops
                "take_profit_pct": 3.0,  # Lower targets
                "entry_aggressiveness": "low",  # Conservative entries
                "preferred_strategies": ["mean_reversion", "defensive"],
            },
            MarketRegime.SIDEWAYS: {
                "position_sizing_multiplier": 0.8,  # Moderate sizing
                "stop_loss_pct": 2.5,  # Medium stops
                "take_profit_pct": 4.0,  # Medium targets
                "entry_aggressiveness": "medium",
                "preferred_strategies": ["range_trading", "mean_reversion"],
            },
            MarketRegime.HIGH_VOLATILITY: {
                "position_sizing_multiplier": 0.6,  # Reduce sizing in high vol
                "stop_loss_pct": 4.0,  # Wider stops for volatility
                "take_profit_pct": 6.0,  # Higher targets to account for vol
                "entry_aggressiveness": "low",
                "preferred_strategies": ["volatility_breakout"],
            },
            MarketRegime.LOW_VOLATILITY: {
                "position_sizing_multiplier": 1.1,  # Slightly increase in low vol
                "stop_loss_pct": 2.0,  # Tighter stops
                "take_profit_pct": 3.0,  # Lower targets
                "entry_aggressiveness": "medium",
                "preferred_strategies": ["momentum", "trend_following"],
            },
        }

    def get_regime_playbook(self, regime: str) -> dict[str, Any]:
        """
        Get playbook for detected regime.

        Args:
            regime: Market regime string (BULL, BEAR, SIDEWAYS, etc.)

        Returns:
            Regime-specific playbook
        """
        # Normalize regime string
        regime_upper = regime.upper()

        if "BULL" in regime_upper or "RISK_ON" in regime_upper:
            return self.regime_playbooks[MarketRegime.BULL]
        elif "BEAR" in regime_upper or "RISK_OFF" in regime_upper:
            return self.regime_playbooks[MarketRegime.BEAR]
        elif "HIGH_VOL" in regime_upper or "VOLATILE" in regime_upper:
            return self.regime_playbooks[MarketRegime.HIGH_VOLATILITY]
        elif "LOW_VOL" in regime_upper:
            return self.regime_playbooks[MarketRegime.LOW_VOLATILITY]
        else:
            # Default to SIDEWAYS
            return self.regime_playbooks[MarketRegime.SIDEWAYS]

    def adapt_position_size(self, base_size: float, regime: str) -> float:
        """
        Adapt position size based on regime.

        Args:
            base_size: Base position size
            regime: Market regime

        Returns:
            Adapted position size
        """
        playbook = self.get_regime_playbook(regime)
        multiplier = playbook.get("position_sizing_multiplier", 1.0)
        return base_size * multiplier

    def adapt_stop_loss(self, base_stop_pct: float, regime: str) -> float:
        """
        Adapt stop loss based on regime.

        Args:
            base_stop_pct: Base stop loss percentage
            regime: Market regime

        Returns:
            Adapted stop loss percentage
        """
        playbook = self.get_regime_playbook(regime)
        return playbook.get("stop_loss_pct", base_stop_pct)

    def adapt_take_profit(self, base_take_profit_pct: float, regime: str) -> float:
        """
        Adapt take profit based on regime.

        Args:
            base_take_profit_pct: Base take profit percentage
            regime: Market regime

        Returns:
            Adapted take profit percentage
        """
        playbook = self.get_regime_playbook(regime)
        return playbook.get("take_profit_pct", base_take_profit_pct)

    def get_preferred_strategies(self, regime: str) -> list:
        """
        Get preferred strategies for regime.

        Args:
            regime: Market regime

        Returns:
            List of preferred strategy names
        """
        playbook = self.get_regime_playbook(regime)
        return playbook.get("preferred_strategies", [])
