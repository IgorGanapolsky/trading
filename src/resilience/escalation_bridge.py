"""
Circuit Breaker Human Escalation Bridge.

Monitors failure counts across safety gates, API calls, and validation passes.
When 3 consecutive failures occur, generates a structured diagnostic package
and triggers human escalation via AskUserQuestion or state file notification.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class FailureEvent:
    source: str
    reason: str
    timestamp: float
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class EscalationPackage:
    escalation_id: str
    consecutive_failures: int
    source: str
    reasons: list[str]
    created_at: float
    status: str  # "pending_operator_review", "resolved", "bypassed"


class HumanEscalationBridge:
    """Monitors consecutive failures and manages operator escalation packages."""

    def __init__(self, failure_threshold: int = 3, state_dir: Optional[Path] = None) -> None:
        self.failure_threshold = failure_threshold
        self.state_dir = state_dir or (Path.cwd() / ".claude" / "memory" / "escalations")
        self._consecutive_failures: list[FailureEvent] = []

    def record_failure(
        self, source: str, reason: str, context: Optional[dict[str, Any]] = None
    ) -> Optional[EscalationPackage]:
        """
        Records a failure event.

        If consecutive failures reach the threshold (e.g. 3), builds and returns an EscalationPackage.
        """
        event = FailureEvent(
            source=source,
            reason=reason,
            timestamp=time.time(),
            context=context or {},
        )
        self._consecutive_failures.append(event)

        if len(self._consecutive_failures) >= self.failure_threshold:
            package = self._trigger_escalation()
            return package
        return None

    def record_success(self) -> None:
        """Resets the consecutive failure count upon successful execution."""
        self._consecutive_failures.clear()

    def get_consecutive_failure_count(self) -> int:
        return len(self._consecutive_failures)

    def _trigger_escalation(self) -> EscalationPackage:
        escalation_id = f"esc_{int(time.time())}_{len(self._consecutive_failures)}"
        reasons = [f.reason for f in self._consecutive_failures]
        source = self._consecutive_failures[-1].source if self._consecutive_failures else "system"

        package = EscalationPackage(
            escalation_id=escalation_id,
            consecutive_failures=len(self._consecutive_failures),
            source=source,
            reasons=reasons,
            created_at=time.time(),
            status="pending_operator_review",
        )

        self._save_escalation_package(package)
        self._consecutive_failures.clear()
        return package

    def _save_escalation_package(self, package: EscalationPackage) -> None:
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            file_path = self.state_dir / f"{package.escalation_id}.json"
            file_path.write_text(json.dumps(asdict(package), indent=2), encoding="utf-8")
        except OSError:
            pass


_GLOBAL_ESCALATION_BRIDGE = HumanEscalationBridge()


def get_escalation_bridge() -> HumanEscalationBridge:
    return _GLOBAL_ESCALATION_BRIDGE
