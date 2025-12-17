"""
Pre-Trade RAG Verification.

Queries lessons learned BEFORE every trade to prevent repeating mistakes.
This is the final gate before order execution.

Usage:
    from src.verification.pre_trade_rag_check import PreTradeRAGCheck

    checker = PreTradeRAGCheck()

    # Before placing trade
    result = checker.verify_trade_safe(
        symbol="NVDA",
        action="BUY",
        quantity=10,
        strategy="momentum",
        market_conditions={"volatility": 0.025}
    )

    if not result["safe"]:
        print(f"Trade blocked: {result['reason']}")
        print(f"Similar past failures: {result['similar_failures']}")

Author: Trading System
Created: 2025-12-15
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

LESSONS_DIR = Path("rag_knowledge/lessons_learned")
TRADE_BLOCKS_LOG = Path("data/audit_trail/trade_blocks.jsonl")


@dataclass
class TradeVerificationResult:
    """Result of pre-trade RAG verification."""

    safe: bool
    confidence: float  # 0.0 to 1.0
    reason: str
    similar_failures: list  # List of similar past failures
    recommendations: list  # Suggested actions
    checks_passed: dict  # Individual check results


class PreTradeRAGCheck:
    """
    Pre-trade verification using RAG knowledge base.

    Checks:
    1. Symbol-specific lessons (e.g., "NVDA had issues with...")
    2. Strategy-specific lessons (e.g., "momentum strategy failed when...")
    3. Market condition lessons (e.g., "high volatility caused...")
    4. Time-based lessons (e.g., "market open is risky for...")
    5. Recent failure patterns (e.g., "last 3 trades on X failed")
    """

    # Severity weights for blocking decisions
    SEVERITY_WEIGHTS = {
        "CRITICAL": 1.0,
        "HIGH": 0.7,
        "MEDIUM": 0.4,
        "LOW": 0.2,
    }

    # Block threshold - if cumulative risk score exceeds this, block trade
    BLOCK_THRESHOLD = 0.8

    def __init__(
        self,
        lessons_dir: Optional[Path] = None,
        block_threshold: float = 0.8,
    ):
        self.lessons_dir = lessons_dir or LESSONS_DIR
        self.block_threshold = block_threshold
        self.lessons = self._load_lessons()
        self.recent_failures = self._load_recent_failures()

    def verify_trade_safe(
        self,
        symbol: str,
        action: str,
        quantity: float,
        strategy: str,
        price: Optional[float] = None,
        market_conditions: Optional[dict] = None,
    ) -> TradeVerificationResult:
        """
        Verify if a trade is safe based on lessons learned.

        Args:
            symbol: Trading symbol (e.g., "NVDA", "BTC/USD")
            action: Trade action ("BUY" or "SELL")
            quantity: Number of shares/units
            strategy: Strategy name (e.g., "momentum", "mean_reversion")
            price: Current price (optional)
            market_conditions: Dict with volatility, volume, etc. (optional)

        Returns:
            TradeVerificationResult with safety assessment
        """
        checks = {}
        similar_failures = []
        recommendations = []
        cumulative_risk = 0.0

        market_conditions = market_conditions or {}

        # Check 1: Symbol-specific lessons
        symbol_lessons = self._search_lessons(
            query=symbol,
            filters={"symbol": symbol}
        )
        if symbol_lessons:
            checks["symbol_check"] = {
                "passed": len(symbol_lessons) == 0,
                "lessons": [lesson["id"] for lesson in symbol_lessons[:3]],
            }
            for lesson in symbol_lessons:
                cumulative_risk += self.SEVERITY_WEIGHTS.get(
                    lesson.get("severity", "LOW"), 0.2
                )
                similar_failures.append({
                    "id": lesson["id"],
                    "title": lesson.get("title", ""),
                    "severity": lesson.get("severity", ""),
                    "match_type": "symbol",
                })
        else:
            checks["symbol_check"] = {"passed": True, "lessons": []}

        # Check 2: Strategy-specific lessons
        strategy_lessons = self._search_lessons(
            query=strategy,
            filters={"strategy": strategy}
        )
        if strategy_lessons:
            checks["strategy_check"] = {
                "passed": len(strategy_lessons) == 0,
                "lessons": [lesson["id"] for lesson in strategy_lessons[:3]],
            }
            for lesson in strategy_lessons:
                cumulative_risk += self.SEVERITY_WEIGHTS.get(
                    lesson.get("severity", "LOW"), 0.2
                ) * 0.8  # Slightly lower weight for strategy
                similar_failures.append({
                    "id": lesson["id"],
                    "title": lesson.get("title", ""),
                    "severity": lesson.get("severity", ""),
                    "match_type": "strategy",
                })
        else:
            checks["strategy_check"] = {"passed": True, "lessons": []}

        # Check 3: Market condition lessons
        if market_conditions:
            condition_lessons = self._check_market_conditions(market_conditions)
            checks["market_conditions"] = {
                "passed": len(condition_lessons) == 0,
                "lessons": [lesson["id"] for lesson in condition_lessons[:3]],
            }
            for lesson in condition_lessons:
                cumulative_risk += self.SEVERITY_WEIGHTS.get(
                    lesson.get("severity", "LOW"), 0.2
                )
                similar_failures.append({
                    "id": lesson["id"],
                    "title": lesson.get("title", ""),
                    "severity": lesson.get("severity", ""),
                    "match_type": "market_condition",
                })

        # Check 4: Time-based lessons (market open, close, etc.)
        time_lessons = self._check_time_based_risks()
        if time_lessons:
            checks["time_check"] = {
                "passed": len(time_lessons) == 0,
                "lessons": [lesson["id"] for lesson in time_lessons[:2]],
            }
            for lesson in time_lessons:
                cumulative_risk += self.SEVERITY_WEIGHTS.get(
                    lesson.get("severity", "LOW"), 0.2
                ) * 0.5  # Lower weight for time

        # Check 5: Recent failures on this symbol
        recent = self._check_recent_failures(symbol)
        if recent["failure_count"] >= 2:
            checks["recent_failures"] = {
                "passed": False,
                "failure_count": recent["failure_count"],
                "last_failure": recent["last_failure"],
            }
            cumulative_risk += 0.3 * recent["failure_count"]
            recommendations.append(
                f"Symbol {symbol} has {recent['failure_count']} recent failures. "
                "Consider reducing position size or skipping."
            )
        else:
            checks["recent_failures"] = {"passed": True, "failure_count": 0}

        # Check 6: Position size sanity
        if quantity > 100:  # Arbitrary threshold
            size_lessons = self._search_lessons(query="position size")
            if size_lessons:
                checks["position_size"] = {
                    "passed": False,
                    "quantity": quantity,
                    "warning": "Large position detected",
                }
                cumulative_risk += 0.3
                recommendations.append(
                    f"Large position size ({quantity}). "
                    "Verify this is intentional per position sizing rules."
                )

        # Determine overall safety
        is_safe = cumulative_risk < self.block_threshold
        confidence = max(0.0, 1.0 - cumulative_risk)

        # Generate reason
        if is_safe:
            reason = "All checks passed"
        else:
            failed_checks = [k for k, v in checks.items() if not v.get("passed", True)]
            reason = f"Risk score {cumulative_risk:.2f} exceeds threshold. Failed: {', '.join(failed_checks)}"

        # Generate recommendations
        if similar_failures:
            most_relevant = similar_failures[0]
            recommendations.append(
                f"Review lesson {most_relevant['id']}: {most_relevant['title']}"
            )

        if cumulative_risk > 0.5 and is_safe:
            recommendations.append(
                "Consider reducing position size due to elevated risk score"
            )

        result = TradeVerificationResult(
            safe=is_safe,
            confidence=confidence,
            reason=reason,
            similar_failures=similar_failures,
            recommendations=recommendations,
            checks_passed=checks,
        )

        # Log if blocked
        if not is_safe:
            self._log_trade_block(symbol, action, quantity, strategy, result)

        return result

    def _search_lessons(
        self,
        query: str,
        filters: Optional[dict] = None,
        top_k: int = 5,
    ) -> list:
        """
        Search lessons learned for relevant matches.

        Args:
            query: Search query
            filters: Optional filters (symbol, strategy, etc.)
            top_k: Max results to return

        Returns:
            List of matching lesson dicts
        """
        query_lower = query.lower()
        filters = filters or {}
        matches = []

        for lesson in self.lessons:
            score = 0.0

            # Check title match
            if query_lower in lesson.get("title", "").lower():
                score += 3.0

            # Check content match
            if query_lower in lesson.get("content", "").lower():
                score += 1.0

            # Check category match
            if query_lower in lesson.get("category", "").lower():
                score += 2.0

            # Check tags
            for tag in lesson.get("tags", []):
                if query_lower in tag.lower():
                    score += 1.5

            # Apply filters
            for key, value in filters.items():
                if value.lower() in lesson.get("content", "").lower():
                    score += 2.0

            if score > 0:
                lesson_copy = lesson.copy()
                lesson_copy["_score"] = score
                matches.append(lesson_copy)

        # Sort by score and severity
        matches.sort(
            key=lambda x: (
                x["_score"],
                self.SEVERITY_WEIGHTS.get(x.get("severity", "LOW"), 0),
            ),
            reverse=True,
        )

        return matches[:top_k]

    def _check_market_conditions(self, conditions: dict) -> list:
        """Check for lessons related to current market conditions."""
        lessons = []

        # High volatility check
        if conditions.get("volatility", 0) > 0.03:  # 3% daily volatility
            vol_lessons = self._search_lessons("volatility spike")
            lessons.extend(vol_lessons)

        # Low volume check
        if conditions.get("volume_ratio", 1.0) < 0.5:  # Below average volume
            vol_lessons = self._search_lessons("low volume")
            lessons.extend(vol_lessons)

        # News event check
        if conditions.get("has_news", False):
            news_lessons = self._search_lessons("news event")
            lessons.extend(news_lessons)

        return lessons

    def _check_time_based_risks(self) -> list:
        """Check for time-based risk lessons."""
        now = datetime.now()
        lessons = []

        # Market open (first 30 minutes)
        if now.hour == 9 and now.minute < 60:  # 9:30-10:00 AM ET
            open_lessons = self._search_lessons("market open")
            lessons.extend(open_lessons)

        # Market close (last 30 minutes)
        if now.hour == 15 and now.minute > 30:  # 3:30-4:00 PM ET
            close_lessons = self._search_lessons("market close")
            lessons.extend(close_lessons)

        # Monday morning
        if now.weekday() == 0 and now.hour < 11:
            monday_lessons = self._search_lessons("monday")
            lessons.extend(monday_lessons)

        # Friday afternoon
        if now.weekday() == 4 and now.hour >= 14:
            friday_lessons = self._search_lessons("friday")
            lessons.extend(friday_lessons)

        return lessons

    def _check_recent_failures(self, symbol: str) -> dict:
        """Check for recent failures on this symbol."""
        cutoff = datetime.now() - timedelta(days=7)
        recent = [
            f for f in self.recent_failures
            if f.get("symbol") == symbol
            and datetime.fromisoformat(f.get("timestamp", "2000-01-01")) > cutoff
        ]

        return {
            "failure_count": len(recent),
            "last_failure": recent[-1]["timestamp"] if recent else None,
            "failures": recent,
        }

    def _load_lessons(self) -> list:
        """Load all lessons from markdown files."""
        lessons = []

        if not self.lessons_dir.exists():
            logger.warning(f"Lessons directory not found: {self.lessons_dir}")
            return lessons

        for md_file in self.lessons_dir.glob("*.md"):
            try:
                content = md_file.read_text()
                lesson = self._parse_lesson(md_file.stem, content)
                if lesson:
                    lessons.append(lesson)
            except Exception as e:
                logger.warning(f"Failed to parse {md_file}: {e}")

        logger.info(f"Loaded {len(lessons)} lessons for pre-trade verification")
        return lessons

    def _parse_lesson(self, filename: str, content: str) -> Optional[dict]:
        """Parse a lesson markdown file."""
        import re

        lesson = {
            "id": filename,
            "content": content,
            "title": "",
            "severity": "MEDIUM",
            "category": "",
            "tags": [],
        }

        # Extract metadata
        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
        if title_match:
            lesson["title"] = title_match.group(1).replace("Lesson Learned: ", "")

        severity_match = re.search(r"\*\*Severity\*\*:\s*(\w+)", content, re.IGNORECASE)
        if severity_match:
            lesson["severity"] = severity_match.group(1).upper()

        category_match = re.search(r"\*\*Category\*\*:\s*(.+)$", content, re.MULTILINE)
        if category_match:
            lesson["category"] = category_match.group(1).strip()

        tags_match = re.search(r"\*\*Tags\*\*:\s*(.+)$", content, re.MULTILINE)
        if tags_match:
            lesson["tags"] = [t.strip() for t in tags_match.group(1).split(",")]

        return lesson

    def _load_recent_failures(self) -> list:
        """Load recent trade failures from audit trail."""
        failures = []

        # Check various failure sources
        failure_sources = [
            Path("data/audit_trail/trade_failures.jsonl"),
            Path("data/anomaly_recurrence.json"),
            TRADE_BLOCKS_LOG,
        ]

        for source in failure_sources:
            if source.exists():
                try:
                    if source.suffix == ".jsonl":
                        with open(source) as f:
                            for line in f:
                                if line.strip():
                                    failures.append(json.loads(line))
                    else:
                        with open(source) as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                failures.extend(data)
                            elif isinstance(data, dict):
                                failures.extend(data.values())
                except Exception as e:
                    logger.warning(f"Failed to load failures from {source}: {e}")

        return failures

    def _log_trade_block(
        self,
        symbol: str,
        action: str,
        quantity: float,
        strategy: str,
        result: TradeVerificationResult,
    ) -> None:
        """Log a blocked trade for analysis."""
        TRADE_BLOCKS_LOG.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "strategy": strategy,
            "reason": result.reason,
            "similar_failures": result.similar_failures,
            "confidence": result.confidence,
        }

        with open(TRADE_BLOCKS_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

        logger.warning(f"Trade blocked: {symbol} {action} {quantity} - {result.reason}")


# =============================================================================
# INTEGRATION WITH TRADING ORCHESTRATOR
# =============================================================================


def integrate_with_orchestrator():
    """
    Integrate pre-trade RAG check with TradingOrchestrator.

    Call this at system startup.
    """
    try:
        from src.orchestrator.main import TradingOrchestrator

        checker = PreTradeRAGCheck()

        # Store original execute_trade
        if hasattr(TradingOrchestrator, "_original_execute_trade"):
            return  # Already integrated

        original_execute = TradingOrchestrator.execute_trade

        def safe_execute_trade(self, symbol, action, quantity, strategy="unknown", **kwargs):
            # Run pre-trade RAG check
            result = checker.verify_trade_safe(
                symbol=symbol,
                action=action,
                quantity=quantity,
                strategy=strategy,
                market_conditions=kwargs.get("market_conditions"),
            )

            if not result.safe:
                logger.error(
                    f"Trade BLOCKED by RAG verification: {symbol} {action} {quantity}\n"
                    f"Reason: {result.reason}\n"
                    f"Similar failures: {result.similar_failures}"
                )
                return {
                    "success": False,
                    "blocked": True,
                    "reason": result.reason,
                    "recommendations": result.recommendations,
                }

            # Log warnings even for passed trades
            if result.recommendations:
                logger.warning(
                    f"Trade proceeding with warnings: {result.recommendations}"
                )

            # Execute original trade
            return original_execute(self, symbol, action, quantity, **kwargs)

        TradingOrchestrator._original_execute_trade = original_execute
        TradingOrchestrator.execute_trade = safe_execute_trade

        logger.info("Integrated PreTradeRAGCheck with TradingOrchestrator")

    except ImportError:
        logger.warning("TradingOrchestrator not available, skipping integration")


if __name__ == "__main__":
    """Demo the pre-trade RAG check."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("PRE-TRADE RAG VERIFICATION DEMO")
    print("=" * 80)

    checker = PreTradeRAGCheck()

    # Demo trades
    trades = [
        {"symbol": "SPY", "action": "BUY", "quantity": 10, "strategy": "momentum"},
        {"symbol": "NVDA", "action": "BUY", "quantity": 50, "strategy": "mean_reversion"},
        {"symbol": "BTC/USD", "action": "BUY", "quantity": 0.1, "strategy": "crypto_momentum"},
    ]

    for trade in trades:
        print(f"\n{'='*60}")
        print(f"Checking: {trade['action']} {trade['quantity']} {trade['symbol']}")
        print(f"Strategy: {trade['strategy']}")
        print("=" * 60)

        result = checker.verify_trade_safe(**trade)

        print(f"\n✅ Safe: {result.safe}")
        print(f"📊 Confidence: {result.confidence:.1%}")
        print(f"📝 Reason: {result.reason}")

        if result.similar_failures:
            print("\n⚠️  Similar past failures:")
            for failure in result.similar_failures[:3]:
                print(f"   - {failure['id']}: {failure['title']}")

        if result.recommendations:
            print("\n💡 Recommendations:")
            for rec in result.recommendations:
                print(f"   - {rec}")

    print("\n" + "=" * 80)
    print("Pre-trade RAG verification ready for integration")
    print("=" * 80)
