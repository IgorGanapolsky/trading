from __future__ import annotations

from unittest.mock import MagicMock

from src.orchestrator.anomaly_monitor import AnomalyMonitor


def test_rejection_spike_triggers_anomaly() -> None:
    telemetry = MagicMock()
    monitor = AnomalyMonitor(
        telemetry,
        window=5,
        min_events=3,
        rejection_threshold=0.8,
    )

    # Two rejects then one pass -> still below threshold
    monitor.track(gate="rl", ticker="SPY", status="reject", metrics=None)
    monitor.track(gate="rl", ticker="QQQ", status="reject", metrics=None)
    assert monitor.track(gate="rl", ticker="IWM", status="pass", metrics=None) is None

    monitor.track(gate="rl", ticker="SPY", status="reject", metrics=None)
    anomaly = monitor.track(gate="rl", ticker="DIA", status="reject", metrics=None)
    assert anomaly is not None
    telemetry.anomaly_event.assert_called_once()


def test_confidence_drop_triggers_anomaly() -> None:
    telemetry = MagicMock()
    monitor = AnomalyMonitor(
        telemetry,
        window=5,
        min_events=4,
        rejection_threshold=1.0,  # disable rejection trigger
        confidence_floor=0.4,
    )

    for i in range(4):
        monitor.track(
            gate="rl",
            ticker=f"T{i}",
            status="pass",
            metrics={"confidence": 0.3},
        )

    anomaly = monitor.track(
        gate="rl",
        ticker="T4",
        status="pass",
        metrics={"confidence": 0.2},
    )
    assert anomaly is not None
    assert anomaly["type"] == "confidence_deterioration"
