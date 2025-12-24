"""Parallel ticker processor for concurrent trade evaluation.

Implements the ADK Parallel Fan-Out/Gather pattern for processing multiple
tickers simultaneously, reducing latency from O(n) to O(1) for n tickers.

Reference: Google ADK Developer's Guide - Multi-Agent Patterns
https://developers.googleblog.com/en/developers-guide-to-multi-agent-patterns-in-adk/

Key benefits:
- Reduces total processing time from N*T to max(T) where T is time per ticker
- Isolates failures - one ticker's error doesn't block others
- Each ticker writes to unique state key (thread-safe)

December 2025 - Based on ADK research for operational efficiency.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class TickerOutcome(Enum):
    """Outcome status for parallel ticker processing."""

    PASSED = "passed"  # All gates passed, trade executed
    REJECTED = "rejected"  # Rejected by one of the gates
    ERROR = "error"  # Exception during processing
    SKIPPED = "skipped"  # Skipped due to external condition


@dataclass
class TickerResult:
    """Result of processing a single ticker in parallel.

    Each ticker writes to its own TickerResult instance (unique key pattern),
    preventing race conditions in the ADK parallel pattern.
    """

    ticker: str
    outcome: TickerOutcome
    gate_reached: int = 0  # Highest gate number reached (0-5)
    rejection_gate: str | None = None
    rejection_reason: str | None = None
    error_message: str | None = None
    processing_time_ms: float = 0.0
    indicators: dict[str, Any] = field(default_factory=dict)
    order_details: dict[str, Any] | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ParallelProcessingResult:
    """Aggregated result of parallel ticker processing."""

    total_tickers: int
    passed: int = 0
    rejected: int = 0
    errors: int = 0
    skipped: int = 0
    total_time_ms: float = 0.0
    results: dict[str, TickerResult] = field(default_factory=dict)

    def summary(self) -> str:
        """Human-readable summary of parallel processing."""
        return (
            f"Parallel processing complete: {self.passed}/{self.total_tickers} passed, "
            f"{self.rejected} rejected, {self.errors} errors in {self.total_time_ms:.0f}ms"
        )


class ThreadSafeCounter:
    """Thread-safe counter for tracking parallel execution stats."""

    def __init__(self) -> None:
        self._value = 0
        self._lock = threading.Lock()

    def increment(self) -> int:
        with self._lock:
            self._value += 1
            return self._value

    @property
    def value(self) -> int:
        with self._lock:
            return self._value


class ParallelTickerProcessor:
    """Processes multiple tickers in parallel using ThreadPoolExecutor.

    Implements the ADK Parallel Fan-Out/Gather pattern:
    1. Fan-out: Submit all ticker processing tasks concurrently
    2. Execute: Each ticker runs through gates independently
    3. Gather: Collect results as they complete, aggregate stats

    Thread safety:
    - Each ticker writes to its own TickerResult (unique key)
    - Shared state access (telemetry, mental_coach) uses locks
    - Counters use ThreadSafeCounter

    Usage:
        processor = ParallelTickerProcessor(
            process_fn=orchestrator._process_ticker_safe,
            max_workers=5
        )
        result = processor.process_tickers(tickers, rl_threshold=0.65)
    """

    def __init__(
        self,
        process_fn: Callable[[str, float], TickerResult],
        max_workers: int = 5,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize parallel processor.

        Args:
            process_fn: Function to process a single ticker.
                        Signature: (ticker: str, rl_threshold: float) -> TickerResult
            max_workers: Maximum concurrent threads. Default 5 (conservative).
                        Higher values may hit API rate limits.
            timeout_seconds: Timeout per ticker. Default 30s.
        """
        self.process_fn = process_fn
        self.max_workers = max_workers
        self.timeout_seconds = timeout_seconds

        # Thread-safe counters
        self._active_count = ThreadSafeCounter()
        self._completed_count = ThreadSafeCounter()

        logger.info(
            "ParallelTickerProcessor initialized: max_workers=%d, timeout=%.1fs",
            max_workers,
            timeout_seconds,
        )

    def process_tickers(
        self,
        tickers: list[str],
        rl_threshold: float,
    ) -> ParallelProcessingResult:
        """Process multiple tickers in parallel.

        Args:
            tickers: List of ticker symbols to process
            rl_threshold: RL confidence threshold for all tickers

        Returns:
            ParallelProcessingResult with aggregated stats and per-ticker results
        """
        if not tickers:
            return ParallelProcessingResult(total_tickers=0)

        start_time = datetime.now(timezone.utc)
        result = ParallelProcessingResult(total_tickers=len(tickers))

        logger.info(
            "Starting parallel processing of %d tickers with %d workers",
            len(tickers),
            min(self.max_workers, len(tickers)),
        )

        # Use ThreadPoolExecutor for parallel execution
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(tickers))) as executor:
            # Fan-out: Submit all tasks
            future_to_ticker = {
                executor.submit(self._process_single, ticker, rl_threshold): ticker
                for ticker in tickers
            }

            # Gather: Collect results as they complete
            for future in as_completed(future_to_ticker, timeout=self.timeout_seconds * 2):
                ticker = future_to_ticker[future]
                try:
                    ticker_result = future.result(timeout=self.timeout_seconds)
                    result.results[ticker] = ticker_result

                    # Update counters based on outcome
                    if ticker_result.outcome == TickerOutcome.PASSED:
                        result.passed += 1
                    elif ticker_result.outcome == TickerOutcome.REJECTED:
                        result.rejected += 1
                    elif ticker_result.outcome == TickerOutcome.ERROR:
                        result.errors += 1
                    else:
                        result.skipped += 1

                except TimeoutError:
                    logger.error("Ticker %s timed out after %.1fs", ticker, self.timeout_seconds)
                    result.results[ticker] = TickerResult(
                        ticker=ticker,
                        outcome=TickerOutcome.ERROR,
                        error_message=f"Timeout after {self.timeout_seconds}s",
                    )
                    result.errors += 1

                except Exception as e:
                    logger.error("Ticker %s failed with unexpected error: %s", ticker, e)
                    result.results[ticker] = TickerResult(
                        ticker=ticker,
                        outcome=TickerOutcome.ERROR,
                        error_message=str(e),
                    )
                    result.errors += 1

        # Calculate total time
        end_time = datetime.now(timezone.utc)
        result.total_time_ms = (end_time - start_time).total_seconds() * 1000

        logger.info(result.summary())

        return result

    def _process_single(self, ticker: str, rl_threshold: float) -> TickerResult:
        """Process a single ticker with timing and error handling.

        This wraps the actual processing function with:
        - Timing measurement
        - Exception handling
        - Structured result creation
        """
        start_time = datetime.now(timezone.utc)
        active = self._active_count.increment()
        logger.debug("Processing %s (active: %d)", ticker, active)

        try:
            # Call the actual processing function
            result = self.process_fn(ticker, rl_threshold)

            # Ensure we have a valid result
            if not isinstance(result, TickerResult):
                # Convert legacy None/dict returns to TickerResult
                result = TickerResult(
                    ticker=ticker,
                    outcome=TickerOutcome.PASSED if result else TickerOutcome.REJECTED,
                )

            # Add timing
            end_time = datetime.now(timezone.utc)
            result.processing_time_ms = (end_time - start_time).total_seconds() * 1000

            completed = self._completed_count.increment()
            logger.debug(
                "Completed %s: %s in %.0fms (completed: %d)",
                ticker,
                result.outcome.value,
                result.processing_time_ms,
                completed,
            )

            return result

        except Exception as e:
            end_time = datetime.now(timezone.utc)
            processing_time_ms = (end_time - start_time).total_seconds() * 1000

            logger.error("Error processing %s: %s", ticker, e, exc_info=True)

            return TickerResult(
                ticker=ticker,
                outcome=TickerOutcome.ERROR,
                error_message=str(e),
                processing_time_ms=processing_time_ms,
            )


def create_thread_safe_wrapper(
    telemetry: Any,
    process_ticker_fn: Callable[[str, float], None],
) -> Callable[[str, float], TickerResult]:
    """Create a thread-safe wrapper around the existing _process_ticker method.

    This adapter converts the existing void _process_ticker method into a
    thread-safe function that returns TickerResult.

    Args:
        telemetry: OrchestratorTelemetry instance (needs lock for session_decisions)
        process_ticker_fn: The original _process_ticker method

    Returns:
        Thread-safe function that returns TickerResult
    """
    # Lock for accessing shared telemetry state
    telemetry_lock = threading.Lock()

    def safe_process_ticker(ticker: str, rl_threshold: float) -> TickerResult:
        """Thread-safe wrapper that captures processing result."""
        # Initialize tracking with lock
        with telemetry_lock:
            telemetry.start_ticker_decision(ticker)

        try:
            # Call the original processing function
            process_ticker_fn(ticker, rl_threshold)

            # Extract result from telemetry (with lock)
            with telemetry_lock:
                decision = telemetry.session_decisions.get(ticker, {})

            outcome = TickerOutcome.PASSED
            if decision.get("decision") == "REJECTED":
                outcome = TickerOutcome.REJECTED
            elif decision.get("decision") == "PENDING":
                outcome = TickerOutcome.SKIPPED

            return TickerResult(
                ticker=ticker,
                outcome=outcome,
                gate_reached=decision.get("gate_reached", 0),
                rejection_reason=decision.get("rejection_reason"),
                indicators=decision.get("indicators", {}),
                order_details=decision.get("order_details"),
            )

        except Exception as e:
            logger.error("Thread-safe wrapper caught error for %s: %s", ticker, e)
            return TickerResult(
                ticker=ticker,
                outcome=TickerOutcome.ERROR,
                error_message=str(e),
            )

    return safe_process_ticker
