import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ExplainabilityTracer:
    """
    Provides deep 'why' tracing for all agent decisions.
    Generates structured audit logs for compliance and debugging.
    """

    def __init__(self, trace_dir: str = "data/audit_traces"):
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.current_trace_id = None
        self.trace_stack = []

    def start_trace(self, context: str) -> str:
        """Start a new decision trace."""
        trace_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.current_trace_id = trace_id

        trace_entry = {
            "trace_id": trace_id,
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "steps": [],
            "final_decision": None,
        }
        self.trace_stack.append(trace_entry)
        return trace_id

    def log_step(self, agent: str, action: str, reasoning: str, data: dict | None = None):
        """Log a specific step/thought in the decision process."""
        if not self.trace_stack:
            return

        step = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "action": action,
            "reasoning": reasoning,
            "data_snapshot": data,
        }
        self.trace_stack[-1]["steps"].append(step)
        logger.info(f"🔍 Trace [{agent}]: {action} - {reasoning}")

    def end_trace(self, final_decision: Any):
        """Complete the trace and save to disk."""
        if not self.trace_stack:
            return

        trace_data = self.trace_stack.pop()
        trace_data["final_decision"] = final_decision
        trace_data["duration_ms"] = (
            datetime.now() - datetime.fromisoformat(trace_data["timestamp"])
        ).total_seconds() * 1000

        # Save to file
        filename = self.trace_dir / f"trace_{trace_data['trace_id']}.json"
        with open(filename, "w") as f:
            json.dump(trace_data, f, indent=2, default=str)

        logger.info(f"📝 Decision trace saved: {filename}")
        return trace_data["trace_id"]


# Global instance
tracer = ExplainabilityTracer()
