"""Psychology State Tracking.

Tracks the psychological state of the trading system using Siebold's
mental toughness principles. Monitors emotional zones, confidence levels,
and cognitive biases in real-time.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class EmotionalZone(str, Enum):
    """Emotional zones based on trading psychology research.

    World-class performers operate primarily in the FLOW zone,
    occasionally dipping into CHALLENGE, and rapidly recovering
    from DANGER zones.
    """

    FLOW = "flow"  # Optimal performance state
    CHALLENGE = "challenge"  # Healthy stress, focused
    CAUTION = "caution"  # Elevated emotions, need awareness
    DANGER = "danger"  # Emotional decision-making likely
    TILT = "tilt"  # Full emotional breakdown, stop trading


class CognitiveBias(str, Enum):
    """Common cognitive biases in trading (from behavioral finance)."""

    LOSS_AVERSION = "loss_aversion"  # Feeling losses 2x more than gains
    OVERCONFIDENCE = "overconfidence"  # Overestimating abilities
    RECENCY_BIAS = "recency_bias"  # Over-weighting recent events
    CONFIRMATION_BIAS = "confirmation_bias"  # Seeking confirming info
    ANCHORING = "anchoring"  # Stuck on reference points
    FOMO = "fomo"  # Fear of missing out
    REVENGE_TRADING = "revenge_trading"  # Trying to recover losses quickly
    ANALYSIS_PARALYSIS = "analysis_paralysis"  # Over-analyzing, not acting
    DISPOSITION_EFFECT = "disposition_effect"  # Selling winners too early


class ConfidenceLevel(str, Enum):
    """Confidence levels mapped to Siebold's framework.

    World-class performers maintain ELITE confidence even through
    adversity. Average performers oscillate based on recent results.
    """

    ELITE = "elite"  # Supreme self-confidence (Siebold #4)
    HIGH = "high"  # Strong confidence, ready to perform
    NORMAL = "normal"  # Baseline functional confidence
    SHAKEN = "shaken"  # Recent setbacks affecting mindset
    BROKEN = "broken"  # Need recovery before trading


@dataclass
class BiasAlert:
    """Record of a detected cognitive bias."""

    bias_type: CognitiveBias
    detected_at: datetime
    severity: float  # 0.0 to 1.0
    trigger: str  # What triggered this detection
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmotionalEvent:
    """Record of a significant emotional event."""

    timestamp: datetime
    event_type: str
    zone_before: EmotionalZone
    zone_after: EmotionalZone
    trigger: str
    notes: str = ""


@dataclass
class PsychologyState:
    """Complete psychological state of the trading system.

    This tracks emotional zone, confidence, detected biases, and
    provides the foundation for coaching interventions.
    """

    # Current state
    current_zone: EmotionalZone = EmotionalZone.FLOW
    confidence_level: ConfidenceLevel = ConfidenceLevel.NORMAL
    mental_energy: float = 1.0  # 0.0 to 1.0

    # Performance tracking (for psychology assessment)
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_drawdown_today: float = 0.0
    trades_today: int = 0

    # Siebold principles scores (0-10 scale)
    emotional_compartmentalization: float = 7.0  # Principle #2
    metacognition_level: float = 7.0  # Principle #5
    abundance_mindset: float = 7.0  # Principle #8
    coachability: float = 8.0  # Principle #6
    purpose_clarity: float = 8.0  # Principle #7

    # Detected biases and events
    active_biases: list[BiasAlert] = field(default_factory=list)
    recent_events: list[EmotionalEvent] = field(default_factory=list)

    # Session tracking
    session_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_coaching_intervention: datetime | None = None

    def update_after_trade(
        self,
        is_win: bool,
        pnl: float,
        trade_reason: str,
    ) -> list[BiasAlert]:
        """Update state after a trade and detect biases.

        Returns list of newly detected biases.
        """
        self.trades_today += 1
        new_biases: list[BiasAlert] = []

        if is_win:
            self.consecutive_wins += 1
            self.consecutive_losses = 0

            # Detect overconfidence after winning streak
            if self.consecutive_wins >= 3:
                new_biases.append(
                    BiasAlert(
                        bias_type=CognitiveBias.OVERCONFIDENCE,
                        detected_at=datetime.now(timezone.utc),
                        severity=min(0.3 + (self.consecutive_wins - 3) * 0.1, 1.0),
                        trigger=f"Winning streak: {self.consecutive_wins} wins",
                        context={"consecutive_wins": self.consecutive_wins},
                    )
                )
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            self.max_drawdown_today = max(self.max_drawdown_today, abs(pnl))

            # Detect loss aversion and revenge trading risk
            if self.consecutive_losses >= 2:
                new_biases.append(
                    BiasAlert(
                        bias_type=CognitiveBias.LOSS_AVERSION,
                        detected_at=datetime.now(timezone.utc),
                        severity=min(0.3 + (self.consecutive_losses - 2) * 0.15, 1.0),
                        trigger=f"Losing streak: {self.consecutive_losses} losses",
                        context={"consecutive_losses": self.consecutive_losses},
                    )
                )

            if self.consecutive_losses >= 3:
                new_biases.append(
                    BiasAlert(
                        bias_type=CognitiveBias.REVENGE_TRADING,
                        detected_at=datetime.now(timezone.utc),
                        severity=min(0.4 + (self.consecutive_losses - 3) * 0.2, 1.0),
                        trigger=f"High revenge trading risk after {self.consecutive_losses} losses",
                        context={"drawdown_today": self.max_drawdown_today},
                    )
                )

        # Update emotional zone based on state
        self._update_emotional_zone()

        # Add new biases to active list
        self.active_biases.extend(new_biases)

        return new_biases

    def _update_emotional_zone(self) -> None:
        """Update emotional zone based on current state."""
        old_zone = self.current_zone

        # Determine zone based on multiple factors
        if self.consecutive_losses >= 5 or self.mental_energy < 0.2:
            self.current_zone = EmotionalZone.TILT
        elif self.consecutive_losses >= 3 or self.mental_energy < 0.4:
            self.current_zone = EmotionalZone.DANGER
        elif self.consecutive_losses >= 2 or len(self.active_biases) >= 3:
            self.current_zone = EmotionalZone.CAUTION
        elif self.consecutive_wins >= 5 or len(self.active_biases) >= 2:
            self.current_zone = EmotionalZone.CHALLENGE
        else:
            self.current_zone = EmotionalZone.FLOW

        # Log zone transitions
        if old_zone != self.current_zone:
            self.recent_events.append(
                EmotionalEvent(
                    timestamp=datetime.now(timezone.utc),
                    event_type="zone_transition",
                    zone_before=old_zone,
                    zone_after=self.current_zone,
                    trigger="auto_assessment",
                )
            )

    def apply_coaching(self, intervention_type: str) -> None:
        """Record that coaching was applied."""
        self.last_coaching_intervention = datetime.now(timezone.utc)

        # Coaching reduces bias severity
        for bias in self.active_biases:
            bias.severity *= 0.7  # 30% reduction per intervention

        # Remove resolved biases
        self.active_biases = [b for b in self.active_biases if b.severity >= 0.1]

        # Improve mental energy slightly
        self.mental_energy = min(1.0, self.mental_energy + 0.1)

    def reset_for_new_session(self) -> None:
        """Reset state for a new trading session."""
        self.current_zone = EmotionalZone.FLOW
        self.confidence_level = ConfidenceLevel.NORMAL
        self.mental_energy = 1.0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.max_drawdown_today = 0.0
        self.trades_today = 0
        self.active_biases = []
        self.recent_events = []
        self.session_start = datetime.now(timezone.utc)
        self.last_coaching_intervention = None

    def get_readiness_score(self) -> float:
        """Calculate overall trading readiness (0-100)."""
        scores = [
            self._zone_score() * 25,  # 25% weight
            self._confidence_score() * 25,  # 25% weight
            self._mental_energy_score() * 20,  # 20% weight
            self._bias_penalty() * 15,  # 15% weight
            self._siebold_score() * 15,  # 15% weight
        ]
        return sum(scores)

    def _zone_score(self) -> float:
        """Score based on emotional zone."""
        zone_scores = {
            EmotionalZone.FLOW: 1.0,
            EmotionalZone.CHALLENGE: 0.8,
            EmotionalZone.CAUTION: 0.5,
            EmotionalZone.DANGER: 0.2,
            EmotionalZone.TILT: 0.0,
        }
        return zone_scores.get(self.current_zone, 0.5)

    def _confidence_score(self) -> float:
        """Score based on confidence level."""
        confidence_scores = {
            ConfidenceLevel.ELITE: 1.0,
            ConfidenceLevel.HIGH: 0.85,
            ConfidenceLevel.NORMAL: 0.7,
            ConfidenceLevel.SHAKEN: 0.4,
            ConfidenceLevel.BROKEN: 0.1,
        }
        return confidence_scores.get(self.confidence_level, 0.5)

    def _mental_energy_score(self) -> float:
        """Score based on mental energy."""
        return self.mental_energy

    def _bias_penalty(self) -> float:
        """Penalty based on active biases."""
        if not self.active_biases:
            return 1.0
        total_severity = sum(b.severity for b in self.active_biases)
        return max(0.0, 1.0 - (total_severity * 0.2))

    def _siebold_score(self) -> float:
        """Average of Siebold principle scores."""
        principles = [
            self.emotional_compartmentalization,
            self.metacognition_level,
            self.abundance_mindset,
            self.coachability,
            self.purpose_clarity,
        ]
        return sum(principles) / len(principles) / 10  # Normalize to 0-1

    def to_dict(self) -> dict[str, Any]:
        """Serialize state to dictionary."""
        return {
            "current_zone": self.current_zone.value,
            "confidence_level": self.confidence_level.value,
            "mental_energy": self.mental_energy,
            "consecutive_wins": self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses,
            "max_drawdown_today": self.max_drawdown_today,
            "trades_today": self.trades_today,
            "siebold_principles": {
                "emotional_compartmentalization": self.emotional_compartmentalization,
                "metacognition_level": self.metacognition_level,
                "abundance_mindset": self.abundance_mindset,
                "coachability": self.coachability,
                "purpose_clarity": self.purpose_clarity,
            },
            "active_biases": [
                {
                    "type": b.bias_type.value,
                    "severity": b.severity,
                    "trigger": b.trigger,
                }
                for b in self.active_biases
            ],
            "readiness_score": self.get_readiness_score(),
            "session_start": self.session_start.isoformat(),
        }


class PsychologyStateManager:
    """Manages persistence and loading of psychology state."""

    def __init__(self, state_path: str | Path | None = None) -> None:
        self.state_path = Path(state_path) if state_path else Path("data/psychology_state.json")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state: PsychologyState | None = None

    def get_state(self) -> PsychologyState:
        """Get current psychology state, loading from disk if needed."""
        if self._state is None:
            self._state = self._load_or_create()
        return self._state

    def save_state(self) -> None:
        """Persist current state to disk."""
        if self._state is None:
            return

        try:
            with self.state_path.open("w", encoding="utf-8") as f:
                json.dump(self._state.to_dict(), f, indent=2, default=str)
        except Exception as e:
            logger.warning("Failed to save psychology state: %s", e)

    def _load_or_create(self) -> PsychologyState:
        """Load state from disk or create new."""
        if not self.state_path.exists():
            return PsychologyState()

        try:
            with self.state_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return self._from_dict(data)
        except Exception as e:
            logger.warning("Failed to load psychology state: %s. Creating new.", e)
            return PsychologyState()

    def _from_dict(self, data: dict[str, Any]) -> PsychologyState:
        """Deserialize state from dictionary."""
        state = PsychologyState()
        state.current_zone = EmotionalZone(data.get("current_zone", "flow"))
        state.confidence_level = ConfidenceLevel(data.get("confidence_level", "normal"))
        state.mental_energy = data.get("mental_energy", 1.0)
        state.consecutive_wins = data.get("consecutive_wins", 0)
        state.consecutive_losses = data.get("consecutive_losses", 0)
        state.max_drawdown_today = data.get("max_drawdown_today", 0.0)
        state.trades_today = data.get("trades_today", 0)

        siebold = data.get("siebold_principles", {})
        state.emotional_compartmentalization = siebold.get("emotional_compartmentalization", 7.0)
        state.metacognition_level = siebold.get("metacognition_level", 7.0)
        state.abundance_mindset = siebold.get("abundance_mindset", 7.0)
        state.coachability = siebold.get("coachability", 8.0)
        state.purpose_clarity = siebold.get("purpose_clarity", 8.0)

        return state
