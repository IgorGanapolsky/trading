"""
Behavioral Finance Module - Based on "Your Money and Your Brain" by Jason Zweig

This module implements key principles from behavioral finance to prevent
psychological biases from affecting trading decisions:

1. Emotional Control - Prevent fear and greed from overriding rational thinking
2. Anticipation vs. Reality - Track expected vs actual outcomes
3. Pattern Recognition Bias - Prevent overconfidence from perceived patterns
4. Loss Aversion - Handle losses without becoming overly conservative
5. Automation - Reduce emotional interference through systematic processes
6. Diversification - Prevent overexposure to single assets
7. Realistic Goals - Set and track achievable objectives
8. Emotional Registry - Track decision patterns for continuous improvement

Author: Trading System
Date: 2025-11-24
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class EmotionalState(Enum):
    """Emotional states that can affect trading decisions."""

    FEAR = "fear"
    GREED = "greed"
    OVERCONFIDENCE = "overconfidence"
    PANIC = "panic"
    EUPHORIA = "euphoria"
    NEUTRAL = "neutral"
    ANXIOUS = "anxious"


class BiasType(Enum):
    """Types of behavioral biases to detect and prevent."""

    PATTERN_RECOGNITION = "pattern_recognition"
    LOSS_AVERSION = "loss_aversion"
    CONFIRMATION_BIAS = "confirmation_bias"
    ANCHORING = "anchoring"
    OVERCONFIDENCE = "overconfidence"
    RECENCY_BIAS = "recency_bias"
    HERD_MENTALITY = "herd_mentality"


@dataclass
class TradeExpectation:
    """Track expected vs actual trade outcomes."""

    symbol: str
    expected_return_pct: float
    expected_confidence: float
    entry_price: float
    entry_date: datetime
    exit_price: Optional[float] = None
    exit_date: Optional[datetime] = None
    actual_return_pct: Optional[float] = None
    actual_confidence: Optional[float] = None
    expectation_gap: Optional[float] = None  # actual - expected


@dataclass
class EmotionalRecord:
    """Record emotional responses to trading decisions."""

    timestamp: datetime
    event_type: str  # "trade_execution", "loss", "gain", "decision_point"
    symbol: Optional[str] = None
    emotional_state: EmotionalState = EmotionalState.NEUTRAL
    intensity: float = 0.0  # 0.0 to 1.0
    decision_made: str = ""
    outcome: Optional[str] = None
    notes: str = ""


@dataclass
class PatternCheck:
    """Check for false pattern recognition."""

    pattern_type: str
    detected_pattern: str
    confidence: float
    historical_success_rate: float
    sample_size: int
    is_valid: bool


class BehavioralFinanceManager:
    """
    Behavioral Finance Manager implementing Jason Zweig's principles.

    This manager prevents psychological biases from affecting trading decisions
    by tracking emotions, expectations, patterns, and decision-making history.
    """

    def __init__(
        self,
        data_dir: str = "data",
        max_pattern_confidence: float = 0.7,
        min_pattern_sample_size: int = 20,
        loss_aversion_threshold: float = -0.02,  # -2% triggers loss aversion check
    ):
        """
        Initialize the Behavioral Finance Manager.

        Args:
            data_dir: Directory to store behavioral finance data
            max_pattern_confidence: Maximum confidence allowed for patterns without validation
            min_pattern_sample_size: Minimum samples needed to validate a pattern
            loss_aversion_threshold: Loss percentage that triggers loss aversion checks
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.max_pattern_confidence = max_pattern_confidence
        self.min_pattern_sample_size = min_pattern_sample_size
        self.loss_aversion_threshold = loss_aversion_threshold

        # Storage for tracking
        self.expectations: list[TradeExpectation] = []
        self.emotional_registry: list[EmotionalRecord] = []
        self.pattern_history: dict[str, list[PatternCheck]] = {}
        self.decision_history: list[dict[str, Any]] = []

        # Load historical data
        self._load_historical_data()

        logger.info("Behavioral Finance Manager initialized")
        logger.info(f"  - Max pattern confidence: {max_pattern_confidence}")
        logger.info(f"  - Min pattern sample size: {min_pattern_sample_size}")
        logger.info(f"  - Loss aversion threshold: {loss_aversion_threshold}%")

    def record_trade_expectation(
        self,
        symbol: str,
        expected_return_pct: float,
        expected_confidence: float,
        entry_price: float,
    ) -> TradeExpectation:
        """
        Record trade expectations before execution.

        Principle: Anticipation vs. Reality - Track what we expect vs what happens.

        Args:
            symbol: Trading symbol
            expected_return_pct: Expected return percentage
            expected_confidence: Confidence level (0-1)
            entry_price: Entry price

        Returns:
            TradeExpectation object
        """
        expectation = TradeExpectation(
            symbol=symbol,
            expected_return_pct=expected_return_pct,
            expected_confidence=expected_confidence,
            entry_price=entry_price,
            entry_date=datetime.now(),
        )

        self.expectations.append(expectation)
        self._save_expectations()

        logger.info(
            f"Recorded expectation for {symbol}: "
            f"expected_return={expected_return_pct:.2f}%, "
            f"confidence={expected_confidence:.2f}"
        )

        return expectation

    def update_trade_outcome(
        self,
        expectation: TradeExpectation,
        exit_price: float,
        actual_return_pct: float,
    ) -> None:
        """
        Update trade outcome and calculate expectation gap.

        Principle: Anticipation vs. Reality - Compare expected vs actual.

        Args:
            expectation: TradeExpectation object
            exit_price: Exit price
            actual_return_pct: Actual return percentage
        """
        expectation.exit_price = exit_price
        expectation.exit_date = datetime.now()
        expectation.actual_return_pct = actual_return_pct
        expectation.expectation_gap = actual_return_pct - expectation.expected_return_pct

        # Record emotional response based on gap
        if expectation.expectation_gap < -0.05:  # Much worse than expected
            self.record_emotion(
                event_type="trade_outcome",
                symbol=expectation.symbol,
                emotional_state=EmotionalState.FEAR,
                intensity=abs(expectation.expectation_gap) * 10,
                decision_made=f"Expected {expectation.expected_return_pct:.2f}%, got {actual_return_pct:.2f}%",
                outcome="disappointment",
            )
        elif expectation.expectation_gap > 0.05:  # Much better than expected
            self.record_emotion(
                event_type="trade_outcome",
                symbol=expectation.symbol,
                emotional_state=EmotionalState.EUPHORIA,
                intensity=expectation.expectation_gap * 10,
                decision_made=f"Expected {expectation.expected_return_pct:.2f}%, got {actual_return_pct:.2f}%",
                outcome="surprise_gain",
            )

        self._save_expectations()

        logger.info(
            f"Updated outcome for {expectation.symbol}: "
            f"expected={expectation.expected_return_pct:.2f}%, "
            f"actual={actual_return_pct:.2f}%, "
            f"gap={expectation.expectation_gap:.2f}%"
        )

    def record_emotion(
        self,
        event_type: str,
        symbol: Optional[str] = None,
        emotional_state: EmotionalState = EmotionalState.NEUTRAL,
        intensity: float = 0.0,
        decision_made: str = "",
        outcome: Optional[str] = None,
        notes: str = "",
    ) -> None:
        """
        Record emotional response to trading events.

        Principle: Emotional Registry - Track emotional patterns for improvement.

        Args:
            event_type: Type of event (trade_execution, loss, gain, etc.)
            symbol: Trading symbol if applicable
            emotional_state: Current emotional state
            intensity: Intensity level (0.0 to 1.0)
            decision_made: Description of decision made
            outcome: Outcome of the decision
            notes: Additional notes
        """
        record = EmotionalRecord(
            timestamp=datetime.now(),
            event_type=event_type,
            symbol=symbol,
            emotional_state=emotional_state,
            intensity=min(max(intensity, 0.0), 1.0),  # Clamp to [0, 1]
            decision_made=decision_made,
            outcome=outcome,
            notes=notes,
        )

        self.emotional_registry.append(record)
        self._save_emotional_registry()

        logger.debug(
            f"Recorded emotion: {emotional_state.value} "
            f"(intensity={intensity:.2f}) for {event_type}"
        )

    def check_pattern_recognition_bias(
        self,
        pattern_type: str,
        detected_pattern: str,
        confidence: float,
    ) -> tuple[bool, str]:
        """
        Check for pattern recognition bias.

        Principle: Pattern Recognition Bias - Prevent overconfidence from perceived patterns.

        Args:
            pattern_type: Type of pattern (e.g., "momentum", "reversal", "breakout")
            detected_pattern: Description of detected pattern
            confidence: Confidence level in the pattern (0-1)

        Returns:
            Tuple of (is_valid, reason)
        """
        # Check if we have enough historical data for this pattern
        if pattern_type not in self.pattern_history:
            self.pattern_history[pattern_type] = []

        pattern_checks = self.pattern_history[pattern_type]

        # If confidence is too high without validation, flag as potential bias
        if (
            confidence > self.max_pattern_confidence
            and len(pattern_checks) < self.min_pattern_sample_size
        ):
            warning = (
                f"High pattern confidence ({confidence:.2f}) without sufficient "
                f"historical validation (only {len(pattern_checks)} samples). "
                f"Requiring {self.min_pattern_sample_size} samples for validation."
            )
            logger.warning(warning)
            return False, warning

        # Calculate historical success rate
        if len(pattern_checks) >= self.min_pattern_sample_size:
            successful_patterns = sum(1 for p in pattern_checks if p.is_valid)
            success_rate = successful_patterns / len(pattern_checks)

            # If historical success rate is low, reduce confidence
            if success_rate < 0.5 and confidence > 0.6:
                adjusted_confidence = confidence * success_rate
                warning = (
                    f"Pattern has low historical success rate ({success_rate:.2%}). "
                    f"Adjusted confidence from {confidence:.2f} to {adjusted_confidence:.2f}"
                )
                logger.warning(warning)
                return False, warning

        # Record the pattern check
        pattern_check = PatternCheck(
            pattern_type=pattern_type,
            detected_pattern=detected_pattern,
            confidence=confidence,
            historical_success_rate=(
                sum(1 for p in pattern_checks if p.is_valid) / len(pattern_checks)
                if pattern_checks
                else 0.0
            ),
            sample_size=len(pattern_checks),
            is_valid=True,  # Will be updated later based on outcome
        )

        self.pattern_history[pattern_type].append(pattern_check)
        self._save_pattern_history()

        return True, "Pattern validated"

    def update_pattern_outcome(
        self,
        pattern_type: str,
        was_successful: bool,
    ) -> None:
        """
        Update pattern outcome to improve future validation.

        Args:
            pattern_type: Type of pattern
            was_successful: Whether the pattern prediction was successful
        """
        if pattern_type in self.pattern_history and self.pattern_history[pattern_type]:
            # Update the most recent pattern check
            self.pattern_history[pattern_type][-1].is_valid = was_successful
            self._save_pattern_history()

    def check_loss_aversion(
        self,
        recent_losses: list[float],
        account_value: float,
        daily_pl: float,
    ) -> tuple[bool, str]:
        """
        Check for loss aversion bias.

        Principle: Loss Aversion - Prevent becoming overly conservative after losses.

        Args:
            recent_losses: List of recent loss percentages
            account_value: Current account value
            daily_pl: Today's profit/loss

        Returns:
            Tuple of (should_trade, reason)
        """
        if not recent_losses:
            return True, "No recent losses"

        # Check if we're experiencing significant losses
        avg_loss = np.mean(recent_losses)
        max_loss = max(recent_losses)

        # If losses exceed threshold, check for loss aversion
        if max_loss < self.loss_aversion_threshold:
            # Check if we're becoming too conservative
            recent_emotions = [
                e for e in self.emotional_registry[-10:] if e.emotional_state == EmotionalState.FEAR
            ]

            if len(recent_emotions) > 5:  # Too many fear responses
                warning = (
                    f"Loss aversion detected: {len(recent_emotions)} fear responses "
                    f"in recent decisions. Average loss: {avg_loss:.2f}%. "
                    f"Consider: losses are normal, don't become overly conservative."
                )
                logger.warning(warning)

                # Record the loss aversion event
                self.record_emotion(
                    event_type="loss_aversion_check",
                    emotional_state=EmotionalState.FEAR,
                    intensity=abs(max_loss) * 10,
                    decision_made="Loss aversion bias detected",
                    outcome="potential_overconservatism",
                    notes=f"Recent losses: {recent_losses}",
                )

                # Still allow trading but with warning
                return True, warning

        return True, "Loss aversion check passed"

    def check_emotional_state(self) -> tuple[EmotionalState, float]:
        """
        Check current emotional state based on recent records.

        Returns:
            Tuple of (dominant_emotion, intensity)
        """
        if not self.emotional_registry:
            return EmotionalState.NEUTRAL, 0.0

        # Look at last 10 emotional records
        recent_emotions = self.emotional_registry[-10:]

        # Count occurrences of each emotion
        emotion_counts: dict[EmotionalState, tuple[int, float]] = {}
        for record in recent_emotions:
            state = record.emotional_state
            if state not in emotion_counts:
                emotion_counts[state] = (0, 0.0)
            count, total_intensity = emotion_counts[state]
            emotion_counts[state] = (count + 1, total_intensity + record.intensity)

        if not emotion_counts:
            return EmotionalState.NEUTRAL, 0.0

        # Find dominant emotion
        dominant_emotion = max(
            emotion_counts.items(),
            key=lambda x: x[1][0],  # Sort by count
        )[0]

        # Calculate average intensity
        count, total_intensity = emotion_counts[dominant_emotion]
        avg_intensity = total_intensity / count if count > 0 else 0.0

        return dominant_emotion, avg_intensity

    def should_proceed_with_trade(
        self,
        symbol: str,
        expected_return: float,
        confidence: float,
        pattern_type: Optional[str] = None,
        recent_losses: Optional[list[float]] = None,
    ) -> tuple[bool, str]:
        """
        Comprehensive check to determine if trade should proceed.

        Combines all behavioral finance checks.

        Args:
            symbol: Trading symbol
            expected_return: Expected return percentage
            confidence: Confidence level (0-1)
            pattern_type: Type of pattern if applicable
            recent_losses: Recent loss percentages

        Returns:
            Tuple of (should_proceed, reason)
        """
        # Check emotional state
        emotion, intensity = self.check_emotional_state()

        if emotion in [EmotionalState.PANIC, EmotionalState.FEAR] and intensity > 0.7:
            return False, (
                f"High {emotion.value} intensity ({intensity:.2f}) detected. "
                f"Pausing trading to prevent emotional decisions."
            )

        if emotion == EmotionalState.EUPHORIA and intensity > 0.8:
            return False, (
                f"High euphoria intensity ({intensity:.2f}) detected. "
                f"Risk of overconfidence. Pausing trading."
            )

        # Check pattern recognition bias
        if pattern_type:
            is_valid, reason = self.check_pattern_recognition_bias(
                pattern_type=pattern_type,
                detected_pattern=f"{symbol} pattern",
                confidence=confidence,
            )
            if not is_valid:
                return False, reason

        # Check loss aversion
        if recent_losses:
            should_trade, reason = self.check_loss_aversion(
                recent_losses=recent_losses,
                account_value=0.0,  # Will be provided by caller if needed
                daily_pl=0.0,
            )
            if "overconservatism" in reason.lower():
                # Still allow but log warning
                logger.warning(reason)

        return True, "All behavioral checks passed"

    def get_behavioral_summary(self) -> dict[str, Any]:
        """
        Get summary of behavioral finance metrics.

        Returns:
            Dictionary with behavioral finance summary
        """
        # Calculate expectation gaps
        completed_expectations = [e for e in self.expectations if e.expectation_gap is not None]
        avg_expectation_gap = (
            np.mean([e.expectation_gap for e in completed_expectations])
            if completed_expectations
            else 0.0
        )

        # Get emotional state
        dominant_emotion, intensity = self.check_emotional_state()

        # Pattern success rates
        pattern_success_rates = {}
        for pattern_type, checks in self.pattern_history.items():
            if checks:
                successful = sum(1 for c in checks if c.is_valid)
                pattern_success_rates[pattern_type] = successful / len(checks)

        return {
            "dominant_emotion": dominant_emotion.value,
            "emotion_intensity": intensity,
            "total_expectations": len(self.expectations),
            "completed_expectations": len(completed_expectations),
            "avg_expectation_gap": avg_expectation_gap,
            "pattern_success_rates": pattern_success_rates,
            "total_emotional_records": len(self.emotional_registry),
            "recent_emotions": [
                {
                    "state": e.emotional_state.value,
                    "intensity": e.intensity,
                    "event": e.event_type,
                }
                for e in self.emotional_registry[-5:]
            ],
        }

    def _load_historical_data(self) -> None:
        """Load historical behavioral finance data from disk."""
        expectations_file = self.data_dir / "behavioral_expectations.json"
        emotions_file = self.data_dir / "behavioral_emotions.json"
        patterns_file = self.data_dir / "behavioral_patterns.json"

        # Load expectations
        if expectations_file.exists():
            try:
                with open(expectations_file) as f:
                    data = json.load(f)
                    self.expectations = [
                        TradeExpectation(
                            symbol=e["symbol"],
                            expected_return_pct=e["expected_return_pct"],
                            expected_confidence=e["expected_confidence"],
                            entry_price=e["entry_price"],
                            entry_date=datetime.fromisoformat(e["entry_date"]),
                            exit_price=e.get("exit_price"),
                            exit_date=(
                                datetime.fromisoformat(e["exit_date"])
                                if e.get("exit_date")
                                else None
                            ),
                            actual_return_pct=e.get("actual_return_pct"),
                            actual_confidence=e.get("actual_confidence"),
                            expectation_gap=e.get("expectation_gap"),
                        )
                        for e in data
                    ]
                logger.info(f"Loaded {len(self.expectations)} historical expectations")
            except Exception as e:
                logger.warning(f"Failed to load expectations: {e}")

        # Load emotional registry
        if emotions_file.exists():
            try:
                with open(emotions_file) as f:
                    data = json.load(f)
                    self.emotional_registry = [
                        EmotionalRecord(
                            timestamp=datetime.fromisoformat(e["timestamp"]),
                            event_type=e["event_type"],
                            symbol=e.get("symbol"),
                            emotional_state=EmotionalState(e["emotional_state"]),
                            intensity=e["intensity"],
                            decision_made=e["decision_made"],
                            outcome=e.get("outcome"),
                            notes=e.get("notes", ""),
                        )
                        for e in data
                    ]
                logger.info(f"Loaded {len(self.emotional_registry)} emotional records")
            except Exception as e:
                logger.warning(f"Failed to load emotional registry: {e}")

        # Load pattern history
        if patterns_file.exists():
            try:
                with open(patterns_file) as f:
                    data = json.load(f)
                    self.pattern_history = {}
                    for pattern_type, patterns in data.items():
                        self.pattern_history[pattern_type] = [
                            PatternCheck(
                                pattern_type=p["pattern_type"],
                                detected_pattern=p["detected_pattern"],
                                confidence=p["confidence"],
                                historical_success_rate=p["historical_success_rate"],
                                sample_size=p["sample_size"],
                                is_valid=p["is_valid"],
                            )
                            for p in patterns
                        ]
                logger.info(f"Loaded pattern history for {len(self.pattern_history)} pattern types")
            except Exception as e:
                logger.warning(f"Failed to load pattern history: {e}")

    def _save_expectations(self) -> None:
        """Save expectations to disk."""
        expectations_file = self.data_dir / "behavioral_expectations.json"
        try:
            data = [
                {
                    "symbol": e.symbol,
                    "expected_return_pct": e.expected_return_pct,
                    "expected_confidence": e.expected_confidence,
                    "entry_price": e.entry_price,
                    "entry_date": e.entry_date.isoformat(),
                    "exit_price": e.exit_price,
                    "exit_date": e.exit_date.isoformat() if e.exit_date else None,
                    "actual_return_pct": e.actual_return_pct,
                    "actual_confidence": e.actual_confidence,
                    "expectation_gap": e.expectation_gap,
                }
                for e in self.expectations
            ]
            with open(expectations_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save expectations: {e}")

    def _save_emotional_registry(self) -> None:
        """Save emotional registry to disk."""
        emotions_file = self.data_dir / "behavioral_emotions.json"
        try:
            data = [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type,
                    "symbol": e.symbol,
                    "emotional_state": e.emotional_state.value,
                    "intensity": e.intensity,
                    "decision_made": e.decision_made,
                    "outcome": e.outcome,
                    "notes": e.notes,
                }
                for e in self.emotional_registry
            ]
            with open(emotions_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save emotional registry: {e}")

    def _save_pattern_history(self) -> None:
        """Save pattern history to disk."""
        patterns_file = self.data_dir / "behavioral_patterns.json"
        try:
            data = {
                pattern_type: [
                    {
                        "pattern_type": p.pattern_type,
                        "detected_pattern": p.detected_pattern,
                        "confidence": p.confidence,
                        "historical_success_rate": p.historical_success_rate,
                        "sample_size": p.sample_size,
                        "is_valid": p.is_valid,
                    }
                    for p in patterns
                ]
                for pattern_type, patterns in self.pattern_history.items()
            }
            with open(patterns_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save pattern history: {e}")
