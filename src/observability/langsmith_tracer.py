"""
LangSmith Integration for Deep Agent Observability.

Based on LangChain's "Observing & Evaluating Deep Agents" webinar (Dec 2025).
Provides real-time tracing, cost tracking, and evaluation for trading decisions.

Key Features:
- Trace every LLM call and decision chain
- Track costs per decision (fits $100/mo budget)
- Create evaluation datasets for A/B testing
- Export metrics for dashboard visualization

Usage:
    from src.observability import traceable_decision, get_tracer

    @traceable_decision(name="trade_signal")
    async def generate_signal(symbol: str) -> Signal:
        # All nested LLM calls auto-traced
        ...

    # Or use context manager
    tracer = get_tracer()
    with tracer.trace("market_analysis") as span:
        span.add_metadata({"symbol": "SPY"})
        result = await analyze_market()
        span.add_output(result)
"""

from __future__ import annotations

import functools
import json
import logging
import os
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

# Type variable for generic decorators
F = TypeVar("F", bound=Callable[..., Any])


class TraceType(Enum):
    """Types of traces for categorization."""

    DECISION = "decision"  # Trade decisions (buy/sell/hold)
    SIGNAL = "signal"  # Signal generation
    TRADE = "trade"  # Trade execution
    ANALYSIS = "analysis"  # Market analysis
    RISK = "risk"  # Risk calculations
    SENTIMENT = "sentiment"  # Sentiment analysis
    RL = "rl"  # RL model inference
    VERIFICATION = "verification"  # Pre-trade verification
    REFLECTION = "reflection"  # Post-trade reflection


@dataclass
class CostMetrics:
    """Track costs per trace for budget management."""

    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    estimated_cost_usd: float = 0.0

    # Cost per 1K tokens (OpenRouter pricing Dec 2025)
    PRICING = {
        "gpt-4o": {"input": 0.0025, "output": 0.01},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
        "deepseek-chat": {"input": 0.00014, "output": 0.00028},
        # Kimi K2 - Budget-friendly 1T param MoE model (Dec 2025)
        # moonshotai/kimi-k2-0905: 256K context, excellent for agentic tasks
        "kimi-k2": {"input": 0.00039, "output": 0.0019},
        "kimi-k2-0905": {"input": 0.00039, "output": 0.0019},
        "kimi-k2-thinking": {"input": 0.00045, "output": 0.00235},
        "default": {"input": 0.001, "output": 0.002},
    }

    def calculate_cost(self) -> float:
        """Calculate estimated cost based on model and tokens."""
        pricing = self.PRICING.get(self.model, self.PRICING["default"])
        input_cost = (self.input_tokens / 1000) * pricing["input"]
        output_cost = (self.output_tokens / 1000) * pricing["output"]
        self.estimated_cost_usd = input_cost + output_cost
        return self.estimated_cost_usd


@dataclass
class TraceSpan:
    """A single span in a trace - represents one operation."""

    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    trace_type: TraceType = TraceType.ANALYSIS
    parent_id: Optional[str] = None
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0

    # Input/Output
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Cost tracking
    cost: CostMetrics = field(default_factory=CostMetrics)

    # Status
    status: str = "running"  # running, success, error
    error: Optional[str] = None

    def complete(self, outputs: Optional[dict[str, Any]] = None, error: Optional[str] = None):
        """Mark span as complete."""
        self.end_time = datetime.now(timezone.utc)
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

        if outputs:
            self.outputs.update(outputs)

        if error:
            self.status = "error"
            self.error = error
        else:
            self.status = "success"

    def add_metadata(self, metadata: dict[str, Any]):
        """Add metadata to the span."""
        self.metadata.update(metadata)

    def add_output(self, key: str, value: Any):
        """Add an output value."""
        self.outputs[key] = value

    def set_cost(self, input_tokens: int, output_tokens: int, model: str):
        """Set cost metrics for the span."""
        self.cost = CostMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
        )
        self.cost.calculate_cost()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "span_id": self.span_id,
            "name": self.name,
            "trace_type": self.trace_type.value,
            "parent_id": self.parent_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "metadata": self.metadata,
            "cost": asdict(self.cost),
            "status": self.status,
            "error": self.error,
        }


@dataclass
class Trace:
    """A complete trace - collection of spans for one operation."""

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    spans: list[TraceSpan] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None

    # Aggregated metrics
    total_duration_ms: float = 0.0
    total_cost_usd: float = 0.0
    total_tokens: int = 0

    # Context
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    def add_span(self, span: TraceSpan):
        """Add a span to the trace."""
        self.spans.append(span)

    def complete(self):
        """Mark trace as complete and calculate aggregates."""
        self.end_time = datetime.now(timezone.utc)
        self.total_duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

        # Aggregate costs and tokens
        for span in self.spans:
            self.total_cost_usd += span.cost.estimated_cost_usd
            self.total_tokens += span.cost.input_tokens + span.cost.output_tokens

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "name": self.name,
            "spans": [span.to_dict() for span in self.spans],
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration_ms": self.total_duration_ms,
            "total_cost_usd": self.total_cost_usd,
            "total_tokens": self.total_tokens,
            "session_id": self.session_id,
            "tags": self.tags,
        }


class EvaluationDataset:
    """Manage evaluation datasets for A/B testing and prompt optimization."""

    def __init__(self, name: str, storage_path: Path):
        self.name = name
        self.storage_path = storage_path / f"eval_{name}.jsonl"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def add_example(
        self,
        inputs: dict[str, Any],
        expected_output: Any,
        actual_output: Any,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """Add an evaluation example."""
        example = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "inputs": inputs,
            "expected_output": expected_output,
            "actual_output": actual_output,
            "match": expected_output == actual_output,
            "metadata": metadata or {},
        }

        with open(self.storage_path, "a") as f:
            f.write(json.dumps(example) + "\n")

    def get_accuracy(self) -> float:
        """Calculate accuracy across all examples."""
        if not self.storage_path.exists():
            return 0.0

        matches = 0
        total = 0

        with open(self.storage_path) as f:
            for line in f:
                example = json.loads(line)
                total += 1
                if example.get("match"):
                    matches += 1

        return matches / total if total > 0 else 0.0

    def get_examples(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent examples from the dataset."""
        if not self.storage_path.exists():
            return []

        examples = []
        with open(self.storage_path) as f:
            for line in f:
                examples.append(json.loads(line))
                if len(examples) >= limit:
                    break

        return examples


class LangSmithTracer:
    """
    Main tracer class for Deep Agent observability.

    Provides LangSmith-compatible tracing with local fallback.
    Integrates with LangSmith API when LANGCHAIN_API_KEY is set.
    """

    _instance: Optional[LangSmithTracer] = None

    def __init__(
        self,
        project_name: str | None = None,
        storage_path: Optional[Path] = None,
    ):
        # CRITICAL: Read project name from LANGCHAIN_PROJECT env var
        # This must match the project in LangSmith UI (igor-trading-system)
        self.project_name = project_name or os.getenv("LANGCHAIN_PROJECT", "igor-trading-system")
        self.storage_path = storage_path or Path("data/traces")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Current trace context (thread-local in production)
        self._current_trace: Optional[Trace] = None
        self._span_stack: list[TraceSpan] = []

        # LangSmith client (if API key available)
        self._langsmith_client = None
        self._langsmith_enabled = False
        self._init_langsmith()

        # Evaluation datasets
        self._eval_datasets: dict[str, EvaluationDataset] = {}

        # Daily cost tracking
        self._daily_costs: dict[str, float] = {}  # date -> total_cost
        self._daily_budget = float(os.getenv("DAILY_LLM_BUDGET", "3.33"))  # $100/30 days

        logger.info(
            f"LangSmithTracer initialized: project={project_name}, "
            f"langsmith_enabled={self._langsmith_enabled}"
        )

    def _init_langsmith(self):
        """Initialize LangSmith client if API key is available."""
        api_key = os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")

        if api_key:
            try:
                from langsmith import Client

                self._langsmith_client = Client(api_key=api_key)
                self._langsmith_enabled = True
                logger.info("LangSmith client initialized successfully")
            except ImportError:
                logger.warning("langsmith package not installed, using local tracing only")
            except Exception as e:
                logger.warning(f"Failed to initialize LangSmith client: {e}")

    @classmethod
    def get_instance(cls, **kwargs) -> LangSmithTracer:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    @contextmanager
    def trace(self, name: str, trace_type: TraceType = TraceType.ANALYSIS, **metadata):
        """Context manager for tracing an operation."""
        # Create new trace if none exists
        if self._current_trace is None:
            self._current_trace = Trace(name=name)

        # Create span
        parent_id = self._span_stack[-1].span_id if self._span_stack else None
        span = TraceSpan(
            name=name,
            trace_type=trace_type,
            parent_id=parent_id,
            metadata=metadata,
        )

        self._span_stack.append(span)
        self._current_trace.add_span(span)

        try:
            yield span
        except Exception as e:
            span.complete(error=str(e))
            raise
        else:
            span.complete()
        finally:
            self._span_stack.pop()

            # If this was the root span, complete and save the trace
            if not self._span_stack:
                self._current_trace.complete()
                self._save_trace(self._current_trace)
                self._track_cost(self._current_trace)
                self._current_trace = None

    def _save_trace(self, trace: Trace):
        """Save trace to storage and optionally to LangSmith."""
        # Save locally
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        trace_file = self.storage_path / f"traces_{today}.jsonl"

        with open(trace_file, "a") as f:
            f.write(json.dumps(trace.to_dict()) + "\n")

        # Send to LangSmith if enabled
        if self._langsmith_enabled and self._langsmith_client:
            try:
                # LangSmith runs API - each span becomes a run
                for span in trace.spans:
                    run_id = str(uuid.uuid4())

                    # Create run with all required fields
                    self._langsmith_client.create_run(
                        name=span.name or f"{span.trace_type.value}_span",
                        run_type="chain",
                        inputs=span.inputs or {},
                        outputs=span.outputs or {},
                        extra=span.metadata if span.metadata else None,
                        project_name=self.project_name,
                        id=run_id,
                        start_time=span.start_time,
                        end_time=span.end_time or datetime.now(timezone.utc),
                        error=span.error,
                        tags=[span.trace_type.value, "trading-system"],
                    )
                    logger.debug(
                        f"Sent run to LangSmith: {span.name} (project={self.project_name})"
                    )

                logger.info(
                    f"✅ Sent {len(trace.spans)} trace(s) to LangSmith project '{self.project_name}'"
                )
            except Exception as e:
                logger.warning(f"Failed to send trace to LangSmith: {e}")

    def _track_cost(self, trace: Trace):
        """Track daily costs for budget management."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if today not in self._daily_costs:
            self._daily_costs[today] = 0.0

        self._daily_costs[today] += trace.total_cost_usd

        # Warn if approaching budget
        if self._daily_costs[today] > self._daily_budget * 0.8:
            logger.warning(
                f"Daily LLM cost approaching budget: "
                f"${self._daily_costs[today]:.4f} / ${self._daily_budget:.2f}"
            )

    def get_daily_cost(self, date: Optional[str] = None) -> float:
        """Get total cost for a specific day."""
        date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._daily_costs.get(date, 0.0)

    def get_evaluation_dataset(self, name: str) -> EvaluationDataset:
        """Get or create an evaluation dataset."""
        if name not in self._eval_datasets:
            self._eval_datasets[name] = EvaluationDataset(
                name=name,
                storage_path=self.storage_path / "evaluations",
            )
        return self._eval_datasets[name]

    def get_trace_summary(self, days: int = 7) -> dict[str, Any]:
        """Get summary of traces for the past N days."""
        summary = {
            "total_traces": 0,
            "total_cost_usd": 0.0,
            "total_tokens": 0,
            "by_type": {},
            "by_day": {},
            "avg_duration_ms": 0.0,
            "error_rate": 0.0,
        }

        durations = []
        errors = 0

        for i in range(days):
            day = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            trace_file = self.storage_path / f"traces_{day}.jsonl"

            if not trace_file.exists():
                continue

            day_cost = 0.0
            day_count = 0

            with open(trace_file) as f:
                for line in f:
                    trace_data = json.loads(line)
                    summary["total_traces"] += 1
                    summary["total_cost_usd"] += trace_data.get("total_cost_usd", 0)
                    summary["total_tokens"] += trace_data.get("total_tokens", 0)
                    durations.append(trace_data.get("total_duration_ms", 0))

                    day_cost += trace_data.get("total_cost_usd", 0)
                    day_count += 1

                    # Count by type
                    for span in trace_data.get("spans", []):
                        trace_type = span.get("trace_type", "unknown")
                        summary["by_type"][trace_type] = summary["by_type"].get(trace_type, 0) + 1

                        if span.get("status") == "error":
                            errors += 1

            summary["by_day"][day] = {"count": day_count, "cost_usd": day_cost}

        if durations:
            summary["avg_duration_ms"] = sum(durations) / len(durations)

        if summary["total_traces"] > 0:
            summary["error_rate"] = errors / summary["total_traces"]

        return summary


# Global tracer instance
_tracer: Optional[LangSmithTracer] = None


def get_tracer(**kwargs) -> LangSmithTracer:
    """Get the global tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = LangSmithTracer.get_instance(**kwargs)
    return _tracer


def traceable_decision(
    name: Optional[str] = None,
    trace_type: TraceType = TraceType.DECISION,
):
    """Decorator for tracing decision-making functions."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            func_name = name or func.__name__

            with tracer.trace(func_name, trace_type=trace_type) as span:
                # Capture inputs (skip self if method)
                inputs = {}
                if args and hasattr(args[0], "__class__"):
                    inputs["args"] = [str(a) for a in args[1:]]
                else:
                    inputs["args"] = [str(a) for a in args]
                inputs["kwargs"] = {k: str(v) for k, v in kwargs.items()}
                span.inputs = inputs

                result = await func(*args, **kwargs)

                # Capture output
                span.add_output("result", str(result)[:500])

                return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            func_name = name or func.__name__

            with tracer.trace(func_name, trace_type=trace_type) as span:
                inputs = {}
                if args and hasattr(args[0], "__class__"):
                    inputs["args"] = [str(a) for a in args[1:]]
                else:
                    inputs["args"] = [str(a) for a in args]
                inputs["kwargs"] = {k: str(v) for k, v in kwargs.items()}
                span.inputs = inputs

                result = func(*args, **kwargs)
                span.add_output("result", str(result)[:500])

                return result

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def traceable_signal(name: Optional[str] = None):
    """Decorator for tracing signal generation."""
    return traceable_decision(name=name, trace_type=TraceType.SIGNAL)


def traceable_trade(name: Optional[str] = None):
    """Decorator for tracing trade execution."""
    return traceable_decision(name=name, trace_type=TraceType.TRADE)


def traceable_analysis(name: Optional[str] = None):
    """Decorator for tracing market analysis."""
    return traceable_decision(name=name, trace_type=TraceType.ANALYSIS)


def traceable_risk(name: Optional[str] = None):
    """Decorator for tracing risk calculations."""
    return traceable_decision(name=name, trace_type=TraceType.RISK)
