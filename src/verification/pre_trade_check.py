"""
Pre-Trade Verification System
Uses RAG + ML to prevent mistakes before trade execution.

Components:
1. RAG Lessons Lookup - Search past mistakes before trading
2. UDM Validation - Validate signals against domain model
3. Anomaly Detection - ML-based pattern checking
4. Circuit Breakers - Hard limits from historical data

Usage:
    from src.verification.pre_trade_check import PreTradeVerifier

    verifier = PreTradeVerifier()
    result = await verifier.verify(signal)
    if result.approved:
        execute_trade(signal)
    else:
        log_blocked(result.reasons)
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.unified_domain_model import AssetClass, DomainValidator, Signal, TradeAction

# =============================================================================
# VERIFICATION RESULT
# =============================================================================


class BlockReason(str, Enum):
    """Reasons a trade might be blocked"""

    VALIDATION_FAILED = "validation_failed"
    LESSONS_LEARNED_WARNING = "lessons_learned_warning"
    ANOMALY_DETECTED = "anomaly_detected"
    CIRCUIT_BREAKER = "circuit_breaker"
    MARKET_CLOSED = "market_closed"
    CONFIDENCE_TOO_LOW = "confidence_too_low"
    COOLDOWN_ACTIVE = "cooldown_active"


@dataclass
class VerificationResult:
    """Result of pre-trade verification"""

    approved: bool
    signal: Signal
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    lessons_found: list[dict] = field(default_factory=list)
    checks_passed: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "signal": self.signal.to_dict() if self.signal else None,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "lessons_found": self.lessons_found,
            "checks_passed": self.checks_passed,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# RAG LESSONS LEARNED SEARCHER
# =============================================================================


class LessonsLearnedRAG:
    """
    Simple RAG system for searching lessons learned.
    Uses keyword matching + similarity for now.
    Can be upgraded to vector embeddings later.
    """

    def __init__(self, lessons_dir: str = "rag_knowledge/lessons_learned"):
        self.lessons_dir = Path(lessons_dir)
        self.lessons_cache: list[dict] = []
        self._load_lessons()

    def _load_lessons(self):
        """Load all lessons into memory"""
        if not self.lessons_dir.exists():
            return

        for lesson_file in self.lessons_dir.glob("*.md"):
            try:
                content = lesson_file.read_text()
                # Parse frontmatter-style metadata
                lesson = {
                    "file": lesson_file.name,
                    "path": str(lesson_file),
                    "content": content,
                    "title": self._extract_title(content),
                    "severity": self._extract_field(content, "Severity"),
                    "category": self._extract_field(content, "Category"),
                    "tags": self._extract_tags(content),
                }
                self.lessons_cache.append(lesson)
            except Exception as e:
                print(f"Error loading {lesson_file}: {e}")

    def _extract_title(self, content: str) -> str:
        """Extract title from markdown"""
        for line in content.split("\n"):
            if line.startswith("# "):
                return line[2:].strip()
        return "Unknown"

    def _extract_field(self, content: str, field: str) -> str:
        """Extract field value from content"""
        for line in content.split("\n"):
            if f"**{field}**:" in line:
                return line.split(":")[-1].strip()
        return ""

    def _extract_tags(self, content: str) -> list[str]:
        """Extract hashtags from content"""
        import re

        return re.findall(r"#(\w+)", content)

    def search(self, query: str, context: dict = None, max_results: int = 5) -> list[dict]:
        """
        Search lessons learned for relevant entries.
        Returns lessons that might be relevant to the current situation.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        # Add context-based keywords
        if context:
            if context.get("symbol"):
                query_words.add(context["symbol"].lower())
            if context.get("action"):
                query_words.add(context["action"].lower())
            if context.get("asset_class"):
                query_words.add(context["asset_class"].lower())

        results = []
        for lesson in self.lessons_cache:
            score = 0
            content_lower = lesson["content"].lower()

            # Score based on keyword matches
            for word in query_words:
                if word in content_lower:
                    score += 1
                if word in lesson.get("title", "").lower():
                    score += 3
                if word in lesson.get("tags", []):
                    score += 2

            # Boost high severity lessons
            if lesson.get("severity", "").upper() in ["HIGH", "CRITICAL"]:
                score += 2

            if score > 0:
                results.append(
                    {
                        "score": score,
                        "title": lesson["title"],
                        "file": lesson["file"],
                        "severity": lesson["severity"],
                        "tags": lesson["tags"],
                        "summary": lesson["content"][:300] + "...",
                    }
                )

        # Sort by score and return top results
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]

    def get_critical_lessons(self) -> list[dict]:
        """Get all HIGH/CRITICAL severity lessons"""
        return [
            {
                "title": l["title"],
                "severity": l["severity"],
                "tags": l["tags"],
            }
            for l in self.lessons_cache
            if l.get("severity", "").upper() in ["HIGH", "CRITICAL"]
        ]


# =============================================================================
# CIRCUIT BREAKERS
# =============================================================================


class CircuitBreakers:
    """
    Hard limits based on historical lessons and risk management.
    These are non-negotiable safety checks.
    """

    # Maximum position sizes by asset class
    MAX_NOTIONAL = {
        AssetClass.CRYPTO: 50.0,  # $50 max per crypto trade
        AssetClass.EQUITY: 100.0,  # $100 max per equity trade
        AssetClass.OPTION: 50.0,  # $50 max per options trade
        AssetClass.ETF: 100.0,  # $100 max per ETF trade
    }

    # Minimum confidence by action
    MIN_CONFIDENCE = {
        TradeAction.BUY: 0.65,
        TradeAction.SELL: 0.60,
        TradeAction.HOLD: 0.0,  # Hold always OK
    }

    # Maximum daily trades
    MAX_DAILY_TRADES = 10

    # Cooldown between trades on same symbol (minutes)
    SYMBOL_COOLDOWN_MINUTES = 30

    @classmethod
    def check_all(cls, signal: Signal, trade_history: list[dict] = None) -> list[str]:
        """Run all circuit breaker checks, return list of violations"""
        violations = []
        trade_history = trade_history or []

        # Check confidence threshold
        min_conf = cls.MIN_CONFIDENCE.get(signal.action, 0.6)
        if signal.confidence < min_conf:
            violations.append(
                f"Confidence {signal.confidence:.0%} below minimum {min_conf:.0%} for {signal.action.value}"
            )

        # Check daily trade count
        today = datetime.utcnow().date()
        today_trades = [t for t in trade_history if t.get("date") == str(today)]
        if len(today_trades) >= cls.MAX_DAILY_TRADES:
            violations.append(f"Daily trade limit reached ({cls.MAX_DAILY_TRADES})")

        # Check symbol cooldown
        symbol_trades = [t for t in trade_history if t.get("symbol") == signal.symbol.ticker]
        if symbol_trades:
            last_trade = max(symbol_trades, key=lambda x: x.get("timestamp", ""))
            last_time = datetime.fromisoformat(last_trade.get("timestamp", "2000-01-01"))
            minutes_since = (datetime.utcnow() - last_time).total_seconds() / 60
            if minutes_since < cls.SYMBOL_COOLDOWN_MINUTES:
                violations.append(
                    f"Cooldown active for {signal.symbol.ticker} ({int(cls.SYMBOL_COOLDOWN_MINUTES - minutes_since)} min remaining)"
                )

        return violations


# =============================================================================
# ANOMALY DETECTOR
# =============================================================================


class AnomalyDetector:
    """
    Simple anomaly detection based on historical patterns.
    Flags unusual trading conditions.
    """

    @staticmethod
    def check(signal: Signal, market_data: dict = None) -> list[str]:
        """Check for anomalies, return list of warnings"""
        warnings = []
        market_data = market_data or {}

        # Check for extreme confidence (might indicate overfitting)
        if signal.confidence > 0.95:
            warnings.append(
                f"Unusually high confidence ({signal.confidence:.0%}) - verify signal source"
            )

        # Check for weekend trading (not allowed for equities)
        now = datetime.utcnow()
        is_weekend = now.weekday() >= 5
        if is_weekend:
            warnings.append("Weekend trading detected - markets closed")

        # Check for after-hours equity trading
        if signal.symbol.asset_class == AssetClass.EQUITY:
            hour = now.hour
            if hour < 9 or hour >= 16:  # Simplified - doesn't account for timezone
                warnings.append("After-hours equity trading - verify market is open")

        return warnings


# =============================================================================
# PRE-TRADE VERIFIER (Main Class)
# =============================================================================


class PreTradeVerifier:
    """
    Main verification system that combines all checks.
    Run this before every trade execution.
    """

    def __init__(self, lessons_dir: str = "rag_knowledge/lessons_learned"):
        self.rag = LessonsLearnedRAG(lessons_dir)
        self.trade_history: list[dict] = []
        self._load_trade_history()

    def _load_trade_history(self):
        """Load recent trade history"""
        trades_dir = Path("data")
        today = datetime.utcnow().strftime("%Y-%m-%d")

        # Load today's trades
        trades_file = trades_dir / f"trades_{today}.json"
        if trades_file.exists():
            try:
                self.trade_history = json.loads(trades_file.read_text())
            except Exception:
                self.trade_history = []

    def verify(self, signal: Signal, extra_context: dict = None) -> VerificationResult:
        """
        Run all verification checks on a signal.
        Returns VerificationResult with approval status and details.
        """
        result = VerificationResult(approved=True, signal=signal)
        extra_context = extra_context or {}

        # 1. UDM Validation
        validation = DomainValidator.validate(signal)
        if not validation.is_valid:
            result.approved = False
            result.reasons.extend(
                [f"Validation failed: {e.field} - {e.message}" for e in validation.errors]
            )
        else:
            result.checks_passed.append("UDM validation")

        # 2. RAG Lessons Lookup
        search_context = {
            "symbol": signal.symbol.ticker,
            "action": signal.action.value,
            "asset_class": signal.symbol.asset_class.value,
        }
        search_query = f"{signal.action.value} {signal.symbol.ticker} {signal.symbol.asset_class.value} trading"
        lessons = self.rag.search(search_query, search_context, max_results=3)

        if lessons:
            result.lessons_found = lessons
            # High-scoring lessons become warnings
            for lesson in lessons:
                if lesson["score"] >= 5:  # High relevance
                    result.warnings.append(
                        f"Relevant lesson: {lesson['title']} (score: {lesson['score']})"
                    )
        result.checks_passed.append("RAG lessons search")

        # 3. Circuit Breakers
        violations = CircuitBreakers.check_all(signal, self.trade_history)
        if violations:
            result.approved = False
            result.reasons.extend(violations)
        else:
            result.checks_passed.append("Circuit breakers")

        # 4. Anomaly Detection
        anomalies = AnomalyDetector.check(signal)
        if anomalies:
            result.warnings.extend(anomalies)
        result.checks_passed.append("Anomaly detection")

        # Log the verification
        self._log_verification(result)

        return result

    def _log_verification(self, result: VerificationResult):
        """Log verification result for audit trail"""
        log_dir = Path("data/verification_logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"verification_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"

        with open(log_file, "a") as f:
            f.write(json.dumps(result.to_dict()) + "\n")

    def get_critical_lessons_summary(self) -> str:
        """Get summary of critical lessons for pre-trade review"""
        critical = self.rag.get_critical_lessons()
        if not critical:
            return "No critical lessons found."

        lines = ["## Critical Lessons to Remember", ""]
        for lesson in critical:
            tags = ", ".join(lesson.get("tags", [])[:3])
            lines.append(f"- **{lesson['title']}** [{lesson.get('severity', 'N/A')}] - {tags}")

        return "\n".join(lines)


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    from src.core.unified_domain_model import TradeAction, factory

    print("=" * 60)
    print("PRE-TRADE VERIFICATION SYSTEM TEST")
    print("=" * 60)

    # Create verifier
    verifier = PreTradeVerifier()

    # Show critical lessons
    print("\n[1] CRITICAL LESSONS SUMMARY")
    print("-" * 40)
    print(verifier.get_critical_lessons_summary())

    # Test with a valid signal
    print("\n[2] TESTING VALID SIGNAL")
    print("-" * 40)

    spy = factory.create_equity_symbol("SPY")
    signal = factory.create_signal(
        symbol=spy, action=TradeAction.BUY, confidence=0.75, source="test_strategy"
    )

    result = verifier.verify(signal)
    print(f"Signal: {signal.action.value} {signal.symbol.ticker} @ {signal.confidence:.0%}")
    print(f"Approved: {result.approved}")
    print(f"Checks passed: {result.checks_passed}")
    if result.warnings:
        print(f"Warnings: {result.warnings}")
    if result.reasons:
        print(f"Block reasons: {result.reasons}")
    if result.lessons_found:
        print(f"Relevant lessons: {[l['title'] for l in result.lessons_found]}")

    # Test with invalid signal (low confidence)
    print("\n[3] TESTING LOW CONFIDENCE SIGNAL")
    print("-" * 40)

    weak_signal = factory.create_signal(
        symbol=btc, action=TradeAction.BUY, confidence=0.45, source="test_strategy"
    )

    result = verifier.verify(weak_signal)
    print(
        f"Signal: {weak_signal.action.value} {weak_signal.symbol.ticker} @ {weak_signal.confidence:.0%}"
    )
    print(f"Approved: {result.approved}")
    print(f"Block reasons: {result.reasons}")

    print("\n" + "=" * 60)
    print("Verification system ready!")
    print("=" * 60)
