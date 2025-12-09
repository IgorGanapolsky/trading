"""Mental Toughness Coach.

The main coaching interface for the trading system. Implements Steve Siebold's
"177 Mental Toughness Secrets of the World Class" principles to provide
real-time psychological coaching during trading.

This coach acts like a world-class trading psychologist, monitoring the
system's emotional state and intervening when needed to maintain peak
mental performance.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .interventions import (
    CoachingIntervention,
    InterventionType,
    SieboldPrinciple,
    get_circuit_breaker,
    get_intervention_for_bias,
    get_purpose_reminder,
    get_random_emotional_reset,
    get_random_long_term_perspective,
    get_random_pre_trade,
    get_random_session_start,
    get_random_system_two,
    get_random_win_grounding,
    get_session_review,
)
from .psychology_state import (
    EmotionalZone,
    PsychologyState,
    PsychologyStateManager,
)

logger = logging.getLogger(__name__)


@dataclass
class CoachingSession:
    """Record of a coaching session."""

    started_at: datetime
    interventions: list[CoachingIntervention] = field(default_factory=list)
    trades_coached: int = 0
    biases_detected: int = 0
    circuit_breakers_triggered: int = 0


class MentalToughnessCoach:
    """World-class mental toughness coach for trading.

    Based on Steve Siebold's "177 Mental Toughness Secrets of the World Class",
    this coach monitors psychological state and provides timely interventions
    to maintain peak trading performance.

    Key coaching areas:
    - Emotional compartmentalization (don't let losses bleed)
    - Metacognition (think about your thinking)
    - Operating from abundance (not fear/scarcity)
    - Failure reframing (losses are data, not defeat)
    - Confidence calibration (avoid over/under-confidence)
    - Purpose alignment (North Star focus)

    Usage:
        coach = MentalToughnessCoach()

        # At session start
        intervention = coach.start_session()

        # Before each trade
        intervention = coach.pre_trade_check()

        # After each trade
        interventions = coach.process_trade_result(is_win=True, pnl=15.50)

        # Check readiness anytime
        ready, intervention = coach.is_ready_to_trade()

        # At session end
        intervention = coach.end_session()
    """

    # Thresholds for interventions
    MAX_CONSECUTIVE_LOSSES_BEFORE_RESET = 2
    MAX_CONSECUTIVE_LOSSES_BEFORE_CIRCUIT_BREAKER = 4
    MIN_MENTAL_ENERGY_TO_TRADE = 0.3
    MIN_READINESS_SCORE_TO_TRADE = 50.0
    OVERCONFIDENCE_WIN_STREAK = 4

    def __init__(
        self,
        state_manager: PsychologyStateManager | None = None,
        log_path: str | Path | None = None,
    ) -> None:
        """Initialize the coach.

        Args:
            state_manager: Optional custom state manager
            log_path: Optional path for coaching log
        """
        self.state_manager = state_manager or PsychologyStateManager()
        self.log_path = Path(log_path) if log_path else Path("data/audit_trail/coaching_log.jsonl")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        self._session: CoachingSession | None = None
        self._intervention_cooldown: dict[InterventionType, datetime] = {}

        # Cooldown periods (prevent intervention spam)
        self._cooldown_minutes = {
            InterventionType.PRE_TRADE_PREP: 5,
            InterventionType.EMOTIONAL_RESET: 10,
            InterventionType.BIAS_CORRECTION: 15,
            InterventionType.CIRCUIT_BREAKER: 60,
            InterventionType.WIN_GROUNDING: 10,
            InterventionType.PURPOSE_REMINDER: 30,
        }

    @property
    def state(self) -> PsychologyState:
        """Get current psychology state."""
        return self.state_manager.get_state()

    def start_session(self) -> CoachingIntervention:
        """Start a new coaching session.

        Called at the beginning of a trading day. Resets psychological
        state and provides opening motivation/framework.

        Returns:
            Session start intervention
        """
        # Reset state for new day
        self.state.reset_for_new_session()
        self.state_manager.save_state()

        # Start coaching session
        self._session = CoachingSession(started_at=datetime.now(timezone.utc))

        # Get session start intervention
        intervention = get_random_session_start()
        self._record_intervention(intervention)

        logger.info(
            "Mental Toughness Coach: Session started. Zone: %s, Readiness: %.1f%%",
            self.state.current_zone.value,
            self.state.get_readiness_score(),
        )

        return intervention

    def pre_trade_check(self, ticker: str = "") -> CoachingIntervention | None:
        """Perform pre-trade mental check.

        Called before entering a trade. Ensures mental readiness and
        provides setup validation coaching.

        Args:
            ticker: Optional ticker symbol for context

        Returns:
            Intervention if coaching needed, None if clear to trade
        """
        # Check cooldown
        if self._is_on_cooldown(InterventionType.PRE_TRADE_PREP):
            return None

        readiness = self.state.get_readiness_score()

        # If readiness is low, provide coaching
        if readiness < 70:
            intervention = get_random_pre_trade()
            intervention.context["ticker"] = ticker
            intervention.context["readiness_score"] = readiness
            self._record_intervention(intervention)
            self._set_cooldown(InterventionType.PRE_TRADE_PREP)
            return intervention

        return None

    def process_trade_result(
        self,
        is_win: bool,
        pnl: float,
        ticker: str = "",
        trade_reason: str = "",
    ) -> list[CoachingIntervention]:
        """Process a trade result and provide coaching.

        Called after each trade completes. Updates psychological state
        and provides appropriate interventions.

        Args:
            is_win: Whether the trade was profitable
            pnl: Profit/loss amount
            ticker: Ticker symbol
            trade_reason: Reason for the trade

        Returns:
            List of coaching interventions (may be empty)
        """
        interventions: list[CoachingIntervention] = []

        # Update state and detect biases
        new_biases = self.state.update_after_trade(
            is_win=is_win,
            pnl=pnl,
            trade_reason=trade_reason,
        )

        # Track in session
        if self._session:
            self._session.trades_coached += 1
            self._session.biases_detected += len(new_biases)

        # Handle wins
        if is_win:
            # Check for overconfidence after winning streak
            if self.state.consecutive_wins >= self.OVERCONFIDENCE_WIN_STREAK:
                intervention = get_random_win_grounding()
                intervention.context.update(
                    {
                        "ticker": ticker,
                        "pnl": pnl,
                        "consecutive_wins": self.state.consecutive_wins,
                    }
                )
                interventions.append(intervention)

        # Handle losses
        else:
            # Emotional reset after losses
            if self.state.consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES_BEFORE_RESET:
                if not self._is_on_cooldown(InterventionType.EMOTIONAL_RESET):
                    intervention = get_random_emotional_reset()
                    intervention.context.update(
                        {
                            "ticker": ticker,
                            "pnl": pnl,
                            "consecutive_losses": self.state.consecutive_losses,
                        }
                    )
                    interventions.append(intervention)
                    self._set_cooldown(InterventionType.EMOTIONAL_RESET)

            # Circuit breaker for severe losing streak
            if self.state.consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES_BEFORE_CIRCUIT_BREAKER:
                intervention = get_circuit_breaker()
                intervention.context.update(
                    {
                        "consecutive_losses": self.state.consecutive_losses,
                        "drawdown_today": self.state.max_drawdown_today,
                    }
                )
                interventions.append(intervention)
                if self._session:
                    self._session.circuit_breakers_triggered += 1

        # Process newly detected biases
        for bias in new_biases:
            bias_intervention = get_intervention_for_bias(bias.bias_type.value)
            if bias_intervention:
                bias_intervention.context.update(
                    {
                        "bias_severity": bias.severity,
                        "trigger": bias.trigger,
                    }
                )
                interventions.append(bias_intervention)

        # Apply coaching effect
        if interventions:
            self.state.apply_coaching(interventions[0].intervention_type.value)

        # Save state
        self.state_manager.save_state()

        # Record all interventions
        for intervention in interventions:
            self._record_intervention(intervention)

        return interventions

    def is_ready_to_trade(self) -> tuple[bool, CoachingIntervention | None]:
        """Check if psychologically ready to trade.

        Returns:
            Tuple of (is_ready, intervention_if_not_ready)
        """
        readiness = self.state.get_readiness_score()
        zone = self.state.current_zone

        # Hard stops
        if zone == EmotionalZone.TILT:
            return False, get_circuit_breaker()

        if zone == EmotionalZone.DANGER:
            intervention = get_random_emotional_reset()
            intervention.severity = "critical"
            return False, intervention

        if self.state.mental_energy < self.MIN_MENTAL_ENERGY_TO_TRADE:
            intervention = get_purpose_reminder()
            intervention.message = (
                "Mental energy is depleted. Champions seek balance (Siebold #16). "
                "Taking a break now is the highest-EV decision. "
                "Your edge comes from fresh, focused execution."
            )
            intervention.severity = "warning"
            return False, intervention

        if readiness < self.MIN_READINESS_SCORE_TO_TRADE:
            intervention = get_random_emotional_reset()
            intervention.context["readiness_score"] = readiness
            return False, intervention

        # Caution but can trade
        if zone == EmotionalZone.CAUTION:
            intervention = get_random_pre_trade()
            intervention.severity = "warning"
            return True, intervention

        # Clear to trade
        return True, None

    def request_coaching(self, situation: str) -> CoachingIntervention:
        """Request coaching for a specific situation.

        Use this when the system needs guidance on a specific scenario.

        Args:
            situation: Description of the situation

        Returns:
            Appropriate coaching intervention
        """
        situation_lower = situation.lower()

        if any(word in situation_lower for word in ["loss", "losing", "lost", "down"]):
            return get_random_emotional_reset()

        if any(word in situation_lower for word in ["win", "winning", "profit", "up"]):
            return get_random_win_grounding()

        if any(word in situation_lower for word in ["scared", "fear", "worried", "anxious"]):
            intervention = get_purpose_reminder()
            intervention.message = (
                "Fear is natural but champions operate from abundance (Siebold #8). "
                "You have a system. You have rules. Trust the process. "
                "Fear-based trading leads to missed opportunities and poor execution."
            )
            return intervention

        if any(word in situation_lower for word in ["unsure", "confused", "uncertain"]):
            return get_random_pre_trade()

        # Default to metacognition prompt
        return CoachingIntervention(
            intervention_type=InterventionType.METACOGNITION,
            principles=[SieboldPrinciple.EMBRACE_METACOGNITION],
            headline="Metacognition Check",
            message=(
                f"You're experiencing: '{situation}'. Champions embrace metacognition "
                "(Siebold #5). Step back and observe your thought process. "
                "Are you thinking clearly or reactively? What would a world-class "
                "trader do in this situation?"
            ),
            action_items=[
                "Name the emotion you're feeling",
                "Ask: Is this thought helpful or harmful?",
                "Decide: Act from logic, not emotion",
            ],
        )

    def end_session(self) -> CoachingIntervention:
        """End the coaching session with review.

        Called at the end of a trading day. Provides session review
        and prepares for next day.

        Returns:
            Session review intervention
        """
        intervention = get_session_review()

        # Add session stats to context
        if self._session:
            intervention.context.update(
                {
                    "trades_coached": self._session.trades_coached,
                    "biases_detected": self._session.biases_detected,
                    "circuit_breakers": self._session.circuit_breakers_triggered,
                    "final_zone": self.state.current_zone.value,
                    "final_readiness": self.state.get_readiness_score(),
                }
            )

        self._record_intervention(intervention)

        # Log session summary
        logger.info(
            "Mental Toughness Coach: Session ended. Trades: %d, Biases: %d, "
            "Circuit Breakers: %d, Final Readiness: %.1f%%",
            self._session.trades_coached if self._session else 0,
            self._session.biases_detected if self._session else 0,
            self._session.circuit_breakers_triggered if self._session else 0,
            self.state.get_readiness_score(),
        )

        return intervention

    def get_daily_affirmation(self) -> str:
        """Get a daily affirmation based on Siebold's principles.

        Returns:
            Motivational affirmation for the day
        """
        affirmations = [
            # Supreme Self Confidence (#4)
            "I trust my system completely. Each trade is executed with confidence, "
            "regardless of recent results. I am a world-class trader in development.",
            # Operate from Abundance (#8)
            "There are unlimited opportunities in the market. I don't chase or force. "
            "I wait for my setups with patience and strike with precision.",
            # Know Why Fighting (#7)
            "I am building something bigger than today's P/L. My North Star is clear: "
            "$100+/day through compound engineering. Every trade moves me closer.",
            # School Never Out (#10)
            "Every trade, win or loss, teaches me something. I am a perpetual student "
            "of the market. Today I will learn something that makes tomorrow easier.",
            # Not Afraid to Suffer (#18)
            "Losses are the cost of doing business. I accept them without emotional "
            "attachment. Pain is temporary; the lessons are permanent.",
            # Compartmentalize Emotions (#2)
            "Each trade is independent. Yesterday's results don't affect today's "
            "opportunities. I execute with fresh eyes and a clear mind.",
            # Embrace Metacognition (#5)
            "I think about my thinking. Before each decision, I ask: Am I trading "
            "my system or my emotions? Clarity precedes action.",
            # Zealots for Change (#12)
            "I embrace evolution. My system improves daily through compound engineering. "
            "What worked yesterday may need adjustment today. I adapt and thrive.",
            # FIRE: Compound Thinking
            "FIRE: Compound growth is my superpower. Small gains today become massive "
            "wealth tomorrow. I'm not trading for today - I'm building for decades.",
            # FIRE: Delayed Gratification
            "FIRE: I delay gratification like the wealthy do. This R&D phase is "
            "front-loading the work. By Month 6, the system trades FOR me.",
            # FIRE: Systems > Goals
            "FIRE: Goals are for amateurs. Systems are for professionals. I don't have "
            "a profit goal - I have a wealth-building SYSTEM that compounds daily.",
            # FIRE: Abundance
            "FIRE: The market offers unlimited opportunities. I operate from abundance, "
            "not scarcity. Missing one trade means nothing. There's always tomorrow.",
            # Kahneman: System 2 Thinking
            "KAHNEMAN: I engage System 2 before every trade. Slow, deliberate, logical. "
            "System 1 is for catching balls, not for trading. I pause. I breathe. I verify.",
            # Kahneman: Loss Aversion
            "KAHNEMAN: My brain lies about losses - they FEEL 2x worse than they are. "
            "I trust my system, not my feelings. The rational move often feels wrong.",
            # Kahneman: WYSIATI
            "KAHNEMAN: What I See Is NOT All There Is. My analysis is incomplete. "
            "Overconfidence comes from coherent stories, not complete information. Stay humble.",
            # Kahneman: Regression to Mean
            "KAHNEMAN: Streaks end. Hot cools off. Cold warms up. I don't chase wins "
            "or despair over losses. The mean is coming. I stay consistent.",
        ]

        import random

        return random.choice(affirmations)

    def get_long_term_perspective(self) -> CoachingIntervention:
        """Get a FIRE-inspired long-term perspective intervention.

        Based on Financial Independence, Retire Early principles to help
        maintain focus on long-term wealth building over daily P/L.

        Returns:
            Long-term perspective coaching intervention
        """
        intervention = get_random_long_term_perspective()
        self._record_intervention(intervention)
        return intervention

    def activate_system_two(self) -> CoachingIntervention:
        """Activate System 2 thinking with Kahneman-inspired coaching.

        Based on Daniel Kahneman's "Thinking, Fast and Slow" (Nobel Prize).
        System 1 = fast, intuitive, emotional (causes trading errors)
        System 2 = slow, deliberate, logical (what we need for trading)

        Use this when you feel rushed, emotional, or uncertain about a trade.

        Returns:
            System 2 activation coaching intervention
        """
        intervention = get_random_system_two()
        self._record_intervention(intervention)

        # Reduce mental energy slightly (System 2 is effortful)
        self.state.mental_energy = max(0.0, self.state.mental_energy - 0.05)
        self.state_manager.save_state()

        return intervention

    def get_state_summary(self) -> dict[str, Any]:
        """Get a summary of current psychological state.

        Returns:
            Dictionary with state summary
        """
        state = self.state
        return {
            "zone": state.current_zone.value,
            "confidence": state.confidence_level.value,
            "mental_energy": f"{state.mental_energy * 100:.0f}%",
            "readiness_score": f"{state.get_readiness_score():.1f}/100",
            "consecutive_wins": state.consecutive_wins,
            "consecutive_losses": state.consecutive_losses,
            "trades_today": state.trades_today,
            "active_biases": [b.bias_type.value for b in state.active_biases],
            "siebold_scores": {
                "emotional_compartmentalization": state.emotional_compartmentalization,
                "metacognition": state.metacognition_level,
                "abundance_mindset": state.abundance_mindset,
                "coachability": state.coachability,
                "purpose_clarity": state.purpose_clarity,
            },
        }

    def get_prompt_context(self) -> str:
        """Get psychology context formatted for injection into LLM prompts.

        This is the KEY METHOD that bridges psychology to LLM decision-making.
        Returns text that should be appended to LLM system prompts to help
        the model make bias-aware, psychologically-informed decisions.

        Based on research showing:
        - LLMs exhibit cognitive biases (recency, loss aversion, overconfidence)
        - Self-reflection and bias mitigation prompts improve decisions
        - Constitutional AI-style self-critique reduces errors

        Returns:
            Formatted string for LLM prompt injection
        """
        state = self.state
        zone = state.current_zone.value
        readiness = state.get_readiness_score()
        energy = state.mental_energy * 100
        active_biases = [b.bias_type.value for b in state.active_biases]
        consecutive_losses = state.consecutive_losses
        consecutive_wins = state.consecutive_wins

        # Build bias-specific warnings
        bias_warnings = []
        if "loss_aversion" in active_biases:
            bias_warnings.append(
                "- LOSS AVERSION DETECTED: You may be holding losers too long. "
                "Evaluate positions objectively, not based on entry price."
            )
        if "revenge_trading" in active_biases:
            bias_warnings.append(
                "- REVENGE TRADING RISK: Recent losses may drive aggressive behavior. "
                "Reduce position sizes by 50%. Require higher conviction."
            )
        if "fomo" in active_biases:
            bias_warnings.append(
                "- FOMO DETECTED: Fear of missing out may cause chasing. "
                "Wait for pullbacks. There will always be another opportunity."
            )
        if "overconfidence" in active_biases:
            bias_warnings.append(
                "- OVERCONFIDENCE WARNING: Recent wins may inflate confidence. "
                "Remember: streaks end. Maintain discipline."
            )
        if "recency_bias" in active_biases:
            bias_warnings.append(
                "- RECENCY BIAS: You may be overweighting recent data. "
                "Consider historical patterns equally with recent moves."
            )
        if "confirmation_bias" in active_biases:
            bias_warnings.append(
                "- CONFIRMATION BIAS: Actively seek disconfirming evidence. "
                "What would make this trade WRONG?"
            )

        # Zone-specific guidance
        zone_guidance = {
            "FLOW": "Psychology: OPTIMAL. Execute with confidence.",
            "CHALLENGE": "Psychology: ENGAGED. Standard risk parameters.",
            "CAUTION": "Psychology: ELEVATED RISK. Consider reducing position sizes.",
            "DANGER": "Psychology: COMPROMISED. Require 80%+ conviction for any trade.",
            "TILT": "Psychology: CRITICAL. Trading NOT recommended. Capital preservation mode.",
        }.get(zone, "Psychology: Unknown state.")

        # Position size modifier based on psychology
        if zone in ["TILT", "DANGER"] or consecutive_losses >= 3:
            size_modifier = "REDUCE position sizes by 50-75%"
        elif zone == "CAUTION" or consecutive_losses >= 2:
            size_modifier = "REDUCE position sizes by 25-50%"
        elif consecutive_wins >= 4:
            size_modifier = "MAINTAIN standard sizes (avoid overconfidence scaling)"
        else:
            size_modifier = "Standard position sizing"

        # Build the prompt context
        context_parts = [
            "",
            "=" * 60,
            "COGNITIVE BIAS MITIGATION & PSYCHOLOGY CONTEXT",
            "=" * 60,
            "",
            "RESEARCH-BACKED BIAS AWARENESS (Kahneman, Siebold, Robbins):",
            "- You exhibit RECENCY BIAS: Weight historical data equally with recent.",
            "- You exhibit LOSS AVERSION: Losses feel 2x worse than gains. Stay objective.",
            "- You exhibit OVERCONFIDENCE after wins: Maintain humility and discipline.",
            "- Engage SYSTEM 2 THINKING: Slow, deliberate, logical analysis.",
            "",
            f"CURRENT TRADING PSYCHOLOGY STATE:",
            f"- Zone: {zone} | Readiness: {readiness:.0f}/100 | Energy: {energy:.0f}%",
            f"- Consecutive Wins: {consecutive_wins} | Consecutive Losses: {consecutive_losses}",
            f"- {zone_guidance}",
            f"- Position Sizing: {size_modifier}",
        ]

        if bias_warnings:
            context_parts.extend([
                "",
                "ACTIVE BIAS ALERTS (detected in recent trading):",
            ])
            context_parts.extend(bias_warnings)

        context_parts.extend([
            "",
            "DECISION FRAMEWORK (apply to every recommendation):",
            "1. What is the BEAR case? (always consider what could go wrong)",
            "2. Am I chasing or waiting for my setup?",
            "3. If this trade loses, will I regret the size?",
            "4. Is my conviction based on analysis or emotion?",
            "",
            "=" * 60,
        ])

        return "\n".join(context_parts)

    def get_position_size_modifier(self) -> float:
        """Get a multiplier for position sizing based on psychology state.

        Returns:
            Float multiplier (0.25 to 1.0) to apply to position sizes
        """
        state = self.state
        zone = state.current_zone.value

        # Start with base multiplier
        multiplier = 1.0

        # Zone adjustments
        if zone == "TILT":
            multiplier = 0.0  # No trading
        elif zone == "DANGER":
            multiplier = 0.25
        elif zone == "CAUTION":
            multiplier = 0.5
        elif zone == "CHALLENGE":
            multiplier = 0.75

        # Consecutive loss adjustments
        if state.consecutive_losses >= 4:
            multiplier = min(multiplier, 0.25)
        elif state.consecutive_losses >= 3:
            multiplier = min(multiplier, 0.5)
        elif state.consecutive_losses >= 2:
            multiplier = min(multiplier, 0.75)

        # Overconfidence check (don't increase size after wins)
        if state.consecutive_wins >= 4:
            multiplier = min(multiplier, 1.0)  # Cap at 1.0, no increase

        return multiplier

    def _is_on_cooldown(self, intervention_type: InterventionType) -> bool:
        """Check if intervention type is on cooldown."""
        if intervention_type not in self._intervention_cooldown:
            return False

        cooldown_until = self._intervention_cooldown[intervention_type]
        return datetime.now(timezone.utc) < cooldown_until

    def _set_cooldown(self, intervention_type: InterventionType) -> None:
        """Set cooldown for intervention type."""
        from datetime import timedelta

        minutes = self._cooldown_minutes.get(intervention_type, 10)
        self._intervention_cooldown[intervention_type] = datetime.now(timezone.utc) + timedelta(
            minutes=minutes
        )

    def _record_intervention(self, intervention: CoachingIntervention) -> None:
        """Record intervention to log file."""
        try:
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "intervention": intervention.to_dict(),
                "state_snapshot": self.state.to_dict(),
            }
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            logger.warning("Failed to record intervention: %s", e)

        # Track in session
        if self._session:
            self._session.interventions.append(intervention)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_coach: MentalToughnessCoach | None = None


def get_coach() -> MentalToughnessCoach:
    """Get the singleton coach instance."""
    global _coach
    if _coach is None:
        _coach = MentalToughnessCoach()
    return _coach


def coach_pre_trade(ticker: str = "") -> CoachingIntervention | None:
    """Quick pre-trade coaching check."""
    return get_coach().pre_trade_check(ticker)


def coach_post_trade(is_win: bool, pnl: float, ticker: str = "") -> list[CoachingIntervention]:
    """Quick post-trade coaching."""
    return get_coach().process_trade_result(is_win, pnl, ticker)


def is_ready_to_trade() -> tuple[bool, CoachingIntervention | None]:
    """Quick readiness check."""
    return get_coach().is_ready_to_trade()


def get_affirmation() -> str:
    """Get daily affirmation."""
    return get_coach().get_daily_affirmation()


def get_prompt_context() -> str:
    """Get psychology context for LLM prompt injection.

    This is the KEY function that bridges psychology to LLM decision-making.
    Call this and append the result to any LLM system prompt.
    """
    return get_coach().get_prompt_context()


def get_position_size_modifier() -> float:
    """Get position size multiplier based on psychology state.

    Returns float between 0.0 (no trading) and 1.0 (full size).
    """
    return get_coach().get_position_size_modifier()
