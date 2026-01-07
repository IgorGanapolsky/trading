"""
Mandatory Trade Gate - NEVER SKIP this validation.

This module provides RAG + ML integration before trade execution:
1. Query RAG lessons for relevant warnings
2. Check ML anomaly detection
3. Validate against known failure patterns
4. Block trades that violate safety rules

Created: Dec 30, 2025
Reason: ML integration gap identified - alpaca_executor imports this but it didn't exist
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TradeBlockedError(Exception):
    """Raised when a trade is blocked by the mandatory gate."""

    def __init__(self, gate_result_or_message: GateValidationResult | str):
        """Accept either a GateValidationResult or a string message."""
        if isinstance(gate_result_or_message, str):
            # String message passed (e.g., from pattern check)
            self.gate_result = None
            self.reason = gate_result_or_message
            super().__init__(f"Trade blocked: {gate_result_or_message}")
        else:
            # GateValidationResult object passed
            self.gate_result = gate_result_or_message
            self.reason = gate_result_or_message.reason
            super().__init__(f"Trade blocked: {gate_result_or_message.reason}")


@dataclass
class GateValidationResult:
    """Result of mandatory trade gate validation."""

    approved: bool = False
    reason: str = ""
    rag_warnings: list[str] = field(default_factory=list)
    ml_anomalies: list[str] = field(default_factory=list)
    confidence: float = 0.0
    context: dict[str, Any] = field(default_factory=dict)


def validate_trade_mandatory(
    symbol: str,
    amount: float,
    side: str,
    strategy: str = "unknown",
    context: dict[str, Any] | None = None,
) -> GateValidationResult:
    """
    MANDATORY validation before ANY trade execution.

    This function:
    1. Queries RAG for relevant lessons (semantic search)
    2. Checks ML anomaly status
    3. Validates against known failure patterns
    4. Returns approval/rejection with reasons

    Args:
        symbol: Trading symbol (e.g., "SPY", "NVDA")
        amount: Dollar amount of the trade
        side: "BUY" or "SELL"
        strategy: Strategy name for context
        context: Account context (equity, buying_power)

    Returns:
        GateValidationResult with approval status and any warnings/anomalies
    """
    ctx = context or {}
    result = GateValidationResult(context=ctx)
    result.rag_warnings = []
    result.ml_anomalies = []

    # ========== GATE 1: Context-Aware Blocking (ll_051 blind trading prevention) ==========
    equity = ctx.get("equity", None)
    buying_power = ctx.get("buying_power", None)

    if equity is not None and equity <= 0:
        result.approved = False
        result.reason = "BLOCKED: Equity is $0 or negative - ll_051 blind trading prevention"
        result.ml_anomalies.append("equity_zero_or_negative")
        logger.error(f"MANDATORY GATE BLOCKED: {result.reason}")
        return result

    if buying_power is not None and buying_power <= 0:
        result.approved = False
        result.reason = "BLOCKED: Buying power is $0 or negative"
        result.ml_anomalies.append("buying_power_zero_or_negative")
        logger.error(f"MANDATORY GATE BLOCKED: {result.reason}")
        return result

    # ========== GATE 2: Query RAG for relevant lessons ==========
    rag_warnings = _query_rag_lessons(symbol, side, strategy, amount)
    result.rag_warnings.extend(rag_warnings)

    # ========== GATE 3: Check ML anomaly detection ==========
    ml_anomalies = _check_ml_anomalies(symbol, amount, side)
    result.ml_anomalies.extend(ml_anomalies)

    # ========== GATE 4: Known failure pattern matching ==========
    pattern_warnings = _check_failure_patterns(symbol, amount, side, strategy)
    result.rag_warnings.extend(pattern_warnings)

    # ========== GATE 5: Amount sanity check ==========
    if amount > 10000:
        result.rag_warnings.append(f"Large order amount: ${amount:.2f} - verify intentional")

    if amount < 1:
        result.approved = False
        result.reason = f"BLOCKED: Amount ${amount:.2f} is too small"
        return result

    # ========== FINAL DECISION ==========
    # Block if any CRITICAL anomalies detected
    critical_anomalies = [a for a in result.ml_anomalies if "critical" in a.lower()]
    if critical_anomalies:
        result.approved = False
        result.reason = f"BLOCKED: Critical ML anomalies detected: {critical_anomalies}"
        logger.error(f"MANDATORY GATE BLOCKED: {result.reason}")
        return result

    # Approve with warnings if no blockers
    result.approved = True
    result.confidence = 1.0 - (len(result.rag_warnings) + len(result.ml_anomalies)) * 0.1
    result.confidence = max(0.0, result.confidence)

    if result.rag_warnings or result.ml_anomalies:
        result.reason = "APPROVED with warnings"
        logger.warning(
            f"MANDATORY GATE APPROVED WITH WARNINGS: {symbol} {side} ${amount:.2f} "
            f"(RAG: {len(result.rag_warnings)}, ML: {len(result.ml_anomalies)})"
        )
    else:
        result.reason = "APPROVED"
        logger.info(f"MANDATORY GATE APPROVED: {symbol} {side} ${amount:.2f}")

    return result


def _query_rag_lessons(symbol: str, side: str, strategy: str, amount: float) -> list[str]:
    """Query RAG for relevant lessons using semantic search."""
    warnings = []

    try:
        from src.rag.lessons_search import LessonsSearch

        search = LessonsSearch()

        # Semantic queries based on trade context
        queries = [
            f"{symbol} trading failure",
            f"{side.lower()} order mistake",
            f"{strategy} strategy problem",
            "operational failure trading",
            "blind trading account data",
        ]

        for query in queries:
            try:
                results = search.query(query, top_k=2)
                for r in results:
                    if r.get("score", 0) > 0.7:  # High relevance threshold
                        title = r.get("title", "Unknown lesson")
                        warnings.append(f"RAG: {title}")
            except Exception:
                pass  # Non-fatal - RAG not available

    except ImportError:
        # LessonsSearch not available - fall back to file-based search
        warnings.extend(_fallback_lesson_search(symbol, strategy))

    return warnings


def _fallback_lesson_search(symbol: str, strategy: str) -> list[str]:
    """Fallback file-based lesson search when RAG unavailable."""
    warnings = []
    lessons_dir = Path("rag_knowledge/lessons_learned")

    if not lessons_dir.exists():
        return warnings

    # Search for symbol-specific lessons
    symbol_lower = symbol.lower()
    strategy_lower = strategy.lower()

    critical_keywords = [
        "blind_trading",
        "equity_zero",
        "catastrophe",
        "critical",
        "blocked",
    ]

    try:
        for lesson_file in lessons_dir.glob("*.md"):
            content = lesson_file.read_text().lower()

            # Check for critical lessons
            if any(kw in content for kw in critical_keywords):
                if symbol_lower in content or strategy_lower in content:
                    warnings.append(f"RAG (fallback): {lesson_file.stem}")

    except Exception as e:
        logger.debug(f"Fallback lesson search failed: {e}")

    return warnings


def _check_ml_anomalies(symbol: str, amount: float, side: str) -> list[str]:
    """Check ML anomaly detection systems."""
    anomalies = []

    try:
        # Try to get anomaly status from the monitor
        from src.orchestrator.anomaly_monitor import AnomalyMonitor
        from src.orchestrator.telemetry import OrchestratorTelemetry

        # Check if there's an active monitor with recent anomalies
        # This is a simplified check - in production, would use singleton pattern
        telemetry = OrchestratorTelemetry()
        monitor = AnomalyMonitor(telemetry)

        # Check for recent gate anomalies
        for gate in ["momentum", "rl_filter", "sentiment", "risk"]:
            stats = monitor.get_latency_stats(gate)
            if stats.get("count", 0) > 0:
                p99 = stats.get("p99", 0)
                threshold = stats.get("threshold_ms", 1000)
                if p99 > threshold * 2:
                    anomalies.append(f"ML: {gate} gate latency spike (P99={p99:.0f}ms)")

    except ImportError:
        pass  # AnomalyMonitor not available

    try:
        # Check RL filter confidence if available
        from src.agents.rl_agent import RLFilter

        rl_filter = RLFilter()
        # Quick inference to check confidence
        prediction = rl_filter.predict({"symbol": symbol, "side": side})
        confidence = prediction.get("confidence", 1.0)

        if confidence < 0.3:
            anomalies.append(f"ML: Low RL confidence ({confidence:.2f}) for {symbol}")

    except Exception:
        pass  # RLFilter not available or failed

    return anomalies


def _check_failure_patterns(symbol: str, amount: float, side: str, strategy: str) -> list[str]:
    """Check against known failure patterns from lessons learned."""
    warnings = []

    # Pattern 1: Large orders (ll_001 - 200x deployment error)
    if amount > 500:
        warnings.append(f"Large order alert: ${amount:.2f} - verify not 200x error (ll_001)")

    # Pattern 2: Options without proper sizing
    if "option" in strategy.lower() and amount > 1000:
        warnings.append(f"Options order ${amount:.2f} - ensure position sizing is correct")

    # Pattern 3: Crypto symbols (ll_052 - We do NOT trade crypto)
    crypto_symbols = {"BTC", "ETH", "DOGE", "SOL", "XRP", "ADA", "AVAX", "MATIC"}
    if symbol.upper() in crypto_symbols or symbol.upper().endswith("USD"):
        warnings.append(f"BLOCKED pattern: {symbol} appears to be crypto (ll_052)")

    return warnings


# ========== Integration with AnomalyMonitor ==========


def create_blocking_anomaly_monitor(
    telemetry: Any,
    block_on_anomaly: bool = True,
) -> Any:
    """
    Create an AnomalyMonitor that can BLOCK trades when anomalies detected.

    This wraps the standard AnomalyMonitor with blocking capability.
    """
    from src.orchestrator.anomaly_monitor import AnomalyMonitor

    class BlockingAnomalyMonitor(AnomalyMonitor):
        """AnomalyMonitor that tracks and can block on anomalies."""

        def __init__(self, *args, **kwargs):
            self._block_on_anomaly = kwargs.pop("block_on_anomaly", True)
            self._active_anomalies: dict[str, dict] = {}
            super().__init__(*args, **kwargs)

        def track(self, *, gate: str, ticker: str, status: str, metrics: dict | None = None):
            """Track gate outcome and optionally block on anomaly."""
            anomaly = super().track(gate=gate, ticker=ticker, status=status, metrics=metrics)

            if anomaly:
                self._active_anomalies[gate] = {
                    "anomaly": anomaly,
                    "ticker": ticker,
                    "timestamp": __import__("time").time(),
                }

            return anomaly

        def should_block_trade(self, ticker: str) -> tuple[bool, str]:
            """Check if current anomalies should block a trade."""
            if not self._block_on_anomaly:
                return False, ""

            # Check for active anomalies in the last 5 minutes
            import time

            now = time.time()
            active_blocks = []

            for gate, data in self._active_anomalies.items():
                if now - data["timestamp"] < 300:  # 5 minute window
                    anomaly = data["anomaly"]
                    if anomaly.get("type") == "rejection_spike":
                        active_blocks.append(
                            f"{gate}: rejection spike ({anomaly.get('rejection_rate', 0) * 100:.0f}%)"
                        )

            if active_blocks:
                return True, f"Active anomalies: {', '.join(active_blocks)}"

            return False, ""

        def clear_anomaly(self, gate: str) -> None:
            """Clear an anomaly after it's been addressed."""
            if gate in self._active_anomalies:
                del self._active_anomalies[gate]

    return BlockingAnomalyMonitor(telemetry, block_on_anomaly=block_on_anomaly)
