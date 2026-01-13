"""
Trading gates module - LLM-friendly decomposition of the trading funnel.

Each gate is a separate method with:
- Clear input/output contracts
- Independent testability
- <150 lines per method
- Explicit pass/reject semantics

Gates:
- Gate S: Security validation (prompt injection, signal validation)
- Gate M: Memory query (TradeMemory feedback loop)
- Gate 0: Psychology pre-trade check
- Gate 1: Momentum filter
- Gate 1.5: Bull/Bear debate
- Gate 2: RL filter
- Gate 3: LLM sentiment
- Gate 3.5: Introspective awareness
- Gate 4: Risk sizing
- Gate 5: Execution

Author: Claude (AI-native refactor Dec 2025)
Updated: Dec 24, 2025 - Added security gate and memory feedback loop
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Pipeline checkpointing for fault tolerance (Dec 2025)
# Tech debt cleanup Jan 13, 2026: Removed unused imports (CHECKPOINT_GATES, PipelineCheckpointer, should_checkpoint)
try:
    from src.orchestrator.checkpoint import get_checkpointer

    CHECKPOINTING_AVAILABLE = True
    logger.info("Pipeline checkpointing enabled")
except ImportError:
    CHECKPOINTING_AVAILABLE = False
    logger.warning("Checkpointing not available - pipeline will not be resumable")

# Observability: Vertex AI RAG + Local logs (Jan 9, 2026)


def _trace_gate(gate_name: str, ticker: str, metadata: dict, result: Any) -> None:
    """
    Trace gate execution for observability.

    Note: LangSmith tracing removed Jan 2026. This is now a no-op stub
    that can be connected to Vertex AI RAG or local logging if needed.
    """
    # Logging only - no external tracing
    logger.debug(
        f"Gate {gate_name} for {ticker}: {result.status if hasattr(result, 'status') else 'ok'}"
    )


def _timed_gate_execution(gate_func, *args, **kwargs) -> GateResult:
    """
    Execute a gate function with timing measurement.

    Capital One lesson: Post-launch latency optimization is critical.
    This wrapper captures execution_time_ms for every gate.
    """
    start_time = time.perf_counter()
    result = gate_func(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    result.execution_time_ms = elapsed_ms
    return result


class GateStatus(Enum):
    """Gate evaluation result status."""

    PASS = "pass"
    REJECT = "reject"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class GateResult:
    """
    Standard result from any trading gate.

    LLM-friendly: All gates return this same structure.
    Includes execution_time_ms for latency tracking (Capital One lesson).
    """

    gate_name: str
    status: GateStatus
    ticker: str
    confidence: float = 0.0
    reason: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0  # Gate latency tracking

    @property
    def passed(self) -> bool:
        return self.status == GateStatus.PASS

    @property
    def rejected(self) -> bool:
        return self.status == GateStatus.REJECT

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate_name,
            "status": self.status.value,
            "ticker": self.ticker,
            "confidence": self.confidence,
            "reason": self.reason,
            "execution_time_ms": self.execution_time_ms,
            **self.data,
        }


@dataclass
class TradeContext:
    """
    Context passed through the gate pipeline.

    Accumulates data from each gate for downstream use.
    """

    ticker: str
    momentum_signal: Any = None
    momentum_strength: float = 0.0
    rl_decision: dict[str, Any] = field(default_factory=dict)
    sentiment_score: float = 0.0
    debate_outcome: Any = None
    introspection_multiplier: float = 1.0
    allocation_plan: Any = None
    current_price: float | None = None
    hist: Any = None
    atr_pct: float | None = None
    regime_snapshot: dict[str, Any] = field(
        default_factory=lambda: {"label": "unknown", "confidence": 0.0}
    )
    rag_context: dict[str, Any] = field(default_factory=dict)
    order_size: float = 0.0
    session_profile: dict[str, Any] = field(default_factory=dict)


class RAGPreTradeQuery:
    """
    Query lessons learned RAG before each trade decision.

    Retrieves relevant lessons, past mistakes, and context for the specific
    ticker and market conditions.

    ENFORCEMENT (Dec 2025): CRITICAL/HIGH severity lessons now BLOCK trades.
    """

    def __init__(self, lessons_rag: Any, telemetry: Any):
        self.lessons_rag = lessons_rag
        self.telemetry = telemetry

    def query(self, ticker: str, ctx: TradeContext) -> dict[str, Any]:
        """
        Query RAG for relevant lessons before trading this ticker.

        Returns:
            Dict with lessons, warnings, and should_block flag
        """
        if not self.lessons_rag:
            return {"available": False, "lessons": [], "warnings": [], "should_block": False}

        try:
            # Build context-aware query
            momentum_label = "bullish" if ctx.momentum_strength > 0.5 else "bearish"
            regime = ctx.regime_snapshot.get("label", "unknown")
            query = f"{ticker} {momentum_label} {regime} trading mistakes errors lessons"

            results = self.lessons_rag.search(query=query, top_k=3)

            lessons = []
            warnings = []
            should_block = False
            block_reason = None

            for lesson, score in results or []:
                if score > 0.15:  # Relevance threshold
                    severity = lesson.severity.upper()
                    lessons.append(
                        {
                            "id": getattr(lesson, "id", "unknown"),
                            "title": lesson.title,
                            "severity": severity,
                            "prevention": lesson.prevention[:200],
                            "score": score,
                        }
                    )
                    if severity in ("HIGH", "CRITICAL"):
                        warnings.append(
                            f"[{lesson.severity}] {lesson.title}: {lesson.prevention[:100]}"
                        )
                        # ENFORCEMENT: Block on CRITICAL with high relevance, or HIGH with very high relevance
                        if severity == "CRITICAL" and score > 0.5:
                            should_block = True
                            block_reason = (
                                f"CRITICAL lesson matched (score={score:.2f}): {lesson.title}"
                            )
                        elif severity == "HIGH" and score > 0.7:
                            should_block = True
                            block_reason = (
                                f"HIGH lesson matched (score={score:.2f}): {lesson.title}"
                            )

            if lessons:
                logger.info("RAG Query (%s): Found %d relevant lessons", ticker, len(lessons))
                self.telemetry.record(
                    event_type="rag.pre_trade",
                    ticker=ticker,
                    status="blocked" if should_block else "queried",
                    payload={
                        "lessons_found": len(lessons),
                        "top_lesson": lessons[0]["title"] if lessons else None,
                        "warnings": len(warnings),
                        "should_block": should_block,
                        "block_reason": block_reason,
                    },
                )

            return {
                "available": True,
                "lessons": lessons,
                "warnings": warnings,
                "query": query,
                "should_block": should_block,
                "block_reason": block_reason,
            }

        except Exception as e:
            logger.debug("RAG query failed for %s: %s", ticker, e)
            return {
                "available": True,
                "lessons": [],
                "warnings": [],
                "error": str(e),
                "should_block": False,
            }


class TradeMemoryQuery:
    """
    Query TradeMemory for historical pattern performance before each trade.

    THE KEY INSIGHT: Most systems write to journals but never READ before trading.
    This class makes pattern history ACTIONABLE by blocking poor performers.

    Based on December 2025 research:
    - TradesViz users see 20% win rate improvement with pre-trade queries
    - Simple pattern matching beats complex ML
    """

    def __init__(self, trade_memory: Any, telemetry: Any):
        self.trade_memory = trade_memory
        self.telemetry = telemetry
        # Minimum win rate to allow trade (configurable)
        self.min_win_rate = float(os.getenv("TRADE_MEMORY_MIN_WIN_RATE", "0.4"))
        # Minimum sample size before enforcing win rate
        self.min_samples = int(os.getenv("TRADE_MEMORY_MIN_SAMPLES", "5"))

    def query(self, ticker: str, strategy: str, entry_reason: str) -> dict[str, Any]:
        """
        Query historical pattern performance before trading.

        Args:
            ticker: Symbol being traded
            strategy: Trading strategy (e.g., "iron_condor", "momentum_long")
            entry_reason: Why we're entering (e.g., "high_iv", "bullish_macd")

        Returns:
            Dict with pattern stats and should_block flag
        """
        if not self.trade_memory:
            return {
                "available": False,
                "should_block": False,
                "recommendation": "NO_MEMORY",
            }

        try:
            # Query the pattern
            result = self.trade_memory.query_similar(strategy, entry_reason)

            should_block = False
            block_reason = None

            # Enforce minimum win rate if we have enough samples
            if result.get("found") and result.get("sample_size", 0) >= self.min_samples:
                win_rate = result.get("win_rate", 0.5)
                if win_rate < self.min_win_rate:
                    should_block = True
                    block_reason = (
                        f"Pattern '{result['pattern']}' has {win_rate:.0%} win rate "
                        f"({result['wins']}W/{result['losses']}L) - below {self.min_win_rate:.0%} threshold"
                    )

            # Also check for STRONG_AVOID recommendation
            if result.get("recommendation") == "STRONG_AVOID":
                should_block = True
                block_reason = f"Pattern '{result['pattern']}' marked STRONG_AVOID (win rate: {result.get('win_rate', 0):.0%})"

            # Log the query
            self.telemetry.record(
                event_type="trade_memory.pre_trade",
                ticker=ticker,
                status="blocked" if should_block else "checked",
                payload={
                    "pattern": result.get("pattern"),
                    "found": result.get("found", False),
                    "sample_size": result.get("sample_size", 0),
                    "win_rate": result.get("win_rate", 0.5),
                    "recommendation": result.get("recommendation"),
                    "should_block": should_block,
                    "block_reason": block_reason,
                },
            )

            if should_block:
                logger.warning("TradeMemory BLOCK (%s): %s", ticker, block_reason)
            elif result.get("found"):
                logger.info(
                    "TradeMemory (%s): Pattern '%s' has %.0f%% win rate (%d trades) - %s",
                    ticker,
                    result.get("pattern"),
                    result.get("win_rate", 0) * 100,
                    result.get("sample_size", 0),
                    result.get("recommendation"),
                )

            return {
                "available": True,
                "pattern": result.get("pattern"),
                "found": result.get("found", False),
                "sample_size": result.get("sample_size", 0),
                "win_rate": result.get("win_rate", 0.5),
                "wins": result.get("wins", 0),
                "losses": result.get("losses", 0),
                "total_pnl": result.get("total_pnl", 0.0),
                "avg_pnl": result.get("avg_pnl", 0.0),
                "recommendation": result.get("recommendation"),
                "should_block": should_block,
                "block_reason": block_reason,
            }

        except Exception as e:
            logger.debug("TradeMemory query failed for %s: %s", ticker, e)
            return {
                "available": False,
                "should_block": False,
                "error": str(e),
                "recommendation": "QUERY_FAILED",
            }


# =============================================================================
# SECURITY GATE (Gate S) - Must run FIRST before any trading logic
# =============================================================================


class GateSecurity:
    """
    Gate S: Security validation gate.

    CRITICAL: This gate MUST run before all other gates.
    Protects against:
    - Prompt injection attacks in external data
    - LLM output manipulation
    - Invalid/hallucinated trade signals

    Based on OWASP LLM01:2025 and OpenAI security research.
    Added: Dec 24, 2025
    """

    def __init__(self, telemetry: Any, strict_mode: bool = True):
        self.telemetry = telemetry
        self.strict_mode = strict_mode

        # Import security utilities
        from src.utils.security import (
            PromptInjectionDefense,
            SecurityError,
            scan_for_injection,
            validate_trade_signal,
        )

        self.defense = PromptInjectionDefense(strict_mode=strict_mode)
        self.scan_for_injection = scan_for_injection
        self.validate_trade_signal = validate_trade_signal
        self.SecurityError = SecurityError

    def _log_telemetry(self, **kwargs):
        """Safely log to telemetry if available."""
        if self.telemetry:
            self.telemetry.record(**kwargs)

    def evaluate(
        self,
        ticker: str,
        external_data: dict[str, str] | None = None,
        trade_signal: dict | None = None,
    ) -> GateResult:
        """
        Validate security of inputs before processing.

        Args:
            ticker: Symbol being evaluated
            external_data: Dict of external data sources to scan (news, sentiment, etc.)
            trade_signal: Optional trade signal to validate

        Returns:
            GateResult with PASS if secure, REJECT if threats detected
        """
        threats_found = []
        blocked = False

        # 1. Scan external data for prompt injection
        if external_data:
            for source, content in external_data.items():
                if content:
                    result = self.scan_for_injection(content)
                    if result.blocked:
                        threats_found.extend([f"{source}:{t}" for t in result.threats_detected])
                        blocked = True
                        logger.warning(
                            "🛡️ Gate S (%s): BLOCKED %s - %s",
                            ticker,
                            source,
                            result.threats_detected,
                        )

        # 2. Validate trade signal if provided
        signal_valid = True
        signal_errors = []
        if trade_signal:
            validation = self.validate_trade_signal(trade_signal)
            if not validation.is_valid:
                signal_valid = False
                signal_errors = validation.errors
                blocked = True
                logger.warning(
                    "🛡️ Gate S (%s): Invalid signal - %s",
                    ticker,
                    validation.errors,
                )

        # Record telemetry (safely, telemetry may be None in tests)
        self._log_telemetry(
            event_type="security.scan",
            ticker=ticker,
            status="blocked" if blocked else "pass",
            payload={
                "threats_found": threats_found,
                "signal_valid": signal_valid,
                "signal_errors": signal_errors,
                "strict_mode": self.strict_mode,
            },
        )

        if blocked:
            return GateResult(
                gate_name="security",
                status=GateStatus.REJECT,
                ticker=ticker,
                reason=f"Security threats: {threats_found + signal_errors}",
                data={"threats": threats_found, "signal_errors": signal_errors},
            )

        return GateResult(
            gate_name="security",
            status=GateStatus.PASS,
            ticker=ticker,
            data={"scanned_sources": list(external_data.keys()) if external_data else []},
        )


# =============================================================================
# MEMORY GATE (Gate M) - Feedback loop from past trades
# =============================================================================


class GateMemory:
    """
    Gate M: Trade memory feedback loop.

    Queries past trades to learn from history before making new decisions.
    This is the "closing the loop" gate that most systems skip.

    Based on TradesViz research showing 20% win rate improvement.
    Added: Dec 24, 2025
    """

    def __init__(self, telemetry: Any, db_path: str = "data/trade_memory.db"):
        self.telemetry = telemetry
        self.db_path = db_path
        self.memory = None

        # Lazy initialization to avoid import errors
        try:
            from src.learning.trade_memory import TradeMemory

            self.memory = TradeMemory(db_path=db_path)
            logger.info("TradeMemory initialized for feedback loop")
        except Exception as e:
            logger.warning("TradeMemory init failed: %s", e)

    def _log_telemetry(self, **kwargs):
        """Safely log to telemetry if available."""
        if self.telemetry:
            self.telemetry.record(**kwargs)

    def evaluate(
        self,
        ticker: str,
        strategy: str,
        entry_reason: str,
        min_win_rate: float = 0.4,
    ) -> GateResult:
        """
        Query past trades for similar setups.

        Args:
            ticker: Symbol being evaluated
            strategy: Trading strategy (e.g., "momentum", "iron_condor")
            entry_reason: Reason for entry (e.g., "high_iv", "macd_cross")
            min_win_rate: Minimum win rate to proceed (default 40%)

        Returns:
            GateResult with PASS/SKIP/REJECT based on historical performance
        """
        if not self.memory:
            return GateResult(
                gate_name="memory",
                status=GateStatus.SKIP,
                ticker=ticker,
                reason="TradeMemory not available",
            )

        try:
            similar = self.memory.query_similar(strategy, entry_reason)

            # Log the query
            self._log_telemetry(
                event_type="memory.query",
                ticker=ticker,
                status="queried",
                payload={
                    "pattern": similar.get("pattern"),
                    "found": similar.get("found"),
                    "sample_size": similar.get("sample_size", 0),
                    "win_rate": similar.get("win_rate", 0.5),
                    "recommendation": similar.get("recommendation"),
                },
            )

            # No history - proceed with neutral confidence
            if not similar.get("found") or similar.get("sample_size", 0) < 3:
                logger.info(
                    "Gate M (%s): No history for %s_%s - proceeding cautiously",
                    ticker,
                    strategy,
                    entry_reason,
                )
                return GateResult(
                    gate_name="memory",
                    status=GateStatus.PASS,
                    ticker=ticker,
                    confidence=0.5,  # Neutral
                    data=similar,
                    reason="No historical data - proceed with caution",
                )

            win_rate = similar.get("win_rate", 0.5)
            recommendation = similar.get("recommendation", "NEUTRAL")

            # Strong avoid - reject
            if recommendation in ("STRONG_AVOID", "AVOID") or win_rate < min_win_rate:
                logger.warning(
                    "Gate M (%s): REJECTED - %s has %.1f%% win rate (min=%.1f%%)",
                    ticker,
                    similar.get("pattern"),
                    win_rate * 100,
                    min_win_rate * 100,
                )
                return GateResult(
                    gate_name="memory",
                    status=GateStatus.REJECT,
                    ticker=ticker,
                    reason=f"Poor historical performance: {win_rate:.1%} win rate",
                    data=similar,
                )

            # Good history - boost confidence
            confidence = min(0.9, 0.5 + (win_rate - 0.5) * 0.8)
            logger.info(
                "Gate M (%s): PASS - %s has %.1f%% win rate, rec=%s",
                ticker,
                similar.get("pattern"),
                win_rate * 100,
                recommendation,
            )

            return GateResult(
                gate_name="memory",
                status=GateStatus.PASS,
                ticker=ticker,
                confidence=confidence,
                data=similar,
            )

        except Exception as e:
            logger.warning("Gate M (%s): Query failed: %s", ticker, e)
            return GateResult(
                gate_name="memory",
                status=GateStatus.SKIP,
                ticker=ticker,
                reason=f"Memory query failed: {e}",
            )

    def record_outcome(
        self,
        ticker: str,
        strategy: str,
        entry_reason: str,
        won: bool,
        pnl: float,
        lesson: str = "",
    ) -> None:
        """
        Record trade outcome for future learning.

        This completes the feedback loop.
        """
        if not self.memory:
            return

        try:
            self.memory.add_trade(
                {
                    "symbol": ticker,
                    "strategy": strategy,
                    "entry_reason": entry_reason,
                    "won": won,
                    "pnl": pnl,
                    "lesson": lesson,
                }
            )
            logger.info(
                "Gate M: Recorded %s trade for %s (%s) - P/L: $%.2f",
                "WIN" if won else "LOSS",
                ticker,
                f"{strategy}_{entry_reason}",
                pnl,
            )
        except Exception as e:
            logger.warning("Failed to record trade outcome: %s", e)


# =============================================================================
# GATE 0: Psychology
# =============================================================================


class Gate0Psychology:
    """
    Gate 0: Pre-trade psychological readiness check.

    Ensures trader is mentally ready before committing capital.
    Based on mental toughness research and tilt detection.
    """

    def __init__(self, mental_coach: Any, telemetry: Any):
        self.mental_coach = mental_coach
        self.telemetry = telemetry

    def evaluate(self, ticker: str) -> GateResult:
        """
        Check psychological readiness to trade.

        Returns:
            GateResult with PASS if ready, REJECT if tilted/danger state
        """
        if not self.mental_coach:
            return GateResult(
                gate_name="psychology",
                status=GateStatus.SKIP,
                ticker=ticker,
                reason="Mental coach not configured",
            )

        try:
            # Pre-trade intervention check
            pre_trade_intervention = self.mental_coach.pre_trade_check(ticker)
            if pre_trade_intervention:
                logger.info(
                    "Gate 0 (%s): Pre-trade coaching - %s",
                    ticker,
                    pre_trade_intervention.headline,
                )
                self.telemetry.record(
                    event_type="coaching.pre_trade",
                    ticker=ticker,
                    status="intervention",
                    payload={
                        "headline": pre_trade_intervention.headline,
                        "severity": pre_trade_intervention.severity,
                        "action_items": pre_trade_intervention.action_items,
                    },
                )

            # Readiness check
            ready, blocking_intervention = self.mental_coach.is_ready_to_trade()
            if not ready:
                reason = blocking_intervention.headline if blocking_intervention else "Mental state"
                logger.warning("Gate 0 (%s): SKIPPED - Not ready: %s", ticker, reason)
                self.telemetry.gate_reject(
                    "coaching",
                    ticker,
                    {
                        "reason": reason,
                        "severity": blocking_intervention.severity
                        if blocking_intervention
                        else "critical",
                    },
                )
                return GateResult(
                    gate_name="psychology",
                    status=GateStatus.REJECT,
                    ticker=ticker,
                    reason=reason,
                )

            return GateResult(
                gate_name="psychology",
                status=GateStatus.PASS,
                ticker=ticker,
                confidence=1.0,
                reason="Ready to trade",
            )

        except Exception as e:
            logger.warning("Gate 0 (%s): Check failed, continuing: %s", ticker, e)
            return GateResult(
                gate_name="psychology",
                status=GateStatus.PASS,  # Fail-open
                ticker=ticker,
                reason=f"Check failed: {e}",
            )


class Gate1Momentum:
    """
    Gate 1: Deterministic momentum filter.

    Uses MACD, RSI, and volume to determine if momentum supports a buy.
    This is the first quantitative filter in the pipeline.
    """

    def __init__(self, momentum_agent: Any, failure_manager: Any, telemetry: Any):
        self.momentum_agent = momentum_agent
        self.failure_manager = failure_manager
        self.telemetry = telemetry

    def evaluate(self, ticker: str, ctx: TradeContext) -> GateResult:
        """
        Analyze momentum indicators for the ticker.

        Returns:
            GateResult with momentum signal data if PASS
        """
        outcome = self.failure_manager.run(
            gate="momentum",
            ticker=ticker,
            operation=lambda: self.momentum_agent.analyze(ticker),
        )

        if not outcome.ok:
            logger.error("Gate 1 (%s): Momentum analysis failed: %s", ticker, outcome.failure.error)
            return GateResult(
                gate_name="momentum",
                status=GateStatus.ERROR,
                ticker=ticker,
                reason=str(outcome.failure.error),
            )

        signal = outcome.result
        ctx.momentum_signal = signal
        ctx.momentum_strength = signal.strength

        if not signal.is_buy:
            ind = signal.indicators
            reason = self._format_rejection(ind)
            logger.info("Gate 1 (%s): REJECTED by momentum filter.", ticker)
            self.telemetry.gate_reject(
                "momentum",
                ticker,
                {
                    "strength": signal.strength,
                    "indicators": ind,
                },
            )
            return GateResult(
                gate_name="momentum",
                status=GateStatus.REJECT,
                ticker=ticker,
                confidence=signal.strength,
                reason=reason,
                data={"indicators": ind},
            )

        logger.info("Gate 1 (%s): PASSED (strength=%.2f)", ticker, signal.strength)
        self.telemetry.gate_pass(
            "momentum",
            ticker,
            {
                "strength": signal.strength,
                "indicators": signal.indicators,
            },
        )
        return GateResult(
            gate_name="momentum",
            status=GateStatus.PASS,
            ticker=ticker,
            confidence=signal.strength,
            data={"indicators": signal.indicators},
        )

    def _format_rejection(self, indicators: dict[str, Any]) -> str:
        """Format momentum rejection reason from indicators."""
        parts = []
        if indicators.get("rsi", 50) > 70:
            parts.append(f"RSI overbought ({indicators.get('rsi'):.1f})")
        if indicators.get("macd_histogram", 0) < 0:
            parts.append("MACD bearish")
        if indicators.get("volume_ratio", 1.0) < 0.8:
            parts.append(f"Low volume ({indicators.get('volume_ratio'):.2f}x)")
        return "; ".join(parts) if parts else "Below momentum threshold"


class Gate15Debate:
    """
    Gate 1.5: Bull/Bear Debate.

    Multi-perspective analysis based on UCLA/MIT TradingAgents research.
    Simulates adversarial debate between bullish and bearish viewpoints.
    """

    def __init__(self, debate_moderator: Any, telemetry: Any, debate_available: bool):
        self.debate_moderator = debate_moderator
        self.telemetry = telemetry
        self.debate_available = debate_available

    def evaluate(self, ticker: str, ctx: TradeContext) -> GateResult:
        """
        Conduct bull/bear debate on the trade.

        Returns:
            GateResult with debate outcome
        """
        if not self.debate_moderator or not self.debate_available:
            return GateResult(
                gate_name="debate",
                status=GateStatus.SKIP,
                ticker=ticker,
                reason="Debate module not available",
            )

        try:
            indicators = ctx.momentum_signal.indicators if ctx.momentum_signal else {}
            market_data = {
                "price": indicators.get("close", 0),
                "rsi": indicators.get("rsi", 50),
                "macd_histogram": indicators.get("macd_histogram", 0),
                "volume_ratio": indicators.get("volume_ratio", 1.0),
                "trend": "BULLISH"
                if ctx.momentum_signal and ctx.momentum_signal.is_buy
                else "BEARISH",
                "ma_50": indicators.get("sma_20", 0),
                "ma_200": indicators.get("sma_50", 0),
            }

            outcome = self.debate_moderator.conduct_debate(ticker, market_data)
            ctx.debate_outcome = outcome

            logger.info(
                "Gate 1.5 (%s): Debate - Winner: %s, Rec: %s, Confidence: %.2f",
                ticker,
                outcome.winner,
                outcome.final_recommendation,
                outcome.confidence,
            )

            self.telemetry.record(
                event_type="debate.outcome",
                ticker=ticker,
                status="completed",
                payload={
                    "winner": outcome.winner,
                    "recommendation": outcome.final_recommendation,
                    "confidence": outcome.confidence,
                    "bull_conviction": outcome.bull_position.conviction,
                    "bear_conviction": outcome.bear_position.conviction,
                },
            )

            # Strong bear rejection
            if outcome.winner == "BEAR" and outcome.confidence > 0.7:
                logger.info("Gate 1.5 (%s): REJECTED by Bear - %s", ticker, outcome.dissenting_view)
                self.telemetry.gate_reject(
                    "debate",
                    ticker,
                    {
                        "winner": "BEAR",
                        "confidence": outcome.confidence,
                    },
                )
                return GateResult(
                    gate_name="debate",
                    status=GateStatus.REJECT,
                    ticker=ticker,
                    confidence=outcome.confidence,
                    reason=outcome.dissenting_view,
                )

            return GateResult(
                gate_name="debate",
                status=GateStatus.PASS,
                ticker=ticker,
                confidence=outcome.confidence,
                data={"winner": outcome.winner, "recommendation": outcome.final_recommendation},
            )

        except Exception as e:
            logger.warning("Gate 1.5 (%s): Debate failed, continuing: %s", ticker, e)
            return GateResult(
                gate_name="debate",
                status=GateStatus.SKIP,
                ticker=ticker,
                reason=f"Debate failed: {e}",
            )


class Gate2RLFilter:
    """
    Gate 2: Reinforcement Learning filter.

    Uses trained RL model to predict trade quality based on market features.
    Can be disabled in simplification mode.
    """

    def __init__(
        self,
        rl_filter: Any,
        failure_manager: Any,
        telemetry: Any,
        rl_filter_enabled: bool,
    ):
        self.rl_filter = rl_filter
        self.failure_manager = failure_manager
        self.telemetry = telemetry
        self.rl_filter_enabled = rl_filter_enabled

    def evaluate(self, ticker: str, ctx: TradeContext, rl_threshold: float) -> GateResult:
        """
        Run RL inference on market features.

        Args:
            ticker: Symbol to evaluate
            ctx: Trade context with momentum data
            rl_threshold: Minimum confidence threshold

        Returns:
            GateResult with RL decision
        """
        if not self.rl_filter_enabled or self.rl_filter is None:
            logger.info("Gate 2 (%s): SKIPPED - RL filter disabled", ticker)
            ctx.rl_decision = {"action": "BUY", "confidence": 1.0, "skipped": True}
            self.telemetry.gate_pass(
                "rl_filter", ticker, {"skipped": True, "reason": "simplification_mode"}
            )
            return GateResult(
                gate_name="rl_filter",
                status=GateStatus.SKIP,
                ticker=ticker,
                confidence=1.0,
                reason="RL filter disabled (simplification mode)",
            )

        indicators = ctx.momentum_signal.indicators if ctx.momentum_signal else {}
        outcome = self.failure_manager.run(
            gate="rl_filter",
            ticker=ticker,
            operation=lambda: self.rl_filter.predict(indicators),
        )

        if not outcome.ok:
            logger.error("Gate 2 (%s): RL filter failed: %s", ticker, outcome.failure.error)
            return GateResult(
                gate_name="rl_filter",
                status=GateStatus.ERROR,
                ticker=ticker,
                reason=str(outcome.failure.error),
            )

        decision = outcome.result
        ctx.rl_decision = decision
        confidence = decision.get("confidence", 0.0)

        if confidence < rl_threshold:
            logger.info(
                "Gate 2 (%s): REJECTED (confidence=%.2f < %.2f)", ticker, confidence, rl_threshold
            )
            self.telemetry.gate_reject("rl_filter", ticker, decision)
            return GateResult(
                gate_name="rl_filter",
                status=GateStatus.REJECT,
                ticker=ticker,
                confidence=confidence,
                reason=f"Confidence {confidence:.2f} below threshold {rl_threshold:.2f}",
            )

        logger.info(
            "Gate 2 (%s): PASSED (action=%s, confidence=%.2f)",
            ticker,
            decision.get("action"),
            confidence,
        )
        self.telemetry.gate_pass("rl_filter", ticker, decision)
        return GateResult(
            gate_name="rl_filter",
            status=GateStatus.PASS,
            ticker=ticker,
            confidence=confidence,
            data=decision,
        )


class Gate3Sentiment:
    """
    Gate 3: LLM sentiment analysis.

    Uses LLM to analyze news and market sentiment.
    Budget-aware with bias cache for efficiency.
    """

    def __init__(
        self,
        llm_agent: Any,
        bias_provider: Any,
        budget_controller: Any,
        playwright_scraper: Any,
        failure_manager: Any,
        telemetry: Any,
        llm_sentiment_enabled: bool,
    ):
        self.llm_agent = llm_agent
        self.bias_provider = bias_provider
        self.budget_controller = budget_controller
        self.playwright_scraper = playwright_scraper
        self.failure_manager = failure_manager
        self.telemetry = telemetry
        self.llm_sentiment_enabled = llm_sentiment_enabled

    def evaluate(self, ticker: str, ctx: TradeContext, session_profile: dict | None) -> GateResult:
        """
        Analyze sentiment from LLM and web sources.

        Returns:
            GateResult with sentiment score
        """
        if not self.llm_sentiment_enabled or self.llm_agent is None:
            logger.info("Gate 3 (%s): SKIPPED - LLM sentiment disabled", ticker)
            self.telemetry.gate_pass("llm_sentiment", ticker, {"skipped": True})
            return GateResult(
                gate_name="llm_sentiment",
                status=GateStatus.SKIP,
                ticker=ticker,
                reason="LLM sentiment disabled (simplification mode)",
            )

        neg_threshold = float(os.getenv("LLM_NEGATIVE_SENTIMENT_THRESHOLD", "-0.2"))
        session_type = (session_profile or {}).get("session_type")
        if session_type == "weekend":
            neg_threshold = float(os.getenv("WEEKEND_SENTIMENT_FLOOR", "-0.1"))

        # Try Playwright scraping first
        playwright_score = self._get_playwright_sentiment(ticker)

        # Try bias cache
        if self.bias_provider:
            bias_snapshot = self.bias_provider.get_bias(ticker)
            if bias_snapshot:
                return self._evaluate_bias(ticker, bias_snapshot, neg_threshold, ctx)

        # Fall back to LLM
        return self._evaluate_llm(ticker, ctx, neg_threshold, playwright_score)

    def _get_playwright_sentiment(self, ticker: str) -> float:
        """Scrape sentiment from web sources."""
        try:
            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                self.playwright_scraper.scrape_all([ticker])
            )
            if ticker in result and result[ticker].total_mentions > 0:
                score = result[ticker].weighted_score
                logger.info("Gate 3 (%s): Playwright sentiment=%.2f", ticker, score)
                return score
        except Exception as e:
            logger.warning("Gate 3 (%s): Playwright failed: %s", ticker, e)
        return 0.0

    def _evaluate_bias(
        self, ticker: str, bias: Any, threshold: float, ctx: TradeContext
    ) -> GateResult:
        """Evaluate using cached bias score."""
        score = bias.score
        ctx.sentiment_score = score

        if score < threshold:
            logger.info("Gate 3 (%s): REJECTED by bias (score=%.2f)", ticker, score)
            self.telemetry.gate_reject("llm", ticker, {"score": score, "reason": bias.reason})
            return GateResult(
                gate_name="llm_sentiment",
                status=GateStatus.REJECT,
                ticker=ticker,
                confidence=abs(score),
                reason=f"Negative sentiment: {bias.reason}",
            )

        logger.info("Gate 3 (%s): PASSED via bias (sentiment=%.2f)", ticker, score)
        self.telemetry.gate_pass("llm", ticker, {"score": score, "source": "bias_store"})
        return GateResult(
            gate_name="llm_sentiment",
            status=GateStatus.PASS,
            ticker=ticker,
            confidence=abs(score),
            data={"score": score, "source": "bias_store"},
        )

    def _evaluate_llm(
        self, ticker: str, ctx: TradeContext, threshold: float, playwright_score: float
    ) -> GateResult:
        """Call LLM for sentiment analysis."""
        llm_model = getattr(self.llm_agent, "model_name", None)

        if not self.budget_controller.can_afford_execution(model=llm_model):
            logger.info("Gate 3 (%s): Skipped to protect budget", ticker)
            return GateResult(
                gate_name="llm_sentiment",
                status=GateStatus.SKIP,
                ticker=ticker,
                reason="Budget protection",
            )

        indicators = ctx.momentum_signal.indicators if ctx.momentum_signal else {}
        outcome = self.failure_manager.run(
            gate="llm",
            ticker=ticker,
            operation=lambda: self.llm_agent.analyze_news(ticker, indicators),
            retry=2,
        )

        if not outcome.ok:
            logger.warning("Gate 3 (%s): LLM error, falling back", ticker)
            return GateResult(
                gate_name="llm_sentiment",
                status=GateStatus.SKIP,
                ticker=ticker,
                reason=f"LLM error: {outcome.failure.error}",
            )

        llm_result = outcome.result
        llm_score = llm_result.get("score", 0.0)

        # Blend with playwright
        if playwright_score != 0.0:
            weight = float(os.getenv("PLAYWRIGHT_SENTIMENT_WEIGHT", "0.3"))
            sentiment_score = llm_score * (1 - weight) + playwright_score * weight
        else:
            sentiment_score = llm_score

        ctx.sentiment_score = sentiment_score
        self.budget_controller.log_spend(llm_result.get("cost", 0.0))

        if sentiment_score < threshold:
            logger.info("Gate 3 (%s): REJECTED (score=%.2f)", ticker, sentiment_score)
            self.telemetry.gate_reject("llm", ticker, llm_result)
            return GateResult(
                gate_name="llm_sentiment",
                status=GateStatus.REJECT,
                ticker=ticker,
                confidence=abs(sentiment_score),
                reason=llm_result.get("reason", "Negative sentiment"),
            )

        logger.info("Gate 3 (%s): PASSED (sentiment=%.2f)", ticker, sentiment_score)
        self.telemetry.gate_pass("llm", ticker, llm_result)
        return GateResult(
            gate_name="llm_sentiment",
            status=GateStatus.PASS,
            ticker=ticker,
            confidence=abs(sentiment_score),
            data={"score": sentiment_score},
        )


class Gate35Introspection:
    """
    Gate 3.5: Introspective awareness.

    Combines self-consistency, epistemic uncertainty, and self-critique.
    Based on Anthropic research on AI self-awareness.
    """

    def __init__(
        self,
        introspective_council: Any,
        uncertainty_tracker: Any,
        telemetry: Any,
        introspection_available: bool,
    ):
        self.introspective_council = introspective_council
        self.uncertainty_tracker = uncertainty_tracker
        self.telemetry = telemetry
        self.introspection_available = introspection_available

    def evaluate(self, ticker: str, ctx: TradeContext) -> GateResult:
        """
        Run introspective analysis on the trade decision.

        Returns:
            GateResult with position multiplier if PASS
        """
        if not self.introspective_council or not self.introspection_available:
            return GateResult(
                gate_name="introspection",
                status=GateStatus.SKIP,
                ticker=ticker,
                reason="Introspection not available",
            )

        try:
            import asyncio

            indicators = ctx.momentum_signal.indicators if ctx.momentum_signal else {}
            market_data = {
                "symbol": ticker,
                "momentum_strength": ctx.momentum_strength,
                "rl_confidence": ctx.rl_decision.get("confidence", 0.0),
                "sentiment_score": ctx.sentiment_score,
                "indicators": indicators,
            }

            result = asyncio.get_event_loop().run_until_complete(
                self.introspective_council.analyze_trade(symbol=ticker, market_data=market_data)
            )

            self.telemetry.record(
                event_type="gate.introspection",
                ticker=ticker,
                status="pass" if result.execute else "reject",
                payload={
                    "combined_confidence": result.combined_confidence,
                    "epistemic_uncertainty": result.epistemic_uncertainty,
                    "position_multiplier": result.position_multiplier,
                },
            )

            if not result.execute:
                logger.info(
                    "Gate 3.5 (%s): REJECTED (confidence=%.2f, state=%s)",
                    ticker,
                    result.combined_confidence,
                    result.introspection_state.value,
                )
                return GateResult(
                    gate_name="introspection",
                    status=GateStatus.REJECT,
                    ticker=ticker,
                    confidence=result.combined_confidence,
                    reason=f"Introspection state: {result.introspection_state.value}",
                )

            ctx.introspection_multiplier = result.position_multiplier
            logger.info(
                "Gate 3.5 (%s): PASSED (confidence=%.2f, multiplier=%.2f)",
                ticker,
                result.combined_confidence,
                result.position_multiplier,
            )
            return GateResult(
                gate_name="introspection",
                status=GateStatus.PASS,
                ticker=ticker,
                confidence=result.combined_confidence,
                data={"position_multiplier": result.position_multiplier},
            )

        except Exception as e:
            logger.warning("Gate 3.5 (%s): Failed, continuing: %s", ticker, e)
            return GateResult(
                gate_name="introspection",
                status=GateStatus.SKIP,
                ticker=ticker,
                reason=f"Introspection failed: {e}",
            )


class Gate4Risk:
    """
    Gate 4: Risk sizing and execution.

    Calculates position size based on account equity, signal strength,
    and risk parameters. Final gate before execution.
    """

    def __init__(
        self,
        risk_manager: Any,
        executor: Any,
        failure_manager: Any,
        telemetry: Any,
    ):
        self.risk_manager = risk_manager
        self.executor = executor
        self.failure_manager = failure_manager
        self.telemetry = telemetry

    def evaluate(self, ticker: str, ctx: TradeContext, allocation_cap: float) -> GateResult:
        """
        Calculate risk-adjusted position size.

        Returns:
            GateResult with order_size if PASS
        """
        outcome = self.failure_manager.run(
            gate="risk",
            ticker=ticker,
            operation=lambda: self.risk_manager.calculate_size(
                ticker=ticker,
                account_equity=self.executor.account_equity,
                signal_strength=ctx.momentum_strength,
                rl_confidence=ctx.rl_decision.get("confidence", 0.0),
                sentiment_score=ctx.sentiment_score,
                multiplier=ctx.rl_decision.get("suggested_multiplier", 1.0),
                current_price=ctx.current_price,
                hist=ctx.hist,
                market_regime=ctx.regime_snapshot.get("label"),
                allocation_cap=allocation_cap * ctx.introspection_multiplier,
            ),
            event_type="gate.risk",
        )

        if not outcome.ok:
            logger.error("Gate 4 (%s): Risk sizing failed: %s", ticker, outcome.failure.error)
            return GateResult(
                gate_name="risk",
                status=GateStatus.ERROR,
                ticker=ticker,
                reason=str(outcome.failure.error),
            )

        order_size = outcome.result

        if order_size <= 0:
            logger.info("Gate 4 (%s): REJECTED (position size = 0)", ticker)
            self.telemetry.gate_reject(
                "risk",
                ticker,
                {
                    "order_size": order_size,
                    "account_equity": self.executor.account_equity,
                },
            )
            return GateResult(
                gate_name="risk",
                status=GateStatus.REJECT,
                ticker=ticker,
                reason="Position size calculated as 0",
            )

        logger.info("Gate 4 (%s): PASSED (size=$%.2f)", ticker, order_size)
        self.telemetry.gate_pass(
            "risk",
            ticker,
            {
                "order_size": order_size,
                "account_equity": self.executor.account_equity,
            },
        )
        return GateResult(
            gate_name="risk",
            status=GateStatus.PASS,
            ticker=ticker,
            confidence=ctx.rl_decision.get("confidence", 0.0),
            data={"order_size": order_size},
        )


class TradingGatePipeline:
    """
    Orchestrates the full trading gate pipeline.

    LLM-friendly: Each gate is a separate call with clear pass/fail.
    Total pipeline is ~50 lines, not 866.
    """

    def __init__(
        self,
        gate0: Gate0Psychology,
        gate1: Gate1Momentum,
        gate15: Gate15Debate,
        gate2: Gate2RLFilter,
        gate3: Gate3Sentiment,
        gate35: Gate35Introspection,
        gate4: Gate4Risk,
        checkpointer: Any | None = None,
    ):
        self.gate0 = gate0
        self.gate1 = gate1
        self.gate15 = gate15
        self.gate2 = gate2
        self.gate3 = gate3
        self.gate35 = gate35
        self.gate4 = gate4
        # Checkpointing for fault tolerance
        self.checkpointer = checkpointer
        if CHECKPOINTING_AVAILABLE and checkpointer is None:
            try:
                self.checkpointer = get_checkpointer()
            except Exception as e:
                logger.warning("Failed to initialize checkpointer: %s", e)

    def _checkpoint(
        self,
        thread_id: str | None,
        gate_index: float,
        gate_name: str,
        ticker: str,
        ctx: TradeContext,
        results: list[GateResult],
        status: str = "success",
    ) -> None:
        """Save checkpoint if checkpointing is enabled and gate is critical."""
        if not thread_id or not self.checkpointer:
            return
        if not should_checkpoint(gate_index):
            return
        try:
            self.checkpointer.save_checkpoint(
                thread_id=thread_id,
                gate_index=gate_index,
                gate_name=gate_name,
                ticker=ticker,
                context=ctx,
                results=results,
                status=status,
            )
        except Exception as e:
            logger.warning("Checkpoint save failed: %s", e)

    def run(
        self,
        ticker: str,
        rl_threshold: float,
        session_profile: dict | None = None,
        allocation_cap: float = 0.0,
        thread_id: str | None = None,
    ) -> tuple[bool, TradeContext, list[GateResult]]:
        """
        Run the full gate pipeline for a ticker.

        Returns:
            (success, context, gate_results) tuple
        """
        ctx = TradeContext(ticker=ticker)
        results: list[GateResult] = []

        # Gate 0: Psychology (with latency tracking)
        result = _timed_gate_execution(self.gate0.evaluate, ticker)
        results.append(result)
        _trace_gate(
            "psychology", ticker, {"gate": 0, "latency_ms": result.execution_time_ms}, result
        )
        if result.rejected:
            return False, ctx, results

        # Gate 1: Momentum (with latency tracking)
        result = _timed_gate_execution(self.gate1.evaluate, ticker, ctx)
        results.append(result)
        _trace_gate(
            "momentum",
            ticker,
            {
                "gate": 1,
                "has_momentum": ctx.momentum_signal is not None,
                "latency_ms": result.execution_time_ms,
            },
            result,
        )
        self._checkpoint(thread_id, 1, "momentum", ticker, ctx, results)
        if result.rejected or result.status == GateStatus.ERROR:
            return False, ctx, results

        # Gate 1.5: Debate (with latency tracking)
        result = _timed_gate_execution(self.gate15.evaluate, ticker, ctx)
        results.append(result)
        _trace_gate("debate", ticker, {"gate": 1.5, "latency_ms": result.execution_time_ms}, result)
        if result.rejected:
            return False, ctx, results

        # Gate 2: RL Filter (with latency tracking)
        result = _timed_gate_execution(self.gate2.evaluate, ticker, ctx, rl_threshold)
        results.append(result)
        _trace_gate(
            "rl_filter",
            ticker,
            {"gate": 2, "rl_threshold": rl_threshold, "latency_ms": result.execution_time_ms},
            result,
        )
        if result.rejected or result.status == GateStatus.ERROR:
            return False, ctx, results

        # Gate 3: Sentiment (with latency tracking)
        result = _timed_gate_execution(self.gate3.evaluate, ticker, ctx, session_profile)
        results.append(result)
        _trace_gate(
            "sentiment",
            ticker,
            {
                "gate": 3,
                "has_session": session_profile is not None,
                "latency_ms": result.execution_time_ms,
            },
            result,
        )
        self._checkpoint(thread_id, 3, "sentiment", ticker, ctx, results)
        if result.rejected:
            return False, ctx, results

        # Gate 3.5: Introspection (with latency tracking)
        result = _timed_gate_execution(self.gate35.evaluate, ticker, ctx)
        results.append(result)
        _trace_gate(
            "introspection", ticker, {"gate": 3.5, "latency_ms": result.execution_time_ms}, result
        )
        if result.rejected:
            return False, ctx, results

        # Gate 4: Risk (with latency tracking)
        result = _timed_gate_execution(self.gate4.evaluate, ticker, ctx, allocation_cap)
        results.append(result)
        _trace_gate(
            "risk",
            ticker,
            {"gate": 4, "allocation_cap": allocation_cap, "latency_ms": result.execution_time_ms},
            result,
        )
        self._checkpoint(thread_id, 4, "risk", ticker, ctx, results)
        if result.rejected or result.status == GateStatus.ERROR:
            return False, ctx, results

        return True, ctx, results


class Gate5Execution:
    """
    Gate 5: Trade execution via gateway.

    Final gate that validates through TradeGateway and executes the order.
    Handles order placement, stop-loss, and verification.
    """

    def __init__(
        self,
        trade_gateway: Any,
        smart_dca: Any,
        executor: Any,
        risk_manager: Any,
        position_manager: Any,
        trade_verifier: Any,
        failure_manager: Any,
        telemetry: Any,
    ):
        self.trade_gateway = trade_gateway
        self.smart_dca = smart_dca
        self.executor = executor
        self.risk_manager = risk_manager
        self.position_manager = position_manager
        self.trade_verifier = trade_verifier
        self.failure_manager = failure_manager
        self.telemetry = telemetry

    def execute(
        self,
        ticker: str,
        ctx: TradeContext,
        order_size: float,
    ) -> GateResult:
        """
        Execute the trade through the gateway.

        Returns:
            GateResult with order details if successful
        """
        from src.risk.trade_gateway import RejectionReason, TradeRequest

        trade_request = TradeRequest(
            symbol=ticker,
            side="buy",
            notional=order_size,
            source="orchestrator",
        )

        gateway_decision = self.trade_gateway.evaluate(trade_request)

        if not gateway_decision.approved:
            rejection_reasons = [r.value for r in gateway_decision.rejection_reasons]
            # Release allocation unless it's a batch minimum issue
            if RejectionReason.MINIMUM_BATCH_NOT_MET not in gateway_decision.rejection_reasons:
                if ctx.allocation_plan:
                    self.smart_dca.release(ctx.allocation_plan.bucket, order_size)

            logger.warning("Gate 5 (%s): REJECTED by gateway - %s", ticker, rejection_reasons)
            self.telemetry.gate_reject(
                "gateway",
                ticker,
                {
                    "rejection_reasons": rejection_reasons,
                    "risk_score": gateway_decision.risk_score,
                },
            )
            return GateResult(
                gate_name="execution",
                status=GateStatus.REJECT,
                ticker=ticker,
                reason=f"Gateway rejection: {rejection_reasons}",
            )

        # Execute the order
        order_outcome = self.failure_manager.run(
            gate="execution.order",
            ticker=ticker,
            operation=lambda: self.trade_gateway.execute(gateway_decision),
            event_type="execution.order",
        )

        if not order_outcome.ok:
            if ctx.allocation_plan:
                self.smart_dca.release(ctx.allocation_plan.bucket, order_size)
            logger.error("Gate 5 (%s): Execution failed: %s", ticker, order_outcome.failure.error)
            return GateResult(
                gate_name="execution",
                status=GateStatus.ERROR,
                ticker=ticker,
                reason=str(order_outcome.failure.error),
            )

        order = order_outcome.result

        # Place stop-loss
        self._place_stop_loss(ticker, ctx, order, order_size)

        # Track position entry
        self._track_entry(ticker, ctx)

        # Verify trade if enabled
        self._verify_trade(ticker, ctx, order, order_size)

        logger.info("Gate 5 (%s): EXECUTED (order_id=%s)", ticker, order.get("id"))
        self.telemetry.gate_pass(
            "execution",
            ticker,
            {
                "order_id": order.get("id"),
                "order_size": order_size,
            },
        )

        return GateResult(
            gate_name="execution",
            status=GateStatus.PASS,
            ticker=ticker,
            data={"order": order, "order_size": order_size},
        )

    def _place_stop_loss(
        self,
        ticker: str,
        ctx: TradeContext,
        order: dict,
        order_size: float,
    ) -> None:
        """Place ATR-based stop-loss."""
        try:
            if ctx.current_price and ctx.current_price > 0:
                stop_price = self.risk_manager.calculate_stop_loss(
                    ticker=ticker,
                    entry_price=float(ctx.current_price),
                    direction="long",
                    hist=ctx.hist,
                )
                qty = order.get("filled_qty") or (order_size / float(ctx.current_price))
                stop_order = self.executor.set_stop_loss(ticker, float(qty), float(stop_price))
                self.telemetry.record(
                    event_type="execution.stop",
                    ticker=ticker,
                    status="submitted",
                    payload={
                        "stop": stop_order,
                        "atr_pct": ctx.atr_pct,
                        "atr_multiplier": float(os.getenv("ATR_STOP_MULTIPLIER", "2.0")),
                    },
                )
        except Exception as exc:
            logger.info("Stop-loss placement skipped for %s: %s", ticker, exc)

    def _track_entry(self, ticker: str, ctx: TradeContext) -> None:
        """Track position entry for DiscoRL learning."""
        try:
            indicators = ctx.momentum_signal.indicators if ctx.momentum_signal else {}
            self.position_manager.track_entry(
                symbol=ticker,
                entry_date=datetime.now(timezone.utc),
                entry_features=indicators,
            )
            logger.debug("Tracked entry for %s with features", ticker)
        except Exception as exc:
            logger.warning("Failed to track entry for %s: %s", ticker, exc)

    def _verify_trade(
        self,
        ticker: str,
        ctx: TradeContext,
        order: dict,
        order_size: float,
    ) -> None:
        """Verify trade via Playwright MCP."""
        verify_trades = os.getenv("ENABLE_TRADE_VERIFICATION", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        if not verify_trades or not order.get("id"):
            return

        try:
            import asyncio

            order_id = order.get("id", "")
            order_qty = (
                order.get("filled_qty")
                or order.get("qty")
                or (order_size / float(ctx.current_price or 1))
            )
            verification = asyncio.get_event_loop().run_until_complete(
                self.trade_verifier.verify_order_execution(
                    order_id=str(order_id),
                    expected_symbol=ticker,
                    expected_qty=float(order_qty),
                    expected_side="buy",
                    api_response=order,
                )
            )
            self.telemetry.record(
                event_type="execution.verification",
                ticker=ticker,
                status="verified" if verification.verified else "unverified",
                payload={
                    "order_id": order_id,
                    "verified": verification.verified,
                    "screenshot": str(verification.screenshot_path)
                    if verification.screenshot_path
                    else None,
                    "errors": verification.errors,
                },
            )
            if verification.verified:
                logger.info("Trade verification PASSED for %s (order=%s)", ticker, order_id)
            else:
                logger.warning("Trade verification FAILED for %s: %s", ticker, verification.errors)
        except Exception as verify_exc:
            logger.warning("Trade verification skipped for %s: %s", ticker, verify_exc)
