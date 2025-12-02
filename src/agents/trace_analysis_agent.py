import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class TraceAnalysisAgent(BaseAgent):
    """
    Trace Analysis Agent: Autonomous Audit & Explainability Monitor.

    Responsibilities:
    - Monitor data/audit_traces/ for new trace files
    - Analyze traces for anomalies, errors, and latency bottlenecks
    - Generate "Why" reports for complex decisions
    - Alert on suspicious agent behavior
    """

    def __init__(self):
        super().__init__(
            name="TraceAnalysisAgent", role="Audit trail analysis and anomaly detection"
        )
        self.trace_dir = Path("data/audit_traces")
        self.trace_dir.mkdir(parents=True, exist_ok=True)

    def analyze(self, data: dict[str, Any] = None) -> dict[str, Any]:
        """
        Analyze recent audit traces.

        Args:
            data: Optional filter criteria (e.g., {'since': '2025-11-25'})

        Returns:
            Analysis report
        """
        logger.info("🔍 Starting Trace Analysis...")

        # 1. Load recent traces
        traces = self._load_recent_traces(limit=10)
        if not traces:
            return {"action": "NO_ACTION", "message": "No traces found to analyze"}

        # 2. Analyze for anomalies
        anomalies = []
        latency_stats = []

        for trace in traces:
            analysis = self._analyze_single_trace(trace)
            if analysis["anomalies"]:
                anomalies.extend(analysis["anomalies"])
            latency_stats.append(analysis["latency"])

        # 3. Generate Report using LLM
        report = self._generate_llm_report(anomalies, latency_stats)

        # 4. Log findings
        self.log_decision(
            {
                "action": "REPORT_GENERATED",
                "anomalies_found": len(anomalies),
                "report_summary": report.get("summary", ""),
            }
        )

        return {
            "action": "REPORT_GENERATED",
            "anomalies": anomalies,
            "latency_stats": latency_stats,
            "llm_report": report,
        }

    def _load_recent_traces(self, limit: int = 10) -> list[dict]:
        """Load the most recent JSON trace files."""
        files = sorted(
            self.trace_dir.glob("trace_*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        traces = []
        for f in files[:limit]:
            try:
                with open(f) as fd:
                    traces.append(json.load(fd))
            except Exception as e:
                logger.error(f"Failed to load trace {f}: {e}")
        return traces

    def _analyze_single_trace(self, trace: dict) -> dict:
        """Analyze a single trace for issues."""
        anomalies = []
        total_duration = trace.get("duration_ms", 0)
        trace_id = trace.get("trace_id", "unknown")

        # Check 1: High Latency
        if total_duration > 5000:  # 5 seconds
            anomalies.append(
                {
                    "type": "HIGH_LATENCY",
                    "trace_id": trace_id,
                    "details": f"Total duration {total_duration:.2f}ms exceeds threshold",
                }
            )

        # Check 2: Errors in steps
        for step in trace.get("steps", []):
            if (
                "error" in str(step.get("action", "")).lower()
                or "error" in str(step.get("reasoning", "")).lower()
            ):
                anomalies.append(
                    {
                        "type": "STEP_ERROR",
                        "trace_id": trace_id,
                        "details": f"Error in step: {step.get('action')}",
                    }
                )

        # Check 3: Final Decision Validity
        final_decision = trace.get("final_decision")
        if not final_decision or (isinstance(final_decision, dict) and "error" in final_decision):
            anomalies.append(
                {
                    "type": "INVALID_DECISION",
                    "trace_id": trace_id,
                    "details": "Final decision missing or indicates error",
                }
            )

        return {"trace_id": trace_id, "latency": total_duration, "anomalies": anomalies}

    def _generate_llm_report(self, anomalies: list[dict], latency_stats: list[float]) -> dict:
        """Use Claude to summarize findings."""
        if not anomalies and not latency_stats:
            return {"summary": "No activity to report."}

        avg_latency = sum(latency_stats) / len(latency_stats) if latency_stats else 0

        prompt = f"""You are the Trace Analysis Agent. Review the following system performance data:

        AVG LATENCY: {avg_latency:.2f} ms
        TOTAL TRACES ANALYZED: {len(latency_stats)}
        ANOMALIES FOUND: {len(anomalies)}

        ANOMALY DETAILS:
        {json.dumps(anomalies[:5], indent=2)}

        Task:
        1. Summarize system health.
        2. Identify any concerning patterns (e.g., repeated errors, latency spikes).
        3. Recommend fixes if needed.
        """

        response = self.reason_with_llm(prompt)
        return {
            "summary": response.get("reasoning", "Analysis complete."),
            "timestamp": datetime.now().isoformat(),
        }
