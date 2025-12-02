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
    """Tracks gate outcomes and emits structured anomaly events."""

    def __init__(
        self,
        telemetry: OrchestratorTelemetry,
        *,
        window: int = 40,
        min_events: int = 12,
        rejection_threshold: float = 0.75,
        confidence_floor: float = 0.45,
    ) -> None:
        self.telemetry = telemetry
        self.window = window
        self.min_events = min_events
        self.rejection_threshold = rejection_threshold
        self.confidence_floor = confidence_floor
        self._history: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self.window)
        )

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
            return anomaly

        return None
