"""
Lessons Learned RAG Store - Trading System Knowledge Base

This module stores and retrieves lessons learned from trading mistakes,
system failures, and strategic insights. Uses vector embeddings for
semantic search to prevent repeating past mistakes.

Key Features:
- Store lessons with severity, category, and impact metrics
- Semantic search for relevant past lessons before making decisions
- Automatic validation against known failure patterns
- Integration with pre-commit hooks for code changes
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

STORAGE_DIR = Path("data/rag")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
LESSONS_DB_PATH = STORAGE_DIR / "lessons_learned.db"


class LessonSeverity(Enum):
    """Severity levels for lessons learned."""
    CRITICAL = "critical"      # Financial loss, data corruption, lying to CEO
    HIGH = "high"              # System failures, missed trades, wrong calculations
    MEDIUM = "medium"          # Suboptimal decisions, minor bugs
    LOW = "low"                # Style issues, minor improvements


class LessonCategory(Enum):
    """Categories for lessons learned."""
    TRADING_LOGIC = "trading_logic"           # Strategy, signals, execution
    DATA_INTEGRITY = "data_integrity"         # Stale data, wrong sources
    RISK_MANAGEMENT = "risk_management"       # Position sizing, stop-losses
    AUTOMATION = "automation"                 # GitHub Actions, scheduling
    VERIFICATION = "verification"             # Anti-lying, fact-checking
    CODE_QUALITY = "code_quality"             # Bugs, tests, refactoring
    CRYPTO_SPECIFIC = "crypto_specific"       # Crypto-only lessons
    COMMUNICATION = "communication"           # CEO reports, clarity


@dataclass
class Lesson:
    """A single lesson learned entry."""
    lesson_id: str
    title: str
    description: str
    root_cause: str
    resolution: str
    prevention: str
    severity: LessonSeverity
    category: LessonCategory
    date_learned: datetime
    impact_description: str = ""
    financial_impact: float = 0.0  # Dollar amount if applicable
    related_files: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_searchable_text(self) -> str:
        """Convert lesson to searchable text for embedding."""
        return f"""
        Title: {self.title}
        Description: {self.description}
        Root Cause: {self.root_cause}
        Resolution: {self.resolution}
        Prevention: {self.prevention}
        Impact: {self.impact_description}
        Category: {self.category.value}
        Tags: {', '.join(self.tags)}
        """


class LessonsLearnedStore:
    """
    RAG-backed store for lessons learned from trading system operation.

    Usage:
        store = LessonsLearnedStore()

        # Add a new lesson
        store.add_lesson(Lesson(...))

        # Check for relevant lessons before making a decision
        relevant = store.search_lessons("crypto trading volume threshold")

        # Validate a proposed action against past failures
        warnings = store.validate_action("execute large order", context={...})
    """

    def __init__(self, db_path: Path = LESSONS_DB_PATH):
        self.db_path = Path(db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.execute("PRAGMA journal_mode=WAL;")
        self._create_schema()
        self._embedder = None

    @property
    def embedder(self):
        """Lazy-load embedder to avoid import errors."""
        if self._embedder is None:
            try:
                from .vector_db.embedder import get_embedder
                self._embedder = get_embedder()
            except ImportError:
                logger.warning("Embedder not available - using keyword search only")
                self._embedder = None
        return self._embedder

    def _create_schema(self) -> None:
        """Create database schema for lessons storage."""
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                root_cause TEXT NOT NULL,
                resolution TEXT NOT NULL,
                prevention TEXT NOT NULL,
                severity TEXT NOT NULL,
                category TEXT NOT NULL,
                date_learned TEXT NOT NULL,
                impact_description TEXT,
                financial_impact REAL DEFAULT 0.0,
                related_files TEXT,
                tags TEXT,
                searchable_text TEXT NOT NULL,
                embedding BLOB,
                embedding_dim INTEGER,
                created_at TEXT NOT NULL
            );
        """)

        # Index for fast category/severity lookups
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_lessons_category
            ON lessons(category);
        """)
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_lessons_severity
            ON lessons(severity);
        """)

        self.connection.commit()

    def add_lesson(self, lesson: Lesson) -> bool:
        """
        Add a new lesson to the store.

        Args:
            lesson: The lesson to add

        Returns:
            True if added successfully
        """
        searchable_text = lesson.to_searchable_text()

        # Generate embedding if embedder available
        embedding = None
        embedding_dim = 0
        if self.embedder:
            try:
                embedding_array = self.embedder.embed(searchable_text)
                embedding = embedding_array.tobytes()
                embedding_dim = len(embedding_array)
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")

        try:
            self.connection.execute("""
                INSERT OR REPLACE INTO lessons (
                    id, title, description, root_cause, resolution, prevention,
                    severity, category, date_learned, impact_description,
                    financial_impact, related_files, tags, searchable_text,
                    embedding, embedding_dim, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lesson.lesson_id,
                lesson.title,
                lesson.description,
                lesson.root_cause,
                lesson.resolution,
                lesson.prevention,
                lesson.severity.value,
                lesson.category.value,
                lesson.date_learned.isoformat(),
                lesson.impact_description,
                lesson.financial_impact,
                json.dumps(lesson.related_files),
                json.dumps(lesson.tags),
                searchable_text,
                embedding,
                embedding_dim,
                datetime.now(timezone.utc).isoformat()
            ))
            self.connection.commit()
            logger.info(f"Added lesson: {lesson.lesson_id} - {lesson.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to add lesson: {e}")
            return False

    def search_lessons(
        self,
        query: str,
        top_k: int = 5,
        category: LessonCategory | None = None,
        min_severity: LessonSeverity | None = None
    ) -> list[dict[str, Any]]:
        """
        Search for relevant lessons using semantic similarity.

        Args:
            query: Search query
            top_k: Number of results to return
            category: Filter by category
            min_severity: Filter by minimum severity

        Returns:
            List of matching lessons with similarity scores
        """
        # Build base query
        sql = "SELECT * FROM lessons WHERE 1=1"
        params = []

        if category:
            sql += " AND category = ?"
            params.append(category.value)

        if min_severity:
            severity_order = ["low", "medium", "high", "critical"]
            min_idx = severity_order.index(min_severity.value)
            valid_severities = severity_order[min_idx:]
            placeholders = ",".join(["?" for _ in valid_severities])
            sql += f" AND severity IN ({placeholders})"
            params.extend(valid_severities)

        cursor = self.connection.execute(sql, params)
        rows = cursor.fetchall()

        if not rows:
            return []

        # If embedder available, use semantic search
        if self.embedder:
            try:
                query_embedding = self.embedder.embed(query)
                results = []

                for row in rows:
                    if row[14]:  # embedding column
                        embedding_dim = row[15]
                        stored_embedding = np.frombuffer(row[14], dtype=np.float32)
                        if len(stored_embedding) == embedding_dim:
                            similarity = np.dot(query_embedding, stored_embedding) / (
                                np.linalg.norm(query_embedding) * np.linalg.norm(stored_embedding)
                            )
                            results.append((row, float(similarity)))

                # Sort by similarity
                results.sort(key=lambda x: x[1], reverse=True)
                return [self._row_to_dict(r[0], r[1]) for r in results[:top_k]]

            except Exception as e:
                logger.warning(f"Semantic search failed, using keyword: {e}")

        # Fallback to keyword search
        query_terms = query.lower().split()
        results = []
        for row in rows:
            searchable = row[13].lower()  # searchable_text column
            score = sum(1 for term in query_terms if term in searchable)
            if score > 0:
                results.append((row, score / len(query_terms)))

        results.sort(key=lambda x: x[1], reverse=True)
        return [self._row_to_dict(r[0], r[1]) for r in results[:top_k]]

    def validate_action(
        self,
        action: str,
        context: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Validate a proposed action against past lessons.

        Args:
            action: Description of the proposed action
            context: Additional context (symbol, amount, etc.)

        Returns:
            List of warnings based on relevant past lessons
        """
        # Build search query from action and context
        search_query = f"{action} {' '.join(str(v) for v in context.values())}"

        # Search for relevant lessons, prioritizing critical ones
        relevant_lessons = self.search_lessons(
            search_query,
            top_k=10,
            min_severity=LessonSeverity.MEDIUM
        )

        warnings = []
        for lesson in relevant_lessons:
            if lesson["similarity"] > 0.3:  # Threshold for relevance
                warnings.append({
                    "lesson_id": lesson["id"],
                    "title": lesson["title"],
                    "prevention": lesson["prevention"],
                    "severity": lesson["severity"],
                    "similarity": lesson["similarity"],
                    "warning": f"PAST LESSON: {lesson['title']} - {lesson['prevention']}"
                })

        return warnings

    def get_critical_lessons(self) -> list[dict[str, Any]]:
        """Get all critical severity lessons for mandatory review."""
        cursor = self.connection.execute(
            "SELECT * FROM lessons WHERE severity = 'critical' ORDER BY date_learned DESC"
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def _row_to_dict(self, row, similarity: float = 0.0) -> dict[str, Any]:
        """Convert database row to dictionary."""
        return {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "root_cause": row[3],
            "resolution": row[4],
            "prevention": row[5],
            "severity": row[6],
            "category": row[7],
            "date_learned": row[8],
            "impact_description": row[9],
            "financial_impact": row[10],
            "related_files": json.loads(row[11]) if row[11] else [],
            "tags": json.loads(row[12]) if row[12] else [],
            "similarity": similarity
        }

    def export_for_training(self, output_path: Path) -> int:
        """
        Export lessons for ML model training.

        Args:
            output_path: Path to save JSONL file

        Returns:
            Number of lessons exported
        """
        cursor = self.connection.execute("SELECT * FROM lessons")
        rows = cursor.fetchall()

        with open(output_path, 'w') as f:
            for row in rows:
                lesson_dict = self._row_to_dict(row)
                f.write(json.dumps(lesson_dict) + "\n")

        logger.info(f"Exported {len(rows)} lessons to {output_path}")
        return len(rows)


def seed_initial_lessons(store: LessonsLearnedStore) -> int:
    """
    Seed the store with known lessons from system history.

    Returns:
        Number of lessons added
    """
    initial_lessons = [
        Lesson(
            lesson_id="LESSON-001",
            title="200x Order Amount Error",
            description="Autonomous trader deployed $1,600 instead of planned $8/day",
            root_cause="Wrong script executed (autonomous_trader.py vs main.py)",
            resolution="Validated correct script, added amount validation",
            prevention="ALWAYS validate order amounts. Reject orders >10x expected. Use explicit script paths.",
            severity=LessonSeverity.CRITICAL,
            category=LessonCategory.TRADING_LOGIC,
            date_learned=datetime(2025, 11, 3, tzinfo=timezone.utc),
            impact_description="Deployed 200x more capital than intended",
            financial_impact=1600.0,
            related_files=["scripts/autonomous_trader.py", "scripts/main.py"],
            tags=["order-validation", "capital-protection", "script-execution"]
        ),
        Lesson(
            lesson_id="LESSON-002",
            title="Stale Data Trading Decision",
            description="System used 5-day old state data for trading decisions",
            root_cause="No staleness detection in system state loading",
            resolution="Added timestamp validation and staleness warnings",
            prevention="ALWAYS check data freshness. Reject data >24 hours old without explicit warning.",
            severity=LessonSeverity.HIGH,
            category=LessonCategory.DATA_INTEGRITY,
            date_learned=datetime(2025, 11, 4, tzinfo=timezone.utc),
            impact_description="Trading decisions made on outdated market conditions",
            related_files=["data/system_state.json", "scripts/state_manager.py"],
            tags=["data-freshness", "staleness", "validation"]
        ),
        Lesson(
            lesson_id="LESSON-003",
            title="Anti-Lying Violation - Wrong Execution Date",
            description="CTO claimed 'Next execution: Tomorrow Nov 8' but that was a Saturday",
            root_cause="Failed to verify calendar before claiming execution timing",
            resolution="Corrected to Monday Nov 10, added calendar verification",
            prevention="ALWAYS verify day of week and market hours before claiming execution dates.",
            severity=LessonSeverity.CRITICAL,
            category=LessonCategory.VERIFICATION,
            date_learned=datetime(2025, 11, 7, tzinfo=timezone.utc),
            impact_description="CEO trust violation - Strike 1 of 3",
            tags=["anti-lying", "verification", "market-hours", "trust"]
        ),
        Lesson(
            lesson_id="LESSON-004",
            title="GitHub Actions Disabled Without Notice",
            description="5-day trading gap due to disabled GitHub Actions workflow",
            root_cause="Python 3.14 protobuf incompatibility + workflow disabled",
            resolution="Upgraded protobuf, re-enabled workflow",
            prevention="Monitor automation health daily. Alert on >24h execution gap.",
            severity=LessonSeverity.HIGH,
            category=LessonCategory.AUTOMATION,
            date_learned=datetime(2025, 11, 11, tzinfo=timezone.utc),
            impact_description="Missed 5 trading days",
            related_files=[".github/workflows/daily-trading.yml"],
            tags=["automation", "github-actions", "monitoring"]
        ),
        Lesson(
            lesson_id="LESSON-005",
            title="Crypto MACD Threshold Too Conservative",
            description="MACD < 0 filter rejected valid crypto trades during consolidation",
            root_cause="Stock-market MACD thresholds applied to crypto",
            resolution="Changed threshold from 0 to -50 for crypto",
            prevention="Crypto needs wider thresholds due to higher volatility. Test separately.",
            severity=LessonSeverity.MEDIUM,
            category=LessonCategory.CRYPTO_SPECIFIC,
            date_learned=datetime(2025, 12, 7, tzinfo=timezone.utc),
            impact_description="Missed valid crypto trading opportunities",
            related_files=["src/strategies/crypto_strategy.py"],
            tags=["crypto", "macd", "thresholds", "volatility"]
        ),
        Lesson(
            lesson_id="LESSON-006",
            title="Alpaca Crypto Stop-Loss Not Supported",
            description="Stop-loss orders fail silently for crypto positions",
            root_cause="Alpaca crypto trading does not support stop-loss orders",
            resolution="Implemented manual position monitoring with software stop-loss",
            prevention="Check broker capabilities before assuming order types work. Crypto needs manual monitoring.",
            severity=LessonSeverity.MEDIUM,
            category=LessonCategory.CRYPTO_SPECIFIC,
            date_learned=datetime(2025, 11, 17, tzinfo=timezone.utc),
            related_files=["src/strategies/crypto_strategy.py"],
            tags=["crypto", "stop-loss", "alpaca", "risk-management"]
        ),
    ]

    count = 0
    for lesson in initial_lessons:
        if store.add_lesson(lesson):
            count += 1

    logger.info(f"Seeded {count} initial lessons")
    return count


# Pre-trade validation hook
def validate_trade_against_lessons(
    symbol: str,
    amount: float,
    action: str,
    store: LessonsLearnedStore | None = None
) -> tuple[bool, list[str]]:
    """
    Validate a proposed trade against lessons learned.

    Args:
        symbol: Trading symbol
        amount: Dollar amount
        action: Buy/Sell
        store: LessonsLearnedStore instance (creates new if None)

    Returns:
        (is_valid, list of warnings)
    """
    if store is None:
        store = LessonsLearnedStore()

    context = {
        "symbol": symbol,
        "amount": amount,
        "action": action
    }

    warnings_list = store.validate_action(f"{action} {symbol} ${amount}", context)

    # Check for critical warnings
    critical_warnings = [w for w in warnings_list if w["severity"] == "critical"]

    if critical_warnings:
        return False, [w["warning"] for w in critical_warnings]

    return True, [w["warning"] for w in warnings_list]
