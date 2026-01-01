"""
Binary Reward Shaper for Trading RLHF.

Converts binary signals (thumbs up/down, profit/loss) into shaped rewards.

Research basis:
- Binary PnL sign outperforms continuous rewards for <1000 samples
- Risk-adjusted composite rewards reduce variance
- HICRA strategic decision weighting improves learning
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class BinaryRewardShaper:
    """
    Converts binary feedback into shaped rewards for RL training.

    Handles:
    1. Trade outcomes (profit/loss)
    2. User feedback (thumbs up/down)
    3. Pattern recognition (TradeMemory lookups)
    """

    def __init__(
        self,
        base_reward: float = 1.0,
        risk_penalty_weight: float = 0.3,
        feedback_weight: float = 2.0,  # User feedback is 2x trade outcome
        pattern_bonus: float = 0.5,
    ):
        """
        Args:
            base_reward: Base reward magnitude for binary outcomes
            risk_penalty_weight: Weight for risk-adjusted penalties
            feedback_weight: Multiplier for human feedback (thumbs > trades)
            pattern_bonus: Bonus for repeating winning patterns
        """
        self.base_reward = base_reward
        self.risk_penalty_weight = risk_penalty_weight
        self.feedback_weight = feedback_weight
        self.pattern_bonus = pattern_bonus

    def shape_trade_outcome(
        self,
        pnl: float,
        holding_period_days: int = 1,
        max_drawdown: float = 0.0,
        volatility: float = 0.02,
        pattern_history: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Shape reward from trade outcome with risk adjustments.

        Args:
            pnl: Profit/loss in dollars
            holding_period_days: Days trade was held
            max_drawdown: Maximum drawdown during trade
            volatility: Market volatility (ATR%)
            pattern_history: From TradeMemory.query_similar()

        Returns:
            Dict with shaped_reward, components, and explanation
        """
        # Binary base reward (research shows this beats continuous for small datasets)
        binary_reward = self.base_reward if pnl > 0 else -self.base_reward

        # Risk adjustment (penalize large drawdowns)
        risk_penalty = 0.0
        if max_drawdown > 0.05:  # >5% drawdown
            risk_penalty = -self.risk_penalty_weight * (max_drawdown - 0.05) * 10

        # Holding period bonus (prefer quick wins)
        holding_bonus = 0.0
        if pnl > 0 and holding_period_days <= 3:
            holding_bonus = 0.2  # Quick win bonus
        elif holding_period_days > 10:
            holding_bonus = -0.1  # Penalize slow capital deployment

        # Volatility adjustment (reduce reward in high volatility)
        vol_adjustment = 0.0
        if volatility > 0.04:  # High volatility
            vol_adjustment = -0.2

        # Pattern bonus (repeat winners)
        pattern_adjustment = 0.0
        if pattern_history and pattern_history.get("found"):
            win_rate = pattern_history.get("win_rate", 0.5)
            if win_rate >= 0.7:
                pattern_adjustment = self.pattern_bonus  # Strong pattern
            elif win_rate <= 0.3:
                pattern_adjustment = -self.pattern_bonus  # Avoid bad patterns

        # Final shaped reward
        shaped_reward = (
            binary_reward
            + risk_penalty
            + holding_bonus
            + vol_adjustment
            + pattern_adjustment
        )

        logger.debug(
            "Reward shaping: binary=%.2f, risk=%.2f, holding=%.2f, vol=%.2f, "
            "pattern=%.2f → final=%.2f",
            binary_reward,
            risk_penalty,
            holding_bonus,
            vol_adjustment,
            pattern_adjustment,
            shaped_reward,
        )

        return {
            "shaped_reward": shaped_reward,
            "binary_reward": binary_reward,
            "risk_penalty": risk_penalty,
            "holding_bonus": holding_bonus,
            "vol_adjustment": vol_adjustment,
            "pattern_adjustment": pattern_adjustment,
            "explanation": self._explain(
                binary_reward, risk_penalty, holding_bonus, vol_adjustment, pattern_adjustment
            ),
        }

    def shape_user_feedback(
        self,
        thumbs_up: bool,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Shape reward from user feedback (thumbs up/down).

        User feedback is weighted HIGHER than trade outcomes because:
        1. It captures strategy quality, not just luck
        2. It reflects process, not just results

        Args:
            thumbs_up: True for thumbs up, False for thumbs down
            context: Optional context (e.g., what action received feedback)

        Returns:
            Dict with shaped_reward and explanation
        """
        # User feedback is 2x trade outcome weight
        base = self.base_reward * self.feedback_weight
        binary_feedback = base if thumbs_up else -base

        # Context adjustment (if we know what decision was rated)
        context_bonus = 0.0
        if context:
            decision_type = context.get("decision_type", "")
            # Strategic decisions weighted higher (from HICRA research)
            if decision_type in ["risk_exceeded", "regime_change", "exit_all"]:
                context_bonus = 0.5  # Strategic feedback worth more
            elif decision_type in ["entry_signal", "position_sizing"]:
                context_bonus = 0.3  # Tactical feedback

        shaped_reward = binary_feedback + context_bonus

        logger.info(
            "User feedback reward: %s → base=%.2f, context=%.2f, final=%.2f",
            "👍" if thumbs_up else "👎",
            binary_feedback,
            context_bonus,
            shaped_reward,
        )

        return {
            "shaped_reward": shaped_reward,
            "binary_feedback": binary_feedback,
            "context_bonus": context_bonus,
            "explanation": (
                f"{'Positive' if thumbs_up else 'Negative'} feedback "
                f"(weight={self.feedback_weight}x trade outcomes)"
            ),
        }

    def _explain(
        self,
        binary: float,
        risk: float,
        holding: float,
        vol: float,
        pattern: float,
    ) -> str:
        """Generate human-readable explanation."""
        parts = []
        if binary > 0:
            parts.append("Profitable trade")
        else:
            parts.append("Losing trade")

        if risk < 0:
            parts.append(f"High drawdown penalty ({risk:.2f})")
        if holding > 0:
            parts.append("Quick win bonus")
        elif holding < 0:
            parts.append("Slow trade penalty")
        if vol < 0:
            parts.append("High volatility penalty")
        if pattern > 0:
            parts.append("Winning pattern bonus")
        elif pattern < 0:
            parts.append("Losing pattern penalty")

        return " | ".join(parts)
