"""
Lightweight anomaly monitor for the hybrid funnel gates.

The monitor keeps a rolling window of gate outcomes (pass/reject plus confidence) and
raises anomalies when:
    1. Rejection rate breaches a configurable threshold.
    2. Median confidence falls below a configurable floor.
    3. Gate latency exceeds threshold (Capital One lesson: optimize post-launch).

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

    # Default latency thresholds per gate (ms) - Capital One lesson
    DEFAULT_LATENCY_THRESHOLDS: dict[str, float] = {
        "psychology": 50.0,  # Simple check, should be fast
        "momentum": 500.0,  # Data fetch + indicators
        "debate": 2000.0,  # LLM-based, can be slower
        "rl_filter": 200.0,  # Model inference
        "sentiment": 3000.0,  # LLM-based sentiment
        "introspection": 1000.0,  # LLM introspection
        "risk": 100.0,  # Position sizing calculation
    }

    def __init__(
        self,
        telemetry: OrchestratorTelemetry,
        *,
        window: int = 40,
        min_events: int = 12,
        rejection_threshold: float = 0.75,
        confidence_floor: float = 0.45,
        latency_thresholds: dict[str, float] | None = None,
        lessons_rag: Any = None,
    ) -> None:
        self.telemetry = telemetry
        self.window = window
        self.min_events = min_events
        self.rejection_threshold = rejection_threshold
        self.confidence_floor = confidence_floor
        self.latency_thresholds = latency_thresholds or self.DEFAULT_LATENCY_THRESHOLDS
        self.lessons_rag = lessons_rag  # For automatic lesson creation
        self._history: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self.window)
        )
        self._latency_history: dict[str, deque[float]] = defaultdict(
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
        latency_bucket = self._latency_history[gate]

        # Extract latency from metrics (Capital One lesson)
        latency_ms = (metrics or {}).get("execution_time_ms", 0.0)

        entry = {
            "status": status,
            "confidence": (metrics or {}).get("confidence"),
            "ticker": ticker,
            "latency_ms": latency_ms,
        }
        bucket.append(entry)

        # Track latency separately for percentile calculations
        if latency_ms > 0:
            latency_bucket.append(latency_ms)

        if len(bucket) < self.min_events:
            return None

        rejection_rate = sum(1 for item in bucket if item["status"] == "reject") / len(bucket)
        anomaly: dict[str, Any] | None = None

        # Check 1: Rejection spike
        if rejection_rate >= self.rejection_threshold:
            anomaly = {
                "type": "rejection_spike",
                "rejection_rate": round(rejection_rate, 3),
                "window": len(bucket),
            }
        # Check 2: Confidence deterioration
        else:
            confidences = [c for c in (item.get("confidence") for item in bucket) if c is not None]
            if confidences:
                if median(confidences) < self.confidence_floor:
                    anomaly = {
                        "type": "confidence_deterioration",
                        "median_confidence": round(median(confidences), 3),
                        "window": len(confidences),
                    }

        # Check 3: Latency spike (Capital One lesson)
        if not anomaly and len(latency_bucket) >= self.min_events:
            threshold = self.latency_thresholds.get(gate, 1000.0)
            median_latency = median(latency_bucket)
            # Also check if current latency is way above threshold (3x)
            if median_latency > threshold or (latency_ms > threshold * 3 and latency_ms > 100):
                anomaly = {
                    "type": "latency_spike",
                    "median_latency_ms": round(median_latency, 2),
                    "current_latency_ms": round(latency_ms, 2),
                    "threshold_ms": threshold,
                    "window": len(latency_bucket),
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

    def get_latency_stats(self, gate: str) -> dict[str, float]:
        """Get latency statistics for a gate. Useful for dashboards."""
        latencies = list(self._latency_history.get(gate, []))
        if not latencies:
            return {"p50": 0, "p95": 0, "p99": 0, "avg": 0, "count": 0}

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        return {
            "p50": sorted_latencies[int(n * 0.50)] if n > 0 else 0,
            "p95": sorted_latencies[int(n * 0.95)] if n > 1 else sorted_latencies[-1],
            "p99": sorted_latencies[int(n * 0.99)] if n > 1 else sorted_latencies[-1],
            "avg": sum(latencies) / n,
            "count": n,
            "threshold_ms": self.latency_thresholds.get(gate, 1000.0),
        }

    def _create_lesson_from_anomaly(self, gate: str, ticker: str, anomaly: dict[str, Any]) -> None:
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
                    f"The {gate} gate rejected {anomaly.get('rejection_rate', 0) * 100:.1f}% "
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
            elif anomaly_type == "latency_spike":
                # Capital One lesson: Post-launch latency optimization is critical
                title = f"Gate {gate} latency spike detected"
                median_ms = anomaly.get("median_latency_ms", 0)
                current_ms = anomaly.get("current_latency_ms", 0)
                threshold_ms = anomaly.get("threshold_ms", 1000)
                description = (
                    f"The {gate} gate is running slow. "
                    f"Median latency: {median_ms:.0f}ms (threshold: {threshold_ms:.0f}ms). "
                    f"Current: {current_ms:.0f}ms. Ticker: {ticker}"
                )
                root_cause = (
                    f"High latency at {gate} gate may indicate: "
                    "1) API rate limiting or slowdown, 2) Network issues, "
                    "3) Heavy compute load, 4) Inefficient code paths, "
                    "5) External service degradation"
                )
                prevention = (
                    f"Optimize {gate} gate performance. Consider: "
                    "1) Caching expensive computations, "
                    "2) Parallel data fetching, "
                    "3) Reducing LLM token counts, "
                    "4) Using faster model tiers for non-critical decisions, "
                    "5) Adding circuit breakers for slow external services"
                )
                severity = "medium"
            else:  # confidence_deterioration
                title = f"Gate {gate} confidence deterioration"
                description = (
                    f"Median confidence at {gate} gate dropped to "
                    f"{anomaly.get('median_confidence', 0) * 100:.1f}% "
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

            # Generate lesson ID and format content as markdown
            from datetime import datetime as dt

            today = dt.now().strftime("%Y%m%d_%H%M%S")
            lesson_id = f"ll_anomaly_{gate}_{anomaly_type}_{today}"

            # Build markdown content
            tags_str = ", ".join(["auto-generated", "anomaly", gate, anomaly_type])
            lesson_content = f"""# {title}

**Severity:** {severity.upper()}
**Symbol:** {ticker}
**Category:** anomaly
**Tags:** {tags_str}
**Date:** {dt.now().strftime("%Y-%m-%d %H:%M:%S")}

## Description
{description}

## Root Cause Analysis
{root_cause}

## Prevention Steps
{prevention}

---
*Auto-generated by Anomaly Monitor*
"""
            self.lessons_rag.add_lesson(lesson_id, lesson_content)

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
