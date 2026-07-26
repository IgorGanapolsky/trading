"""Unit tests for HumanEscalationBridge."""

from __future__ import annotations

import json
from pathlib import Path
from src.resilience.escalation_bridge import HumanEscalationBridge, get_escalation_bridge


def test_failure_counter_and_success_reset() -> None:
    bridge = HumanEscalationBridge(failure_threshold=3)
    assert bridge.get_consecutive_failure_count() == 0

    bridge.record_failure("test_gate", "Failure 1")
    assert bridge.get_consecutive_failure_count() == 1

    bridge.record_failure("test_gate", "Failure 2")
    assert bridge.get_consecutive_failure_count() == 2

    # Success resets counter
    bridge.record_success()
    assert bridge.get_consecutive_failure_count() == 0


def test_escalation_trigger_at_threshold(tmp_path: Path) -> None:
    bridge = HumanEscalationBridge(failure_threshold=3, state_dir=tmp_path)

    bridge.record_failure("risk_monitor", "Error 1")
    bridge.record_failure("risk_monitor", "Error 2")
    package = bridge.record_failure("risk_monitor", "Error 3")

    assert package is not None
    assert package.consecutive_failures == 3
    assert package.status == "pending_operator_review"
    assert len(package.reasons) == 3

    # State file written
    saved_files = list(tmp_path.glob("esc_*.json"))
    assert len(saved_files) == 1
    data = json.loads(saved_files[0].read_text(encoding="utf-8"))
    assert data["escalation_id"] == package.escalation_id


def test_singleton_accessor() -> None:
    b1 = get_escalation_bridge()
    b2 = get_escalation_bridge()
    assert b1 is b2
