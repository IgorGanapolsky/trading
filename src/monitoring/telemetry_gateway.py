"""
Telemetry Gateway - OpenTelemetry-inspired structured logging.
Provides industrial-grade instrumentation for agent spans.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TelemetryGateway:
    """
    Central gateway for all agent spans and trace events.
    """

    _TRACE_LOG = Path("data/monitoring/agent_traces.jsonl")

    def __init__(self):
        self._TRACE_LOG.parent.mkdir(parents=True, exist_ok=True)

    def capture_span(
        self,
        name: str,
        trace_id: str,
        parent_id: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
    ):
        """
        Records a structured span to the trace log.
        """
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "name": name,
            "trace_id": trace_id,
            "parent_id": parent_id,
            "attributes": attributes or {},
        }

        with open(self._TRACE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

        logger.debug(f"Captured span: {name} (trace: {trace_id})")

    def get_traces_for_id(self, trace_id: str) -> list:
        """
        Retrieves all spans for a specific trace.
        """
        if not self._TRACE_LOG.exists():
            return []

        spans = []
        with open(self._TRACE_LOG, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                span = json.loads(line)
                if span["trace_id"] == trace_id:
                    spans.append(span)
        return spans
