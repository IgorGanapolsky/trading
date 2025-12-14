"""
Hooks for integrating Procedural Memory with Trading Orchestrator.

Provides automatic skill learning and retrieval during trading.

Usage:
    from src.memory.skill_hooks import enable_skill_learning

    # Enable automatic skill learning
    enable_skill_learning(orchestrator)

    # Or manually integrate
    from src.memory import get_skill_library, ProceduralMemory

    memory = ProceduralMemory()

    # Before trade
    suggestion = memory.suggest_action(market_context)
    if suggestion:
        skill, action, confidence = suggestion
        # Use skill's recommended action

    # After trade
    memory.learn_from_trade(trade_record)
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Dict, Optional, TypeVar

from src.memory.procedural_memory import (
    ProceduralMemory,
    SkillLibrary,
    SkillType,
    TradingSkill,
    get_skill_library,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class SkillLearningHook:
    """
    Hook for automatic skill learning from trades.

    Observes trades and extracts skills from successful ones.
    """

    def __init__(
        self,
        memory: Optional[ProceduralMemory] = None,
        min_profit_pct: float = 0.5,
        auto_suggest: bool = True,
    ):
        self.memory = memory or ProceduralMemory()
        self.min_profit_pct = min_profit_pct
        self.auto_suggest = auto_suggest

        # Track active trades
        self._trade_contexts: Dict[str, Dict[str, Any]] = {}

    def on_trade_enter(
        self,
        trade_id: str,
        symbol: str,
        action: str,
        context: Dict[str, Any],
    ):
        """Called when entering a trade. Records context for later learning."""
        self._trade_contexts[trade_id] = {
            "trade_id": trade_id,
            "symbol": symbol,
            "action": action,
            "entry_time": context.get("timestamp"),
            **context,
        }

        # Check if a skill was used
        if "skill_id" in context:
            self.memory.record_skill_use(context["skill_id"], trade_id)

        logger.debug(f"Recorded trade entry context for {trade_id}")

    def on_trade_exit(
        self,
        trade_id: str,
        profit_pct: float,
        exit_context: Dict[str, Any],
    ):
        """Called when exiting a trade. Learns skill if profitable."""
        entry_context = self._trade_contexts.pop(trade_id, None)
        if entry_context is None:
            logger.warning(f"No entry context found for trade {trade_id}")
            return

        # Merge contexts
        trade_record = {
            **entry_context,
            "profit_pct": profit_pct,
            "exit_time": exit_context.get("timestamp"),
            "duration_minutes": exit_context.get("duration_minutes", 60),
        }

        # Record outcome for any skill that was used
        self.memory.record_trade_outcome(
            trade_id,
            profit_pct,
            trade_record.get("duration_minutes", 60),
        )

        # Learn new skill if profitable
        if profit_pct >= self.min_profit_pct:
            skill = self.memory.learn_from_trade(trade_record)
            if skill:
                logger.info(
                    f"Learned skill '{skill.name}' from trade {trade_id} "
                    f"(profit: {profit_pct:+.1f}%)"
                )

    def suggest_for_context(
        self,
        context: Dict[str, Any],
        skill_type: Optional[SkillType] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get skill suggestion for the current context.

        Returns suggestion dict with skill details if found.
        """
        if not self.auto_suggest:
            return None

        suggestion = self.memory.suggest_action(context, skill_type)
        if suggestion is None:
            return None

        skill, action, confidence = suggestion

        return {
            "skill_id": skill.skill_id,
            "skill_name": skill.name,
            "action_type": action.action_type,
            "size_method": action.size_method,
            "size_value": action.size_value,
            "stop_loss_pct": action.stop_loss_pct,
            "take_profit_pct": action.take_profit_pct,
            "confidence": confidence,
            "expected_win_rate": skill.outcome.expected_win_rate,
            "expected_profit_pct": skill.outcome.expected_profit_pct,
            "historical_uses": skill.outcome.uses,
        }


def enable_skill_learning(
    orchestrator: Any,
    min_profit_pct: float = 0.5,
    auto_suggest: bool = True,
) -> SkillLearningHook:
    """
    Enable automatic skill learning for an orchestrator.

    Wraps key methods to automatically:
    - Record trade context on entry
    - Learn skills from profitable exits
    - Suggest skills for new trades

    Returns the hook instance for manual interaction.
    """
    hook = SkillLearningHook(
        min_profit_pct=min_profit_pct,
        auto_suggest=auto_suggest,
    )

    # Store hook reference
    orchestrator._skill_hook = hook

    # Add method to get skill suggestions
    def get_skill_suggestion(context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return hook.suggest_for_context(context)

    orchestrator.get_skill_suggestion = get_skill_suggestion

    logger.info(
        f"Skill learning enabled: min_profit={min_profit_pct}%, "
        f"auto_suggest={auto_suggest}"
    )

    return hook


def create_initial_skills() -> SkillLibrary:
    """
    Create initial skill library with common trading patterns.

    These are "seed" skills based on established trading wisdom.
    They will be refined through actual trading.
    """
    from src.memory.procedural_memory import (
        MarketRegime,
        SkillAction,
        SkillConditions,
        SkillOutcome,
        SkillType,
        TradingSkill,
    )

    library = get_skill_library()

    # Seed skills if library is empty
    if len(library.skills) == 0:
        seed_skills = [
            # RSI Oversold Buy
            TradingSkill(
                name="RSI Oversold Bounce",
                description="Buy when RSI drops below 30 in uptrend",
                skill_type=SkillType.ENTRY,
                conditions=SkillConditions(
                    rsi_range=(0, 35),
                    trend="up",
                    volume_condition="normal",
                ),
                action=SkillAction(
                    action_type="buy",
                    size_method="volatility_adjusted",
                    size_value=1.0,
                    stop_loss_pct=-3.0,
                    take_profit_pct=5.0,
                ),
                outcome=SkillOutcome(
                    expected_win_rate=0.55,
                    expected_profit_pct=2.0,
                    confidence=0.4,
                ),
                tags=["mean_reversion", "oversold"],
            ),
            # RSI Overbought Fade
            TradingSkill(
                name="RSI Overbought Fade",
                description="Sell when RSI exceeds 70 in ranging market",
                skill_type=SkillType.EXIT,
                conditions=SkillConditions(
                    rsi_range=(70, 100),
                    regime=MarketRegime.RANGING,
                ),
                action=SkillAction(
                    action_type="sell",
                    size_method="fixed",
                    size_value=1.0,
                ),
                outcome=SkillOutcome(
                    expected_win_rate=0.52,
                    expected_profit_pct=1.5,
                    confidence=0.4,
                ),
                tags=["mean_reversion", "overbought"],
            ),
            # Momentum Breakout
            TradingSkill(
                name="Volume Breakout Entry",
                description="Buy on high volume breakout in uptrend",
                skill_type=SkillType.ENTRY,
                conditions=SkillConditions(
                    trend="up",
                    volume_condition="high",
                    macd_signal="bullish",
                ),
                action=SkillAction(
                    action_type="buy",
                    size_method="volatility_adjusted",
                    size_value=1.2,
                    stop_loss_pct=-2.5,
                    take_profit_pct=4.0,
                    trailing_stop_pct=1.5,
                ),
                outcome=SkillOutcome(
                    expected_win_rate=0.58,
                    expected_profit_pct=2.5,
                    confidence=0.45,
                ),
                tags=["momentum", "breakout"],
            ),
            # Trend Following Hold
            TradingSkill(
                name="Trend Following Hold",
                description="Hold position in strong uptrend",
                skill_type=SkillType.EXIT,
                conditions=SkillConditions(
                    trend="up",
                    regime=MarketRegime.TRENDING_UP,
                    rsi_range=(40, 70),
                ),
                action=SkillAction(
                    action_type="hold",
                    trailing_stop_pct=2.0,
                ),
                outcome=SkillOutcome(
                    expected_win_rate=0.60,
                    expected_profit_pct=3.0,
                    confidence=0.5,
                ),
                tags=["trend_following", "hold"],
            ),
            # Volatile Market Sizing
            TradingSkill(
                name="Volatile Market Small Size",
                description="Reduce position size in volatile conditions",
                skill_type=SkillType.SIZING,
                conditions=SkillConditions(
                    regime=MarketRegime.VOLATILE,
                    volatility_percentile=(80, 100),
                ),
                action=SkillAction(
                    action_type="buy",
                    size_method="volatility_adjusted",
                    size_value=0.5,  # Half size
                    stop_loss_pct=-5.0,  # Wider stop
                ),
                outcome=SkillOutcome(
                    expected_win_rate=0.50,
                    expected_profit_pct=1.0,
                    confidence=0.55,
                ),
                tags=["risk_management", "sizing"],
            ),
        ]

        for skill in seed_skills:
            library.add_skill(skill)

        logger.info(f"Created {len(seed_skills)} seed skills")

    return library
