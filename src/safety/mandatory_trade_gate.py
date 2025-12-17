"""
MANDATORY Trade Gate - RAG + ML Verification Before EVERY Trade

This gate MUST be called before ANY trade execution. It:
1. Queries RAG for relevant lessons learned
2. Runs ML anomaly detection on the order
3. BLOCKS the trade if either check fails
4. TRACES every decision to LangSmith for observability

Created: Dec 16, 2025
Updated: Dec 16, 2025 - Added LangSmith tracing
Purpose: Prevent repeated mistakes by learning from RAG and ML

NEVER BYPASS THIS GATE. If you need to bypass, add a lesson learned first.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# LangSmith tracing - import the observability module
try:
    from src.observability.langsmith_tracer import TraceType, get_tracer
    LANGSMITH_AVAILABLE = True
    logger.info("LangSmith tracing available for trade gate")
except ImportError:
    LANGSMITH_AVAILABLE = False
    logger.warning("LangSmith not available - gate decisions will only be logged locally")

# Hindsight Agentic Memory - 91% accuracy on LongMemEval (Dec 2025)
# Provides: retain/recall/reflect API with confidence-scored opinions
try:
    from src.rag.hindsight_adapter import HindsightAdapter, is_hindsight_available  # noqa: F401
    HINDSIGHT_AVAILABLE = True
except ImportError:
    HINDSIGHT_AVAILABLE = False
    HindsightAdapter = None  # type: ignore

# Gate configuration
GATE_ENABLED = os.getenv("MANDATORY_TRADE_GATE", "true").lower() in {"1", "true", "yes"}
BLOCK_ON_RAG_WARNING = os.getenv("BLOCK_ON_RAG_WARNING", "true").lower() in {"1", "true", "yes"}
BLOCK_ON_ML_ANOMALY = os.getenv("BLOCK_ON_ML_ANOMALY", "true").lower() in {"1", "true", "yes"}


@dataclass
class GateResult:
    """Result of the mandatory trade gate check."""

    approved: bool
    reason: str
    rag_warnings: list[str]
    ml_anomalies: list[str]
    confidence: float
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "reason": self.reason,
            "rag_warnings": self.rag_warnings,
            "ml_anomalies": self.ml_anomalies,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


class MandatoryTradeGate:
    """
    MANDATORY gate that MUST be called before every trade.

    This gate:
    1. Verifies tracing is healthy (LangSmith operational)
    2. Queries RAG for lessons learned relevant to this trade
    3. Runs ML anomaly detection on the order parameters
    4. Returns APPROVED or BLOCKED with reasons
    5. Traces every decision to LangSmith

    Usage:
        gate = MandatoryTradeGate()
        result = gate.validate_trade(
            symbol="SPY",
            amount=100.0,
            side="BUY",
            strategy="equities"
        )

        if not result.approved:
            logger.error(f"Trade BLOCKED: {result.reason}")
            return None
    """

    def __init__(self):
        self.gate_log_path = Path("data/trade_gate_log.json")
        self.gate_log_path.parent.mkdir(parents=True, exist_ok=True)

        # Verify tracing health on initialization
        self.tracing_healthy = False
        self._verify_tracing_health()

        # Initialize RAG - CRITICAL for learning from past mistakes
        self.rag_available = False
        self.lessons_search = None
        try:
            from src.rag.lessons_search import LessonsSearch
            self.lessons_search = LessonsSearch()
            self.rag_available = True
            stats = self.lessons_search.get_stats()
            logger.info(f"RAG lessons search initialized: {stats['total_chunks']} chunks, {stats['total_files']} lessons")

            # Check for recent CRITICAL failures at startup
            self._check_recent_critical_failures()
        except Exception as e:
            logger.warning(f"RAG not available for trade gate: {e}")

        # Initialize ML Anomaly Detector
        self.ml_available = False
        self.anomaly_detector = None
        try:
            from src.ml.anomaly_detector import TradingAnomalyDetector
            self.anomaly_detector = TradingAnomalyDetector(
                expected_daily_amount=float(os.getenv("DAILY_INVESTMENT", "10.0")),
                portfolio_value=float(os.getenv("PORTFOLIO_VALUE", "100000.0")),
            )
            self.ml_available = True
            logger.info("ML anomaly detector initialized for trade gate")
        except Exception as e:
            logger.warning(f"ML anomaly detector not available: {e}")

        # Initialize Hindsight Agentic Memory (graceful fallback to local RAG)
        self.hindsight_adapter = None
        self.hindsight_available = False
        if HINDSIGHT_AVAILABLE:
            try:
                self.hindsight_adapter = HindsightAdapter()
                health = self.hindsight_adapter.check_health()
                self.hindsight_available = True
                mode = "full" if health.should_use_hindsight else "degraded"
                logger.info(f"Hindsight memory initialized for trade gate (mode: {mode})")
            except Exception as e:
                logger.debug(f"Hindsight adapter not available: {e}")

    def _verify_tracing_health(self) -> None:
        """Verify LangSmith tracing is operational."""
        try:
            from src.observability.tracing_health_check import verify_tracing_health

            result = verify_tracing_health(block_on_failure=False)
            self.tracing_healthy = result.healthy

            if result.healthy:
                logger.info("✅ Tracing health verified - LangSmith operational")
            else:
                logger.warning(f"⚠️ Tracing health check failed: {result.errors}")
                logger.warning("   Trades will execute but may not be traced!")
        except ImportError:
            logger.warning("Tracing health check module not available")
            self.tracing_healthy = False
        except Exception as e:
            logger.warning(f"Tracing health check failed: {e}")
            self.tracing_healthy = False

    def _check_recent_critical_failures(self) -> None:
        """
        Check for recent CRITICAL operational failures at startup.

        This runs ONCE when the gate is initialized to warn about
        recent lessons learned that might affect today's trading.
        """
        if not self.rag_available or not self.lessons_search:
            return

        try:
            # Query for recent critical operational failures
            critical_queries = [
                "CRITICAL operational failure",
                "trade blocked catastrophe",
                "blind trading equity zero",
            ]

            critical_lessons = []
            for query in critical_queries:
                results = self.lessons_search.query(query, top_k=3)
                for result in results:
                    if result.score > 0.4:  # Relevance threshold
                        content_lower = result.content.lower()
                        if "critical" in content_lower:
                            critical_lessons.append(result)

            if critical_lessons:
                logger.warning("=" * 60)
                logger.warning("🚨 CRITICAL LESSONS FOUND - READ BEFORE TRADING!")
                logger.warning("=" * 60)
                for lesson in critical_lessons[:3]:
                    logger.warning(f"  📚 {lesson.lesson_file}: {lesson.section_title}")
                logger.warning("=" * 60)
                logger.warning("Review these lessons to avoid repeating past failures!")

        except Exception as e:
            logger.debug(f"Critical failure check error (non-fatal): {e}")

    def _query_rag_for_lessons(self, symbol: str, strategy: str, side: str) -> list[str]:
        """
        Query RAG for relevant lessons learned using SEMANTIC SEARCH.

        This method MUST use semantic similarity, not keyword matching!
        The lessons we have about "blind trading" or "options not closing"
        will NOT be found by searching for "SPY trading".

        Returns:
            List of warnings from relevant lessons. CRITICAL lessons will block trades.
        """
        warnings = []

        # ========== SEMANTIC SEARCH QUERIES ==========
        # Build queries that will ACTUALLY find operational failure lessons
        semantic_queries = [
            # Operational failure patterns
            f"operational failure {strategy} trading",
            f"trade execution failure {side.lower()} order",
            "blind trading account data reading failure",
            "portfolio sync error equity zero",
            "API connection failure trade blocked",
            # Symbol-specific patterns
            f"{symbol} loss failure mistake",
            f"{strategy} strategy failure lesson learned",
            # General safety patterns
            "CRITICAL severity operational failure",
            "trade blocked safety gate",
            "buy to close sell to close options error",
        ]

        # Use the LessonsSearch semantic search engine
        if self.rag_available and self.lessons_search:
            try:
                all_results = []
                for query in semantic_queries[:5]:  # Top 5 queries to avoid latency
                    results = self.lessons_search.query(query, top_k=2)
                    all_results.extend(results)

                # Deduplicate by lesson file
                seen_lessons = set()
                unique_results = []
                for result in all_results:
                    if result.lesson_file not in seen_lessons:
                        seen_lessons.add(result.lesson_file)
                        unique_results.append(result)

                # Sort by relevance score
                unique_results.sort(key=lambda r: r.score, reverse=True)

                # Process results
                for result in unique_results[:5]:  # Top 5 relevant lessons
                    severity = result.metadata.get("severity", "").upper()
                    content_lower = result.content.lower()

                    # Check for CRITICAL severity
                    if severity == "CRITICAL" or "severity: critical" in content_lower or "severity**: critical" in content_lower:
                        warning = f"CRITICAL: {result.lesson_file} (score: {result.score:.2f})"
                        warnings.append(warning)
                        logger.warning(f"🚨 RAG found CRITICAL lesson: {result.lesson_file}")
                    elif result.score > 0.5:  # High relevance
                        warning = f"WARNING: {result.lesson_file} - {result.section_title} (score: {result.score:.2f})"
                        warnings.append(warning)

                if unique_results:
                    logger.info(f"📚 RAG semantic search found {len(unique_results)} relevant lessons")

            except Exception as e:
                logger.error(f"RAG semantic search failed: {e}")
                warnings.append(f"RAG search error (falling back to keyword): {e}")

        # ========== FALLBACK: DIRECT FILE SEARCH ==========
        # Also check lesson files directly for CRITICAL failures
        lessons_dir = Path("rag_knowledge/lessons_learned")
        if lessons_dir.exists():
            try:
                # Search for CRITICAL lessons about operational failures
                critical_patterns = [
                    ("blind trading", "equity", "zero"),
                    ("options", "close", "buy to close"),
                    ("operational failure", "catastrophe"),
                    ("API", "failure", "account"),
                    ("smoke test", "mandatory", "block"),
                ]

                for lesson_file in lessons_dir.glob("*.md"):
                    content = lesson_file.read_text().lower()

                    # Check if CRITICAL and matches any pattern
                    is_critical = "severity**: critical" in content or "severity: critical" in content

                    for pattern in critical_patterns:
                        if all(term in content for term in pattern):
                            if is_critical:
                                warning = f"CRITICAL: {lesson_file.stem} matches pattern {pattern}"
                                if warning not in warnings:
                                    warnings.append(warning)
                                    logger.warning(f"🚨 Direct search found CRITICAL: {lesson_file.stem}")
                            break

            except Exception as e:
                logger.error(f"Direct lesson search failed: {e}")

        # ========== OPERATIONAL CONTEXT CHECKS ==========
        # Check for specific known dangerous situations
        known_issues = {
            "200x": "ll_001: Check for 200x order amount error",
            "blind": "ll_051: Blind trading - verify account readable before trade",
            "equity_zero": "ll_051: Account shows $0 equity - BLOCK TRADE",
        }

        for keyword, warning in known_issues.items():
            if keyword in symbol.lower() or keyword in strategy.lower():
                warnings.append(warning)

        if not self.rag_available or not self.lessons_search:
            warnings.append("RAG not available - proceeding with caution")

        return warnings

    def _query_rag_for_lessons_ORIGINAL_KEYWORD_MATCHING(self, symbol: str, strategy: str, side: str) -> list[str]:
        """DEPRECATED: Original keyword matching that never worked.

        Kept for reference to show what NOT to do.
        """
        warnings = []

        if not self.rag_available or not self.lessons_search:
            return ["RAG not available - proceeding with caution"]

        try:
            # Build search queries based on trade context
            queries = [
                f"{symbol} trading",
                f"{strategy} strategy",
                f"{side.lower()} order mistakes",
                "position sizing error",
                "order execution failure",
            ]

            lessons_dir = Path("rag_knowledge/lessons_learned")
            if not lessons_dir.exists():
                return ["No lessons learned directory found"]

            # Simple keyword search through lessons
            relevant_lessons = []
            for lesson_file in lessons_dir.glob("*.md"):
                content = lesson_file.read_text().lower()
                for query in queries:
                    if query.lower() in content:
                        # Check if this is a CRITICAL lesson
                        if "severity**: critical" in content or "severity: critical" in content.lower():
                            relevant_lessons.append(f"CRITICAL: {lesson_file.stem}")
                        break

            if relevant_lessons:
                warnings.extend([f"RAG found relevant lessons: {', '.join(relevant_lessons[:3])}"])

            # Check for specific known issues
            known_issues = {
                "200x": "ll_001: Check for 200x order amount error",
            }

            for keyword, warning in known_issues.items():
                if keyword in symbol.lower() or keyword in strategy.lower():
                    warnings.append(warning)

        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            warnings.append(f"RAG query error: {e}")

        return warnings

    def _query_hindsight_memory(self, symbol: str, strategy: str) -> list[str]:
        """Query Hindsight agentic memory for relevant trade warnings."""
        warnings = []

        if not self.hindsight_available or not self.hindsight_adapter:
            return []

        try:
            # Check for similar past trades
            result = self.hindsight_adapter.check_similar_trades(
                symbol=symbol,
                strategy=strategy,
                n_results=3,
            )

            if result.success and result.data:
                # Look for negative outcomes in similar trades
                for memory in (result.data if isinstance(result.data, list) else [result.data]):
                    memory_str = str(memory).lower()
                    if "loss" in memory_str or "failed" in memory_str:
                        warnings.append(f"HINDSIGHT: Similar {symbol} trades had losses - review before proceeding")
                        break

            # Get ticker opinion with confidence
            opinion = self.hindsight_adapter.get_ticker_opinion(symbol)
            if opinion.success and opinion.confidence is not None:
                if opinion.confidence < 0.3:
                    warnings.append(f"HINDSIGHT: Low conviction on {symbol} ({opinion.confidence:.0%})")

        except Exception as e:
            logger.debug(f"Hindsight memory query failed: {e}")

        return warnings

    def _run_ml_anomaly_check(
        self,
        symbol: str,
        amount: float,
        side: str
    ) -> list[str]:
        """Run ML anomaly detection on the order."""
        anomalies = []

        if not self.ml_available or not self.anomaly_detector:
            return ["ML anomaly detector not available - proceeding with caution"]

        try:
            detected = self.anomaly_detector.validate_trade(symbol, amount, side)

            for anomaly in detected:
                level = anomaly.alert_level.value
                msg = f"[{level.upper()}] {anomaly.anomaly_type.value}: {anomaly.message}"
                anomalies.append(msg)

                if level == "block":
                    logger.error(f"ML BLOCKING TRADE: {msg}")

        except Exception as e:
            logger.error(f"ML anomaly check failed: {e}")
            anomalies.append(f"ML check error: {e}")

        return anomalies

    def _log_gate_decision(self, result: GateResult, trade_context: dict) -> None:
        """Log the gate decision for audit trail."""
        try:
            log_entry = {
                "timestamp": result.timestamp,
                "trade_context": trade_context,
                "result": result.to_dict(),
            }

            # Append to log file
            existing = []
            if self.gate_log_path.exists():
                try:
                    existing = json.loads(self.gate_log_path.read_text())
                except Exception:
                    existing = []

            existing.append(log_entry)

            # Keep last 1000 entries
            existing = existing[-1000:]

            self.gate_log_path.write_text(json.dumps(existing, indent=2))

        except Exception as e:
            logger.error(f"Failed to log gate decision: {e}")

    def validate_trade(
        self,
        symbol: str,
        amount: float,
        side: str,
        strategy: str = "unknown",
        bypass_reason: str | None = None,
        context: dict | None = None,
    ) -> GateResult:
        """
        MANDATORY validation before ANY trade.

        ALL gate decisions are traced to LangSmith for observability.

        Args:
            symbol: Trading symbol (e.g., "SPY")
            amount: Dollar amount of the trade
            side: "BUY" or "SELL"
            strategy: Trading strategy type
            bypass_reason: If set, logs bypass but still validates
            context: Optional additional context (e.g., {"equity": 0.0})

        Returns:
            GateResult with approved/blocked status and reasons
        """
        timestamp = datetime.now().isoformat()
        context = context or {}
        trade_context = {
            "symbol": symbol,
            "amount": amount,
            "side": side,
            "strategy": strategy,
            "bypass_reason": bypass_reason,
            **context,
        }

        # Check if gate is disabled (NOT RECOMMENDED)
        if not GATE_ENABLED:
            logger.warning("⚠️ MANDATORY TRADE GATE IS DISABLED - This is dangerous!")
            result = GateResult(
                approved=True,
                reason="Gate disabled (NOT RECOMMENDED)",
                rag_warnings=[],
                ml_anomalies=[],
                confidence=0.0,
                timestamp=timestamp,
            )
            self._trace_gate_decision(result, trade_context)
            return result

        logger.info(f"🚦 MANDATORY GATE: Validating {side} {symbol} ${amount:.2f} ({strategy})")

        # 1. Query RAG for lessons learned (SEMANTIC SEARCH)
        rag_warnings = self._query_rag_for_lessons(symbol, strategy, side)

        if rag_warnings:
            logger.info(f"📚 RAG: Found {len(rag_warnings)} relevant warning(s)")
            for w in rag_warnings[:3]:
                logger.info(f"   📖 {w}")

        # 1.5. Query Hindsight agentic memory (auto-fallback to local RAG)
        hindsight_warnings = self._query_hindsight_memory(symbol, strategy)
        if hindsight_warnings:
            logger.info(f"📚 HINDSIGHT: {len(hindsight_warnings)} memory warning(s)")

        # 2. Run ML anomaly detection
        ml_anomalies = self._run_ml_anomaly_check(symbol, amount, side)

        # 3. Determine if trade should be blocked
        blocked = False
        block_reasons = []

        # ========== CONTEXT-AWARE BLOCKING ==========
        # Check for dangerous operational conditions (ll_051 prevention)
        equity = context.get("equity", None)
        buying_power = context.get("buying_power", None)

        if equity is not None and equity <= 0:
            blocked = True
            block_reasons.append("BLOCKED: Equity is $0 - ll_051 blind trading prevention")
            logger.error("🚨 BLOCKING: Equity is $0 - learned from blind trading catastrophe!")

        if buying_power is not None and buying_power <= 0:
            blocked = True
            block_reasons.append("BLOCKED: Buying power is $0 - cannot execute trades")
            logger.error("🚨 BLOCKING: Buying power is $0!")
        # ============================================

        # Check for blocking ML anomalies
        blocking_anomalies = [a for a in ml_anomalies if "[BLOCK]" in a.upper()]
        if blocking_anomalies and BLOCK_ON_ML_ANOMALY:
            blocked = True
            block_reasons.extend(blocking_anomalies)

        # Check for critical RAG warnings (includes Hindsight warnings)
        all_rag_warnings = rag_warnings + hindsight_warnings
        critical_warnings = [w for w in all_rag_warnings if "CRITICAL" in w.upper()]
        if critical_warnings and BLOCK_ON_RAG_WARNING:
            blocked = True
            block_reasons.extend(critical_warnings)
            logger.error(f"🚨 BLOCKING due to CRITICAL lessons: {critical_warnings}")

        # Calculate confidence (lower if warnings/anomalies exist)
        total_issues = len(all_rag_warnings) + len(ml_anomalies)
        confidence = max(0.0, 1.0 - (total_issues * 0.1))

        if blocked:
            reason = f"BLOCKED: {'; '.join(block_reasons)}"
            logger.error(f"🚫 TRADE BLOCKED: {reason}")
        else:
            reason = "APPROVED" if total_issues == 0 else f"APPROVED with {total_issues} warnings"
            logger.info(f"✅ TRADE {reason}")

        result = GateResult(
            approved=not blocked,
            reason=reason,
            rag_warnings=all_rag_warnings,  # Includes Hindsight + local RAG warnings
            ml_anomalies=ml_anomalies,
            confidence=confidence,
            timestamp=timestamp,
        )

        # Log the decision locally
        self._log_gate_decision(result, trade_context)

        # ========== LANGSMITH TRACING ==========
        # Trace every gate decision for observability
        self._trace_gate_decision(result, trade_context)
        # ========================================

        return result

    def _trace_gate_decision(self, result: GateResult, trade_context: dict) -> None:
        """Trace the gate decision to LangSmith."""
        if not LANGSMITH_AVAILABLE:
            return

        try:
            tracer = get_tracer()
            symbol = trade_context.get("symbol", "UNKNOWN")
            side = trade_context.get("side", "UNKNOWN")

            with tracer.trace(
                name=f"trade_gate_{symbol}_{side}",
                trace_type=TraceType.VERIFICATION,
            ) as span:
                # Set inputs
                span.inputs = trade_context

                # Add outputs
                span.add_output("approved", result.approved)
                span.add_output("reason", result.reason)
                span.add_output("confidence", result.confidence)
                span.add_output("rag_warnings_count", len(result.rag_warnings))
                span.add_output("ml_anomalies_count", len(result.ml_anomalies))

                # Add metadata
                span.add_metadata({
                    "gate_decision": "APPROVED" if result.approved else "BLOCKED",
                    "symbol": symbol,
                    "amount": trade_context.get("amount"),
                    "strategy": trade_context.get("strategy"),
                    "rag_warnings": result.rag_warnings[:5],  # Limit to first 5
                    "ml_anomalies": result.ml_anomalies[:5],  # Limit to first 5
                })

            logger.debug(f"📊 Gate decision traced to LangSmith: {symbol} {side} -> {result.reason}")
        except Exception as e:
            logger.warning(f"Failed to trace gate decision to LangSmith: {e}")


# Global singleton for easy access
_gate_instance: MandatoryTradeGate | None = None


def get_trade_gate() -> MandatoryTradeGate:
    """Get the global trade gate instance."""
    global _gate_instance
    if _gate_instance is None:
        _gate_instance = MandatoryTradeGate()
    return _gate_instance


def validate_trade_mandatory(
    symbol: str,
    amount: float,
    side: str,
    strategy: str = "unknown",
    context: dict | None = None,
) -> GateResult:
    """
    MANDATORY function to call before ANY trade execution.

    This is the main entry point for trade validation.

    The context parameter allows passing operational state like equity
    and buying_power to enable context-aware blocking based on lessons learned.

    Example:
        result = validate_trade_mandatory(
            "SPY", 100.0, "BUY", "equities",
            context={"equity": account.equity, "buying_power": account.buying_power}
        )
        if not result.approved:
            raise TradeBlockedError(result.reason)
    """
    gate = get_trade_gate()
    return gate.validate_trade(symbol, amount, side, strategy, context=context)


class TradeBlockedError(Exception):
    """Raised when a trade is blocked by the mandatory gate."""

    def __init__(self, result: GateResult):
        self.result = result
        super().__init__(f"Trade blocked: {result.reason}")
