from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.schemas.events import AuditEvent

logger = logging.getLogger(__name__)


class AuditGraph:
    """
    Unified event graph for trade integrity.
    Links signals, decisions, and executions end-to-end.
    """

    def __init__(self, data_dir: str = "data/audit"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.data_dir / "graph_index.json"
        self._load_index()

    def _load_index(self):
        if self.index_file.exists():
            try:
                with open(self.index_file) as f:
                    self.index = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load audit index: {e}")
                self.index = {}
        else:
            self.index = {}

    def _save_index(self):
        try:
            with open(self.index_file, "w") as f:
                json.dump(self.index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save audit index: {e}")

    def emit(self, event: AuditEvent):
        """Persist an event and update the graph index."""
        event_file = self.data_dir / f"{event.event_id}.json"

        # Store the event data
        event_data = {
            "event_id": event.event_id,
            "trace_id": event.trace_id,
            "timestamp": event.timestamp,
            "event_type": event.event_type.value,
            "agent_id": event.agent_id,
            "data": event.data,
            "metadata": event.metadata,
        }

        with open(event_file, "w") as f:
            json.dump(event_data, f, indent=2)

        # Update trace index
        if event.trace_id not in self.index:
            self.index[event.trace_id] = []

        self.index[event.trace_id].append(event.event_id)
        self._save_index()

        logger.info(
            f"Audit event emitted: {event.event_type.value} | {event.event_id} | trace={event.trace_id}"
        )

    def get_trace(self, trace_id: str) -> list[dict[str, Any]]:
        """Retrieve all events linked to a specific trace_id."""
        event_ids = self.index.get(trace_id, [])
        events = []
        for eid in event_ids:
            event_file = self.data_dir / f"{eid}.json"
            if event_file.exists():
                with open(event_file) as f:
                    events.append(json.load(f))

        # Sort by timestamp
        return sorted(events, key=lambda x: x["timestamp"])

    def find_mismatches(self) -> list[dict[str, Any]]:
        """Find traces that lack key events (e.g., signal without execution)."""
        mismatches = []
        for trace_id, _event_ids in self.index.items():
            trace = self.get_trace(trace_id)
            types = {e["event_type"] for e in trace}

            # Simple mismatch detection
            if "decision" in types and "execution" not in types:
                mismatches.append(
                    {"trace_id": trace_id, "issue": "DECISION_WITHOUT_EXECUTION", "events": types}
                )
        return mismatches
