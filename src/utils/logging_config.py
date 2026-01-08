"""
Central logging configuration with trace context injection.

Implements "observability lasagna" pattern - connecting logs to traces.
Based on Incident.io's "Stop Building Dashboard Soup" framework (Jan 2026).

Log entries now include trace_id and span_id for direct navigation to
LangSmith traces when debugging issues.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.observability.langsmith_tracer import LangSmithTracer


class TraceContextFilter(logging.Filter):
    """
    Inject trace_id and span_id into log records.

    This is the critical "arrow" connecting logs to traces in the
    observability lasagna. When something fails, you can now jump
    directly from the log entry to the LangSmith trace.

    Usage:
        # Log entry will include trace context:
        # 2026-01-08 10:30:00 - trading - INFO - [trace:abc123/span:def456] - Message

        with tracer.trace("my_operation") as span:
            logger.info("Processing started")  # trace context auto-injected
    """

    def __init__(self, tracer_getter=None, name: str = ""):
        """
        Initialize filter with optional tracer getter function.

        Args:
            tracer_getter: Callable that returns the tracer instance.
                          If None, tries to import get_tracer lazily.
            name: Filter name (passed to parent).
        """
        super().__init__(name)
        self._tracer_getter = tracer_getter
        self._tracer: LangSmithTracer | None = None

    def _get_tracer(self) -> LangSmithTracer | None:
        """Lazily get the tracer instance to avoid circular imports."""
        if self._tracer is not None:
            return self._tracer

        if self._tracer_getter:
            self._tracer = self._tracer_getter()
            return self._tracer

        # Try to import get_tracer lazily
        try:
            from src.observability.langsmith_tracer import get_tracer

            self._tracer = get_tracer()
            return self._tracer
        except ImportError:
            return None
        except Exception:
            return None

    def filter(self, record: logging.LogRecord) -> bool:
        """Add trace_id and span_id to the log record."""
        # Default values when no trace is active
        record.trace_id = "-"
        record.span_id = "-"

        tracer = self._get_tracer()
        if tracer is None:
            return True

        # Get current trace context
        current_trace = getattr(tracer, "_current_trace", None)
        span_stack = getattr(tracer, "_span_stack", [])

        if current_trace:
            # Use short trace_id (first 8 chars) for readability
            record.trace_id = current_trace.trace_id[:8]

        if span_stack:
            # Get the current (innermost) span
            current_span = span_stack[-1]
            record.span_id = current_span.span_id

        return True


def setup_logging(level: str | None = None) -> logging.Logger:
    """
    Configure application-wide logging with trace context.

    Log format now includes trace_id/span_id for debugging:
    - Console: concise format with trace context
    - File: detailed format with trace context + file location

    Args:
        level: Optional log level override (INFO, DEBUG, etc.).

    Returns:
        Root trading logger instance.
    """
    log_level = level or os.getenv("LOG_LEVEL", "INFO").upper()

    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Configure root logger
    logger = logging.getLogger("trading")
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    logger.handlers = []  # clear existing handlers to avoid duplicates

    # Add trace context filter to inject trace_id/span_id
    trace_filter = TraceContextFilter()

    # Console Handler - concise format with trace context
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))
    console_handler.addFilter(trace_filter)
    # Format: timestamp - logger - level - [trace:xxx/span:yyy] - message
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [trace:%(trace_id)s/span:%(span_id)s] - %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File Handler - System Log (INFO+) - detailed format
    system_log_path = os.path.join(log_dir, "trading_system.log")
    file_handler = logging.FileHandler(system_log_path)
    file_handler.setLevel(logging.INFO)
    file_handler.addFilter(trace_filter)
    # Format includes file location for debugging
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - "
        "[trace:%(trace_id)s/span:%(span_id)s] - "
        "[%(filename)s:%(lineno)d] - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # File Handler - Error Log (ERROR+) - detailed format
    error_log_path = os.path.join(log_dir, "trading_errors.log")
    error_handler = logging.FileHandler(error_log_path)
    error_handler.setLevel(logging.ERROR)
    error_handler.addFilter(trace_filter)
    error_handler.setFormatter(file_formatter)
    logger.addHandler(error_handler)

    return logger


def get_trace_context() -> dict[str, str]:
    """
    Get current trace context for external use (e.g., Slack alerts).

    Returns:
        dict with trace_id and span_id (or "-" if no trace active)
    """
    try:
        from src.observability.langsmith_tracer import get_tracer

        tracer = get_tracer()
        current_trace = getattr(tracer, "_current_trace", None)
        span_stack = getattr(tracer, "_span_stack", [])

        return {
            "trace_id": current_trace.trace_id[:8] if current_trace else "-",
            "span_id": span_stack[-1].span_id if span_stack else "-",
            "full_trace_id": current_trace.trace_id if current_trace else None,
        }
    except Exception:
        return {"trace_id": "-", "span_id": "-", "full_trace_id": None}


def get_langsmith_trace_url(trace_id: str | None = None) -> str | None:
    """
    Generate LangSmith trace URL for quick debugging.

    Usage in error handlers:
        url = get_langsmith_trace_url()
        if url:
            send_slack_alert(f"Error occurred! Trace: {url}")

    Args:
        trace_id: Optional trace ID. If None, uses current trace.

    Returns:
        LangSmith URL or None if not available.
    """
    project = os.getenv("LANGCHAIN_PROJECT", "igor-trading-system")

    if trace_id is None:
        ctx = get_trace_context()
        trace_id = ctx.get("full_trace_id")

    if trace_id:
        return (
            f"https://smith.langchain.com/o/igor-trading-system/projects/{project}/runs/{trace_id}"
        )

    return None
