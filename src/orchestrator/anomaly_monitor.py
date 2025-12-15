"""
Lightweight anomaly monitor for the hybrid funnel gates.

The monitor keeps a rolling window of gate outcomes (pass/reject plus confidence) and
raises anomalies when:
    1. Rejection rate breaches a configurable threshold.
    2. Median confidence falls below a configurable floor.

When an anomaly is detected the monitor notifies telemetry so the dashboard, CI, and
incident workflows can react (halt trading, escalate, etc.).
"""

from __future__ import annotations

from collections import defaultdict, deque
from statistics import median
from typing import Any

from src.orchestrator.telemetry import OrchestratorTelemetry


class AnomalyMonitor:
    """Tracks gate outcomes and emits structured anomaly events.

    Dec 2025: Enhanced with automatic lesson creation feedback loop.
    When anomalies are detected, lessons are automatically created in RAG.
    """

    def __init__(
        self,
        telemetry: OrchestratorTelemetry,
        *,
        window: int = 40,
        min_events: int = 12,
        rejection_threshold: float = 0.75,
        confidence_floor: float = 0.45,
        lessons_rag: Any = None,
    ) -> None:
        self.telemetry = telemetry
        self.window = window
        self.min_events = min_events
        self.rejection_threshold = rejection_threshold
        self.confidence_floor = confidence_floor
        self.lessons_rag = lessons_rag  # For automatic lesson creation
        self._history: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self.window)
        )
        self._lesson_cooldown: dict[str, float] = {}  # Prevent lesson spam

    def track(
        self,
        *,
        gate: str,
        ticker: str,
        status: str,
        metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        bucket = self._history[gate]
        entry = {
            "status": status,
            "confidence": (metrics or {}).get("confidence"),
            "ticker": ticker,
        }
        bucket.append(entry)

        if len(bucket) < self.min_events:
            return None

        rejection_rate = sum(1 for item in bucket if item["status"] == "reject") / len(bucket)
        anomaly: dict[str, Any] | None = None

        if rejection_rate >= self.rejection_threshold:
            anomaly = {
                "type": "rejection_spike",
                "rejection_rate": round(rejection_rate, 3),
                "window": len(bucket),
            }
        else:
            confidences = [c for c in (item.get("confidence") for item in bucket) if c is not None]
            if confidences:
                if median(confidences) < self.confidence_floor:
                    anomaly = {
                        "type": "confidence_deterioration",
                        "median_confidence": round(median(confidences), 3),
                        "window": len(confidences),
                    }

        if anomaly:
            metrics_payload = {**anomaly, "gate": gate}
            self.telemetry.anomaly_event(
                ticker=ticker,
                gate=gate,
                reason=anomaly["type"],
                metrics=metrics_payload,
            )
            # Auto-create lesson from anomaly (feedback loop)
            self._create_lesson_from_anomaly(gate, ticker, anomaly)
            return anomaly

        return None

    def _create_lesson_from_anomaly(
        self, gate: str, ticker: str, anomaly: dict[str, Any]
    ) -> None:
        """
        Automatically create a lesson learned entry when an anomaly is detected.

        This creates the feedback loop: anomaly → lesson → RAG → future trades.
        Includes cooldown to prevent lesson spam for repeated anomalies.
        """
        import time

        if not self.lessons_rag:
            return

        # Cooldown: Don't create lessons for same gate more than once per hour
        cooldown_key = f"{gate}_{anomaly['type']}"
        now = time.time()
        last_lesson = self._lesson_cooldown.get(cooldown_key, 0)
        if now - last_lesson < 3600:  # 1 hour cooldown
            return

        try:
            anomaly_type = anomaly.get("type", "unknown")
            if anomaly_type == "rejection_spike":
                title = f"Gate {gate} rejection spike detected"
                description = (
                    f"The {gate} gate rejected {anomaly.get('rejection_rate', 0)*100:.1f}% "
                    f"of trades over a {anomaly.get('window', 0)} trade window. "
                    f"Last ticker affected: {ticker}"
                )
                root_cause = (
                    f"High rejection rate at {gate} gate may indicate: "
                    "1) Overly aggressive filters, 2) Market regime change, "
                    "3) Data quality issues, or 4) Strategy misalignment"
                )
                prevention = (
                    f"Review {gate} gate thresholds. Consider: "
                    "1) Loosening filters during R&D phase, "
                    "2) Checking for market regime changes, "
                    "3) Validating data pipeline quality"
                )
                severity = "high"
            else:  # confidence_deterioration
                title = f"Gate {gate} confidence deterioration"
                description = (
                    f"Median confidence at {gate} gate dropped to "
                    f"{anomaly.get('median_confidence', 0)*100:.1f}% "
                    f"over {anomaly.get('window', 0)} trades. Last ticker: {ticker}"
                )
                root_cause = (
                    "Low confidence may indicate: "
                    "1) Model degradation, 2) Market conditions outside training distribution, "
                    "3) Feature drift, or 4) Insufficient training data"
                )
                prevention = (
                    "Consider: 1) Retraining the model, "
                    "2) Adding more diverse training data, "
                    "3) Implementing online learning, "
                    "4) Reducing position sizes during low confidence periods"
                )
                severity = "medium"

            lesson_id = self.lessons_rag.add_lesson(
                category="anomaly",
                title=title,
                description=description,
                root_cause=root_cause,
                prevention=prevention,
                tags=["auto-generated", "anomaly", gate, anomaly_type],
                severity=severity,
                symbol=ticker,
            )

            self._lesson_cooldown[cooldown_key] = now
            self.telemetry.record(
                event_type="lesson.auto_created",
                ticker=ticker,
                status="created",
                payload={
                    "lesson_id": lesson_id,
                    "gate": gate,
                    "anomaly_type": anomaly_type,
                },
            )

        except Exception as e:
            # Non-fatal - don't break trading for lesson creation failures
            import logging
            logging.getLogger(__name__).debug(f"Failed to create lesson from anomaly: {e}")
