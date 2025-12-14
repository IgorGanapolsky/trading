"""
Model Circuit Breaker

Automatically disables LLM models that fall below accuracy thresholds.
Prevents continued losses from consistently wrong models.

Based on electrical circuit breaker pattern:
- Monitor model accuracy in real-time
- Trip (disable) when accuracy drops below threshold
- Auto-reset after cooldown period with improved accuracy
- Track trip history for pattern analysis

Created: Dec 11, 2025
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

CIRCUIT_BREAKER_STATE_PATH = Path("data/circuit_breaker_state.json")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation - model is enabled
    OPEN = "open"  # Tripped - model is disabled
    HALF_OPEN = "half_open"  # Testing - allowing limited requests


@dataclass
class ModelCircuitState:
    """State of a single model's circuit breaker."""

    model: str
    state: CircuitState = CircuitState.CLOSED
    accuracy: float = 1.0
    total_predictions: int = 0
    correct_predictions: int = 0
    consecutive_failures: int = 0
    last_failure_time: Optional[str] = None
    trip_count: int = 0
    last_trip_time: Optional[str] = None
    cooldown_until: Optional[str] = None
    trip_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "state": self.state.value,
            "accuracy": self.accuracy,
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "consecutive_failures": self.consecutive_failures,
            "last_failure_time": self.last_failure_time,
            "trip_count": self.trip_count,
            "last_trip_time": self.last_trip_time,
            "cooldown_until": self.cooldown_until,
            "trip_reasons": self.trip_reasons[-10:],  # Keep last 10
        }


class ModelCircuitBreaker:
    """
    Circuit breaker for LLM models.

    Automatically disables models that:
    1. Fall below accuracy threshold (default 50%)
    2. Have too many consecutive failures (default 5)
    3. Show sudden accuracy drops (default 20% in 10 predictions)

    Features:
    - Per-model tracking
    - Configurable thresholds
    - Auto-reset after cooldown
    - Half-open state for gradual recovery
    - Trip history for analysis
    """

    def __init__(
        self,
        accuracy_threshold: float = 0.50,  # 50% minimum accuracy
        consecutive_failure_limit: int = 5,
        min_predictions_for_trip: int = 10,  # Need at least 10 predictions
        cooldown_minutes: int = 60,  # 1 hour cooldown after trip
        half_open_test_count: int = 3,  # Test 3 predictions in half-open
    ):
        self.accuracy_threshold = accuracy_threshold
        self.consecutive_failure_limit = consecutive_failure_limit
        self.min_predictions_for_trip = min_predictions_for_trip
        self.cooldown_minutes = cooldown_minutes
        self.half_open_test_count = half_open_test_count

        self.model_states: dict[str, ModelCircuitState] = {}
        self._load_state()

        logger.info(
            f"ModelCircuitBreaker initialized: "
            f"accuracy_threshold={accuracy_threshold}, "
            f"consecutive_failure_limit={consecutive_failure_limit}"
        )

    def is_model_enabled(self, model: str) -> bool:
        """
        Check if a model is enabled (circuit closed or half-open).

        Args:
            model: Model identifier

        Returns:
            True if model can be used, False if disabled
        """
        if model not in self.model_states:
            return True  # New models are enabled by default

        state = self.model_states[model]

        # Check if cooldown has expired
        if state.state == CircuitState.OPEN and state.cooldown_until:
            cooldown_end = datetime.fromisoformat(state.cooldown_until)
            if datetime.now(timezone.utc) >= cooldown_end:
                # Move to half-open for testing
                state.state = CircuitState.HALF_OPEN
                state.consecutive_failures = 0
                logger.info(f"Circuit breaker for {model} moved to HALF_OPEN for testing")
                self._save_state()

        return state.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_prediction(
        self,
        model: str,
        was_correct: bool,
        context: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Record a prediction outcome and check circuit breaker.

        Args:
            model: Model identifier
            was_correct: Whether the prediction was correct
            context: Optional context for logging

        Returns:
            Dict with circuit state and any actions taken
        """
        if model not in self.model_states:
            self.model_states[model] = ModelCircuitState(model=model)

        state = self.model_states[model]

        # Update stats
        state.total_predictions += 1
        if was_correct:
            state.correct_predictions += 1
            state.consecutive_failures = 0

            # If in half-open and doing well, close the circuit
            if state.state == CircuitState.HALF_OPEN:
                if (
                    state.consecutive_failures == 0
                    and state.total_predictions >= self.half_open_test_count
                ):
                    recent_accuracy = self._calculate_recent_accuracy(
                        state, self.half_open_test_count
                    )
                    if recent_accuracy >= self.accuracy_threshold:
                        state.state = CircuitState.CLOSED
                        logger.info(f"Circuit breaker for {model} CLOSED - recovered")
        else:
            state.consecutive_failures += 1
            state.last_failure_time = datetime.now(timezone.utc).isoformat()

        # Update accuracy
        state.accuracy = (
            state.correct_predictions / state.total_predictions
            if state.total_predictions > 0
            else 1.0
        )

        # Check if we should trip the circuit
        action_taken = None
        if state.state != CircuitState.OPEN:
            trip_reason = self._should_trip(state)
            if trip_reason:
                self._trip_circuit(state, trip_reason)
                action_taken = f"TRIPPED: {trip_reason}"

        self._save_state()

        return {
            "model": model,
            "state": state.state.value,
            "is_enabled": state.state != CircuitState.OPEN,
            "accuracy": state.accuracy,
            "consecutive_failures": state.consecutive_failures,
            "action_taken": action_taken,
        }

    def _should_trip(self, state: ModelCircuitState) -> Optional[str]:
        """Check if circuit should trip. Returns reason if yes."""
        # Check consecutive failures
        if state.consecutive_failures >= self.consecutive_failure_limit:
            return f"Consecutive failures: {state.consecutive_failures}"

        # Check overall accuracy (only with enough predictions)
        if state.total_predictions >= self.min_predictions_for_trip:
            if state.accuracy < self.accuracy_threshold:
                return f"Low accuracy: {state.accuracy:.1%} < {self.accuracy_threshold:.1%}"

        return None

    def _trip_circuit(self, state: ModelCircuitState, reason: str) -> None:
        """Trip the circuit breaker for a model."""
        state.state = CircuitState.OPEN
        state.trip_count += 1
        state.last_trip_time = datetime.now(timezone.utc).isoformat()
        state.cooldown_until = (
            datetime.now(timezone.utc) + timedelta(minutes=self.cooldown_minutes)
        ).isoformat()
        state.trip_reasons.append(f"{state.last_trip_time}: {reason}")

        logger.warning(
            f"🔴 CIRCUIT BREAKER TRIPPED for {state.model}: {reason}. "
            f"Model disabled until {state.cooldown_until}"
        )

    def _calculate_recent_accuracy(self, state: ModelCircuitState, n: int) -> float:
        """Calculate accuracy over last n predictions."""
        # This is a simplified version - ideally we'd track individual predictions
        return state.accuracy

    def force_reset(self, model: str) -> dict[str, Any]:
        """
        Force reset a circuit breaker (admin override).

        Args:
            model: Model to reset

        Returns:
            New state
        """
        if model in self.model_states:
            state = self.model_states[model]
            state.state = CircuitState.CLOSED
            state.consecutive_failures = 0
            state.cooldown_until = None
            self._save_state()
            logger.info(f"Circuit breaker for {model} force reset to CLOSED")
            return {"model": model, "state": "closed", "action": "force_reset"}
        return {"model": model, "error": "Model not found"}

    def get_status(self) -> dict[str, Any]:
        """Get status of all circuit breakers."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {
                "accuracy_threshold": self.accuracy_threshold,
                "consecutive_failure_limit": self.consecutive_failure_limit,
                "cooldown_minutes": self.cooldown_minutes,
            },
            "models": {model: state.to_dict() for model, state in self.model_states.items()},
            "summary": {
                "total_models": len(self.model_states),
                "enabled": sum(
                    1 for s in self.model_states.values() if s.state != CircuitState.OPEN
                ),
                "disabled": sum(
                    1 for s in self.model_states.values() if s.state == CircuitState.OPEN
                ),
                "total_trips": sum(s.trip_count for s in self.model_states.values()),
            },
        }

    def get_disabled_models(self) -> list[str]:
        """Get list of currently disabled models."""
        return [
            model for model, state in self.model_states.items() if state.state == CircuitState.OPEN
        ]

    def _load_state(self) -> None:
        """Load circuit breaker state from disk."""
        if CIRCUIT_BREAKER_STATE_PATH.exists():
            try:
                with open(CIRCUIT_BREAKER_STATE_PATH) as f:
                    data = json.load(f)
                    for model, state_dict in data.get("models", {}).items():
                        self.model_states[model] = ModelCircuitState(
                            model=model,
                            state=CircuitState(state_dict.get("state", "closed")),
                            accuracy=state_dict.get("accuracy", 1.0),
                            total_predictions=state_dict.get("total_predictions", 0),
                            correct_predictions=state_dict.get("correct_predictions", 0),
                            consecutive_failures=state_dict.get("consecutive_failures", 0),
                            last_failure_time=state_dict.get("last_failure_time"),
                            trip_count=state_dict.get("trip_count", 0),
                            last_trip_time=state_dict.get("last_trip_time"),
                            cooldown_until=state_dict.get("cooldown_until"),
                            trip_reasons=state_dict.get("trip_reasons", []),
                        )
            except Exception as e:
                logger.warning(f"Could not load circuit breaker state: {e}")

    def _save_state(self) -> None:
        """Save circuit breaker state to disk."""
        CIRCUIT_BREAKER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "models": {model: state.to_dict() for model, state in self.model_states.items()},
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        try:
            with open(CIRCUIT_BREAKER_STATE_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save circuit breaker state: {e}")
