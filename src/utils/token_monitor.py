"""
Token Usage Monitor for LLM Context Management

Tracks token consumption across all LLM calls to:
1. Monitor actual usage vs allocated limits
2. Alert when approaching context thresholds
3. Provide insights for optimization
4. Detect context growth patterns

Based on 2025-2026 best practices for context engineering.
Reference: Anthropic's "Effective Context Engineering for AI Agents"

Example:
    >>> from src.utils.token_monitor import get_token_monitor
    >>> monitor = get_token_monitor()
    >>> monitor.record_usage("execution_agent", 1500, 500)
    >>> print(monitor.get_summary())
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TokenUsageEntry:
    """Single token usage record."""

    timestamp: datetime
    agent_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str = "unknown"
    context_window: int = 200000  # Default Claude context window


@dataclass
class UsageStats:
    """Aggregated usage statistics."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    call_count: int = 0
    avg_input_tokens: float = 0.0
    avg_output_tokens: float = 0.0
    max_input_tokens: int = 0
    max_output_tokens: int = 0
    tokens_by_agent: dict[str, int] = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)


class TokenUsageMonitor:
    """
    Monitors LLM token usage across the trading system.

    Features:
    - Tracks input/output tokens per call
    - Aggregates by agent, session, and time period
    - Alerts when usage exceeds thresholds
    - Persists data for analysis

    Thread-safe implementation for concurrent agent access.
    """

    # Alert thresholds
    SINGLE_CALL_THRESHOLD = 50000  # Alert if single call uses > 50K tokens
    SESSION_THRESHOLD = 500000  # Alert if session exceeds 500K total
    DAILY_THRESHOLD = 2000000  # Alert if daily usage exceeds 2M tokens

    # Context window sizes by model
    CONTEXT_WINDOWS = {
        "claude-3-opus-20240229": 200000,
        "claude-3-sonnet-20240229": 200000,
        "claude-3-haiku-20240307": 200000,
        "claude-3-5-sonnet-20241022": 200000,
        "claude-opus-4-5-20251101": 200000,
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
    }

    def __init__(self, data_dir: str | Path | None = None):
        """
        Initialize the token monitor.

        Args:
            data_dir: Directory for persisting usage data
        """
        self.data_dir = Path(data_dir) if data_dir else Path("data/token_usage")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._entries: list[TokenUsageEntry] = []
        self._session_start = datetime.now()
        self._lock = threading.Lock()

        # Load existing data
        self._load_existing_data()

        logger.info(
            f"TokenUsageMonitor initialized. Session start: {self._session_start.isoformat()}"
        )

    def record_usage(
        self,
        agent_name: str,
        input_tokens: int,
        output_tokens: int,
        model: str = "unknown",
    ) -> list[str]:
        """
        Record a single LLM call's token usage.

        Args:
            agent_name: Name of the agent making the call
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name used

        Returns:
            List of alert messages (empty if no alerts)
        """
        total = input_tokens + output_tokens
        alerts = []

        entry = TokenUsageEntry(
            timestamp=datetime.now(),
            agent_name=agent_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            model=model,
            context_window=self.CONTEXT_WINDOWS.get(model, 200000),
        )

        with self._lock:
            self._entries.append(entry)

            # Check thresholds
            if total > self.SINGLE_CALL_THRESHOLD:
                alert = f"HIGH_USAGE: {agent_name} used {total:,} tokens in single call"
                alerts.append(alert)
                logger.warning(alert)

            session_total = self._get_session_total_unsafe()
            if session_total > self.SESSION_THRESHOLD:
                alert = f"SESSION_LIMIT: Total session usage {session_total:,} exceeds threshold"
                if alert not in [e for e in self._get_recent_alerts_unsafe()]:
                    alerts.append(alert)
                    logger.warning(alert)

            # Check context window utilization
            utilization = input_tokens / entry.context_window
            if utilization > 0.75:
                alert = f"CONTEXT_WARNING: {agent_name} at {utilization:.0%} of context window"
                alerts.append(alert)
                logger.warning(alert)

        # Log the usage
        logger.debug(
            f"Token usage: {agent_name} | in={input_tokens:,} out={output_tokens:,} | "
            f"model={model}"
        )

        return alerts

    def get_session_stats(self) -> UsageStats:
        """Get statistics for the current session."""
        with self._lock:
            return self._calculate_stats_unsafe(self._session_start)

    def get_daily_stats(self) -> UsageStats:
        """Get statistics for the current day."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        with self._lock:
            return self._calculate_stats_unsafe(today_start)

    def get_agent_stats(self, agent_name: str) -> UsageStats:
        """Get statistics for a specific agent."""
        with self._lock:
            relevant_entries = [e for e in self._entries if e.agent_name == agent_name]
            return self._calculate_stats_from_entries(relevant_entries)

    def get_summary(self) -> dict[str, Any]:
        """Get a comprehensive usage summary."""
        session_stats = self.get_session_stats()
        daily_stats = self.get_daily_stats()

        return {
            "timestamp": datetime.now().isoformat(),
            "session_start": self._session_start.isoformat(),
            "session": {
                "total_tokens": session_stats.total_tokens,
                "call_count": session_stats.call_count,
                "avg_tokens_per_call": round(
                    session_stats.total_tokens / max(1, session_stats.call_count)
                ),
                "tokens_by_agent": session_stats.tokens_by_agent,
                "alerts": session_stats.alerts,
            },
            "daily": {
                "total_tokens": daily_stats.total_tokens,
                "call_count": daily_stats.call_count,
                "threshold_pct": round(
                    100 * daily_stats.total_tokens / self.DAILY_THRESHOLD, 1
                ),
            },
            "thresholds": {
                "single_call": self.SINGLE_CALL_THRESHOLD,
                "session": self.SESSION_THRESHOLD,
                "daily": self.DAILY_THRESHOLD,
            },
            "recommendations": self._get_recommendations(session_stats),
        }

    def save_report(self) -> Path:
        """Save a detailed usage report to file."""
        report = self.get_summary()
        report["entries"] = [
            {
                "timestamp": e.timestamp.isoformat(),
                "agent": e.agent_name,
                "input": e.input_tokens,
                "output": e.output_tokens,
                "model": e.model,
            }
            for e in self._entries[-100:]  # Last 100 entries
        ]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.data_dir / f"token_report_{timestamp}.json"

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Token usage report saved to {report_path}")
        return report_path

    def _calculate_stats_unsafe(self, since: datetime) -> UsageStats:
        """Calculate stats since a given time (must hold lock)."""
        relevant_entries = [e for e in self._entries if e.timestamp >= since]
        return self._calculate_stats_from_entries(relevant_entries)

    def _calculate_stats_from_entries(
        self, entries: list[TokenUsageEntry]
    ) -> UsageStats:
        """Calculate stats from a list of entries."""
        if not entries:
            return UsageStats()

        total_input = sum(e.input_tokens for e in entries)
        total_output = sum(e.output_tokens for e in entries)
        total = total_input + total_output
        count = len(entries)

        # Group by agent
        by_agent: dict[str, int] = {}
        for e in entries:
            by_agent[e.agent_name] = by_agent.get(e.agent_name, 0) + e.total_tokens

        # Find max values
        max_input = max(e.input_tokens for e in entries)
        max_output = max(e.output_tokens for e in entries)

        # Collect alerts
        alerts = []
        if total > self.SESSION_THRESHOLD:
            alerts.append(f"Session total ({total:,}) exceeds threshold")

        return UsageStats(
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total,
            call_count=count,
            avg_input_tokens=total_input / count,
            avg_output_tokens=total_output / count,
            max_input_tokens=max_input,
            max_output_tokens=max_output,
            tokens_by_agent=by_agent,
            alerts=alerts,
        )

    def _get_session_total_unsafe(self) -> int:
        """Get session total tokens (must hold lock)."""
        return sum(
            e.total_tokens
            for e in self._entries
            if e.timestamp >= self._session_start
        )

    def _get_recent_alerts_unsafe(self) -> list[str]:
        """Get recent alerts (must hold lock)."""
        recent = [e for e in self._entries if e.timestamp >= self._session_start]
        # This is a simplified version - in production, alerts would be stored separately
        return []

    def _get_recommendations(self, stats: UsageStats) -> list[str]:
        """Generate optimization recommendations based on usage patterns."""
        recommendations = []

        if stats.avg_input_tokens > 10000:
            recommendations.append(
                "Consider summarizing context before LLM calls - avg input is high"
            )

        if stats.max_input_tokens > 50000:
            recommendations.append(
                "Some calls use >50K input tokens - review for context optimization"
            )

        # Check for uneven agent distribution
        if stats.tokens_by_agent:
            max_agent = max(stats.tokens_by_agent.values())
            total = sum(stats.tokens_by_agent.values())
            if max_agent > 0.7 * total:
                heavy_agent = max(stats.tokens_by_agent, key=stats.tokens_by_agent.get)
                recommendations.append(
                    f"Agent '{heavy_agent}' uses >70% of tokens - investigate"
                )

        if not recommendations:
            recommendations.append("Token usage looks healthy - no optimizations needed")

        return recommendations

    def _load_existing_data(self) -> None:
        """Load existing usage data from disk."""
        today = datetime.now().strftime("%Y%m%d")
        daily_file = self.data_dir / f"daily_{today}.json"

        if daily_file.exists():
            try:
                with open(daily_file) as f:
                    data = json.load(f)
                    for entry in data.get("entries", []):
                        self._entries.append(
                            TokenUsageEntry(
                                timestamp=datetime.fromisoformat(entry["timestamp"]),
                                agent_name=entry["agent"],
                                input_tokens=entry["input"],
                                output_tokens=entry["output"],
                                total_tokens=entry["input"] + entry["output"],
                                model=entry.get("model", "unknown"),
                            )
                        )
                logger.info(f"Loaded {len(self._entries)} entries from {daily_file}")
            except Exception as e:
                logger.warning(f"Could not load existing data: {e}")

    def persist(self) -> None:
        """Persist current data to disk."""
        today = datetime.now().strftime("%Y%m%d")
        daily_file = self.data_dir / f"daily_{today}.json"

        data = {
            "date": today,
            "entries": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "agent": e.agent_name,
                    "input": e.input_tokens,
                    "output": e.output_tokens,
                    "model": e.model,
                }
                for e in self._entries
                if e.timestamp.strftime("%Y%m%d") == today
            ],
        }

        with open(daily_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.debug(f"Persisted token usage to {daily_file}")


# Singleton instance
_monitor: TokenUsageMonitor | None = None
_monitor_lock = threading.Lock()


def get_token_monitor(data_dir: str | Path | None = None) -> TokenUsageMonitor:
    """
    Get the singleton TokenUsageMonitor instance.

    Args:
        data_dir: Optional directory for data storage

    Returns:
        TokenUsageMonitor singleton instance
    """
    global _monitor

    if _monitor is None:
        with _monitor_lock:
            if _monitor is None:
                _monitor = TokenUsageMonitor(data_dir)

    return _monitor


def record_llm_usage(
    agent_name: str,
    input_tokens: int,
    output_tokens: int,
    model: str = "unknown",
) -> list[str]:
    """
    Convenience function to record LLM usage.

    Args:
        agent_name: Name of the calling agent
        input_tokens: Input token count
        output_tokens: Output token count
        model: Model name

    Returns:
        List of any triggered alerts
    """
    monitor = get_token_monitor()
    return monitor.record_usage(agent_name, input_tokens, output_tokens, model)
