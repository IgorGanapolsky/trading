"""
Observability Hooks for TradingOrchestrator.

Provides automatic tracing integration without modifying core orchestrator code.
Uses monkey-patching to wrap key methods with observability.

Usage:
    from src.observability.orchestrator_hooks import enable_observability

    # Enable observability for all orchestrator instances
    enable_observability()

    # Or for a specific instance
    orchestrator = TradingOrchestrator(tickers=["SPY"])
    enable_observability(orchestrator)
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Optional, TypeVar

from src.observability.langsmith_tracer import (
    LangSmithTracer,
    TraceType,
    get_tracer,
)
from src.observability.trade_evaluator import TradeEvaluator

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _wrap_with_trace(
    method: F,
    name: str,
    trace_type: TraceType,
    tracer: LangSmithTracer,
) -> F:
    """Wrap a method with tracing."""

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        with tracer.trace(name, trace_type=trace_type) as span:
            # Capture key inputs
            if args and len(args) > 1:
                span.inputs["args"] = [str(a)[:200] for a in args[1:]]
            span.inputs["kwargs"] = {k: str(v)[:200] for k, v in kwargs.items()}

            try:
                result = method(*args, **kwargs)
                span.add_output("result", str(result)[:500] if result else "None")
                return result
            except Exception as e:
                span.complete(error=str(e))
                raise

    return wrapper  # type: ignore


def enable_observability(
    orchestrator: Optional[Any] = None,
    tracer: Optional[LangSmithTracer] = None,
    evaluator: Optional[TradeEvaluator] = None,
) -> None:
    """
    Enable observability for the trading orchestrator.

    If orchestrator is provided, wraps that specific instance.
    Otherwise, monkey-patches the TradingOrchestrator class.

    Args:
        orchestrator: Optional specific orchestrator instance to wrap
        tracer: Optional custom tracer (uses global if not provided)
        evaluator: Optional custom evaluator (creates new if not provided)
    """
    tracer = tracer or get_tracer()
    evaluator = evaluator or TradeEvaluator()

    # Methods to wrap with their trace types
    methods_to_wrap = {
        "run": TraceType.DECISION,
        "_process_ticker": TraceType.ANALYSIS,
        "_execute_trade": TraceType.TRADE,
        "_evaluate_signal": TraceType.SIGNAL,
        "_apply_risk_checks": TraceType.RISK,
    }

    if orchestrator is not None:
        # Wrap specific instance
        for method_name, trace_type in methods_to_wrap.items():
            if hasattr(orchestrator, method_name):
                original = getattr(orchestrator, method_name)
                wrapped = _wrap_with_trace(original, method_name, trace_type, tracer)
                setattr(orchestrator, method_name, wrapped)

        # Store references
        orchestrator._observability_tracer = tracer
        orchestrator._observability_evaluator = evaluator

        logger.info("Observability enabled for orchestrator instance")
    else:
        # Monkey-patch the class
        try:
            from src.orchestrator.main import TradingOrchestrator

            original_init = TradingOrchestrator.__init__

            @functools.wraps(original_init)
            def patched_init(self, *args, **kwargs):
                original_init(self, *args, **kwargs)

                # Wrap methods on this instance
                for method_name, trace_type in methods_to_wrap.items():
                    if hasattr(self, method_name):
                        original = getattr(self, method_name)
                        wrapped = _wrap_with_trace(original, method_name, trace_type, tracer)
                        setattr(self, method_name, wrapped)

                self._observability_tracer = tracer
                self._observability_evaluator = evaluator

                logger.info("Observability auto-enabled for new TradingOrchestrator")

            TradingOrchestrator.__init__ = patched_init
            logger.info("TradingOrchestrator class patched with observability")

        except ImportError:
            logger.warning("Could not import TradingOrchestrator for patching")


def create_traced_orchestrator(
    tickers: list[str],
    paper: bool = True,
    **kwargs,
) -> Any:
    """
    Factory function to create an orchestrator with observability enabled.

    Usage:
        orchestrator = create_traced_orchestrator(["SPY", "QQQ"])
        orchestrator.run()  # All methods automatically traced
    """
    from src.orchestrator.main import TradingOrchestrator

    orchestrator = TradingOrchestrator(tickers=tickers, paper=paper, **kwargs)
    enable_observability(orchestrator)

    return orchestrator


class ObservabilityMiddleware:
    """
    Middleware for adding observability to any trading component.

    Usage:
        from src.observability.orchestrator_hooks import ObservabilityMiddleware

        middleware = ObservabilityMiddleware()

        @middleware.trace("signal_generation")
        def generate_signal(symbol: str) -> Signal:
            ...

        # Or use as context manager
        with middleware.span("analysis", symbol="SPY") as span:
            result = analyze_market()
            span.add_output("result", result)
    """

    def __init__(
        self,
        tracer: Optional[LangSmithTracer] = None,
        evaluator: Optional[TradeEvaluator] = None,
    ):
        self.tracer = tracer or get_tracer()
        self.evaluator = evaluator or TradeEvaluator()

    def trace(self, name: str, trace_type: TraceType = TraceType.ANALYSIS):
        """Decorator for tracing a function."""

        def decorator(func: F) -> F:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self.tracer.trace(name, trace_type=trace_type) as span:
                    span.inputs = {"args": str(args)[:500], "kwargs": str(kwargs)[:500]}
                    result = func(*args, **kwargs)
                    span.add_output("result", str(result)[:500])
                    return result

            return wrapper  # type: ignore

        return decorator

    def span(self, name: str, trace_type: TraceType = TraceType.ANALYSIS, **metadata):
        """Context manager for creating a traced span."""
        return self.tracer.trace(name, trace_type=trace_type, **metadata)

    def record_decision(
        self,
        symbol: str,
        decision: str,
        confidence: float,
        reasoning: str,
        price: float,
        **kwargs,
    ) -> str:
        """Record a trade decision for evaluation."""
        return self.evaluator.record_decision(
            symbol=symbol,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            price=price,
            **kwargs,
        )

    def record_outcome(self, record_id: str, exit_price: float, **kwargs):
        """Record the outcome of a trade decision."""
        return self.evaluator.record_outcome(
            record_id=record_id,
            exit_price=exit_price,
            **kwargs,
        )
