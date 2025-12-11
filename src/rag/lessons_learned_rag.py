"""
Lessons Learned RAG System

Stores and retrieves trading mistakes, bugs, and lessons learned using
vector similarity search. Integrates with pre-trade verification to
prevent repeating past mistakes.

Key Features:
1. Semantic search for similar past issues
2. Automatic ingestion of post-trade anomalies
3. Category-based filtering (size_error, execution, strategy, etc.)
4. Integration with verification pipeline

Author: Trading System
Created: 2025-12-11
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Try to import sentence transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("sentence-transformers not installed. Using keyword search fallback.")


@dataclass
class Lesson:
    """A single lesson learned entry."""

    id: str
    timestamp: str
    category: str
    title: str
    description: str
    root_cause: str
    prevention: str
    tags: list[str]
    severity: str  # "low", "medium", "high", "critical"
    financial_impact: Optional[float] = None
    symbol: Optional[str] = None
    embedding: Optional[list[float]] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "root_cause": self.root_cause,
            "prevention": self.prevention,
            "tags": self.tags,
            "severity": self.severity,
            "financial_impact": self.financial_impact,
            "symbol": self.symbol,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Lesson":
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            category=data["category"],
            title=data["title"],
            description=data["description"],
            root_cause=data["root_cause"],
            prevention=data["prevention"],
            tags=data.get("tags", []),
            severity=data.get("severity", "medium"),
            financial_impact=data.get("financial_impact"),
            symbol=data.get("symbol"),
            embedding=data.get("embedding"),
        )


class LessonsLearnedRAG:
    """
    RAG system for storing and retrieving lessons learned.

    Uses semantic search to find relevant past mistakes based on:
    - Trade context (symbol, side, amount)
    - Error type
    - Similar descriptions
    """

    def __init__(
        self,
        db_path: str = "data/rag/lessons_learned.json",
        model_name: str = "all-MiniLM-L6-v2",
    ):
        self.db_path = Path(db_path)
        self.model_name = model_name
        self.encoder = None
        self.lessons: list[Lesson] = []
        self.embeddings: Optional[np.ndarray] = None

        # Load existing lessons
        self._load_db()

        # Initialize encoder if available
        if EMBEDDINGS_AVAILABLE:
            try:
                self.encoder = SentenceTransformer(model_name)
                logger.info(f"Loaded embedding model: {model_name}")
                self._compute_embeddings()
            except Exception as e:
                logger.warning(f"Could not load embedding model: {e}")

    def add_lesson(
        self,
        category: str,
        title: str,
        description: str,
        root_cause: str,
        prevention: str,
        tags: Optional[list[str]] = None,
        severity: str = "medium",
        financial_impact: Optional[float] = None,
        symbol: Optional[str] = None,
    ) -> str:
        """
        Add a new lesson to the database.

        Args:
            category: Category (size_error, execution, strategy, data, etc.)
            title: Short title for the lesson
            description: Detailed description of what happened
            root_cause: What caused the issue
            prevention: How to prevent it in the future
            tags: Optional tags for filtering
            severity: Severity level
            financial_impact: Dollar impact if known
            symbol: Related symbol if applicable

        Returns:
            ID of the new lesson
        """
        lesson_id = f"lesson_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.lessons)}"

        lesson = Lesson(
            id=lesson_id,
            timestamp=datetime.now().isoformat(),
            category=category,
            title=title,
            description=description,
            root_cause=root_cause,
            prevention=prevention,
            tags=tags or [],
            severity=severity,
            financial_impact=financial_impact,
            symbol=symbol,
        )

        # Compute embedding if encoder available
        if self.encoder:
            text = f"{title} {description} {root_cause} {prevention}"
            lesson.embedding = self.encoder.encode(text).tolist()

        self.lessons.append(lesson)
        self._save_db()

        logger.info(f"Added lesson: {lesson_id} - {title}")
        return lesson_id

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        symbol: Optional[str] = None,
        top_k: int = 5,
    ) -> list[tuple[Lesson, float]]:
        """
        Search for relevant lessons.

        Args:
            query: Search query (natural language)
            category: Optional category filter
            symbol: Optional symbol filter
            top_k: Number of results to return

        Returns:
            List of (Lesson, relevance_score) tuples
        """
        if not self.lessons:
            return []

        # Filter by category/symbol first
        candidates = self.lessons
        if category:
            candidates = [l for l in candidates if l.category == category]
        if symbol:
            candidates = [l for l in candidates if l.symbol == symbol or l.symbol is None]

        if not candidates:
            return []

        # Semantic search if embeddings available
        if self.encoder and all(l.embedding for l in candidates):
            query_embedding = self.encoder.encode(query)

            scores = []
            for lesson in candidates:
                if lesson.embedding:
                    similarity = self._cosine_similarity(query_embedding, lesson.embedding)
                    scores.append((lesson, similarity))

            # Sort by similarity
            scores.sort(key=lambda x: x[1], reverse=True)
            return scores[:top_k]

        else:
            # Fallback to keyword search
            query_words = set(query.lower().split())

            scores = []
            for lesson in candidates:
                text = f"{lesson.title} {lesson.description} {lesson.root_cause}".lower()
                text_words = set(text.split())
                overlap = len(query_words & text_words)
                score = overlap / len(query_words) if query_words else 0
                scores.append((lesson, score))

            scores.sort(key=lambda x: x[1], reverse=True)
            return scores[:top_k]

    def get_prevention_checklist(
        self,
        category: Optional[str] = None,
    ) -> list[str]:
        """
        Get prevention checklist from lessons.

        Args:
            category: Optional category filter

        Returns:
            List of prevention steps
        """
        lessons = self.lessons
        if category:
            lessons = [l for l in lessons if l.category == category]

        # Extract unique prevention steps, prioritize by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_lessons = sorted(lessons, key=lambda l: severity_order.get(l.severity, 4))

        checklist = []
        seen = set()
        for lesson in sorted_lessons:
            if lesson.prevention not in seen:
                checklist.append(lesson.prevention)
                seen.add(lesson.prevention)

        return checklist

    def get_context_for_trade(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> dict[str, Any]:
        """
        Get relevant context for a trade decision.

        Args:
            symbol: Trading symbol
            side: "buy" or "sell"
            amount: Trade amount

        Returns:
            Dict with relevant lessons and warnings
        """
        # Build query from trade context
        query = f"{symbol} {side} trade amount {amount} dollars position size"

        # Search for relevant lessons
        results = self.search(query, top_k=3)

        # Also search for symbol-specific lessons
        symbol_results = self.search(symbol, symbol=symbol, top_k=2)

        # Combine and deduplicate
        all_results = {}
        for lesson, score in results + symbol_results:
            if lesson.id not in all_results:
                all_results[lesson.id] = (lesson, score)

        # Sort by score
        sorted_results = sorted(all_results.values(), key=lambda x: x[1], reverse=True)[:5]

        # Build context
        warnings = []
        prevention_steps = []

        for lesson, score in sorted_results:
            if score > 0.3:  # Relevance threshold
                warnings.append({
                    "title": lesson.title,
                    "severity": lesson.severity,
                    "prevention": lesson.prevention,
                    "relevance": score,
                })
                prevention_steps.append(lesson.prevention)

        return {
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "relevant_lessons": len(warnings),
            "warnings": warnings,
            "prevention_checklist": list(set(prevention_steps)),
        }

    def _cosine_similarity(self, a: np.ndarray, b: list) -> float:
        """Calculate cosine similarity between two vectors."""
        b_arr = np.array(b)
        return float(np.dot(a, b_arr) / (np.linalg.norm(a) * np.linalg.norm(b_arr)))

    def _compute_embeddings(self) -> None:
        """Compute embeddings for lessons without them."""
        if not self.encoder:
            return

        updated = False
        for lesson in self.lessons:
            if not lesson.embedding:
                text = f"{lesson.title} {lesson.description} {lesson.root_cause} {lesson.prevention}"
                lesson.embedding = self.encoder.encode(text).tolist()
                updated = True

        if updated:
            self._save_db()

    def _load_db(self) -> None:
        """Load lessons from database file."""
        if not self.db_path.exists():
            self._initialize_default_lessons()
            return

        try:
            with open(self.db_path) as f:
                data = json.load(f)
            self.lessons = [Lesson.from_dict(l) for l in data]
            logger.info(f"Loaded {len(self.lessons)} lessons from {self.db_path}")
        except Exception as e:
            logger.error(f"Error loading lessons DB: {e}")
            self._initialize_default_lessons()

    def _save_db(self) -> None:
        """Save lessons to database file."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        data = []
        for lesson in self.lessons:
            d = lesson.to_dict()
            if lesson.embedding:
                d["embedding"] = lesson.embedding
            data.append(d)

        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=2)

    def _initialize_default_lessons(self) -> None:
        """Initialize with default lessons from known issues."""
        default_lessons = [
            {
                "category": "size_error",
                "title": "200x Position Size Bug (Nov 3, 2025)",
                "description": "Trade executed at $1,600 instead of expected $8 due to unit confusion between shares and dollars",
                "root_cause": "Code calculated position in shares but passed to API expecting dollars",
                "prevention": "Always verify order size matches expected daily budget before submit. Add pre-trade size sanity check.",
                "tags": ["bug", "critical", "position_size", "unit_conversion"],
                "severity": "critical",
                "financial_impact": 1592.0,
            },
            {
                "category": "execution",
                "title": "Market Order Slippage Warning",
                "description": "Large market orders can experience significant slippage during volatile periods",
                "root_cause": "Market orders execute at best available price, which can vary widely",
                "prevention": "Use limit orders for large positions. Add slippage tolerance checks.",
                "tags": ["execution", "slippage", "market_order"],
                "severity": "medium",
            },
            {
                "category": "strategy",
                "title": "Momentum Signal False Positive",
                "description": "MACD crossover signals can be unreliable in low-volume conditions",
                "root_cause": "Technical indicators assume sufficient volume for price discovery",
                "prevention": "Add volume filter: only trade when volume > 80% of 20-day average",
                "tags": ["strategy", "momentum", "volume", "macd"],
                "severity": "low",
            },
            {
                "category": "data",
                "title": "Stale Data Detection",
                "description": "System used 24-hour old market data for trading decision",
                "root_cause": "Data freshness check was not enforced before trading",
                "prevention": "Verify data timestamp < 5 minutes before any trade. Block trading on stale data.",
                "tags": ["data", "freshness", "validation"],
                "severity": "high",
            },
        ]

        for lesson_data in default_lessons:
            self.add_lesson(**lesson_data)

        logger.info(f"Initialized {len(default_lessons)} default lessons")


def ingest_trade_anomaly(
    rag: LessonsLearnedRAG,
    anomaly_type: str,
    description: str,
    root_cause: str,
    symbol: Optional[str] = None,
    financial_impact: Optional[float] = None,
) -> str:
    """
    Convenience function to ingest a trade anomaly as a lesson.

    Args:
        rag: LessonsLearnedRAG instance
        anomaly_type: Type of anomaly
        description: What happened
        root_cause: Why it happened
        symbol: Related symbol
        financial_impact: Dollar impact

    Returns:
        Lesson ID
    """
    prevention = f"Add validation to prevent: {anomaly_type}"

    return rag.add_lesson(
        category=anomaly_type,
        title=f"Trade Anomaly: {anomaly_type}",
        description=description,
        root_cause=root_cause,
        prevention=prevention,
        severity="high" if financial_impact and financial_impact > 100 else "medium",
        financial_impact=financial_impact,
        symbol=symbol,
    )


if __name__ == "__main__":
    """Demo the lessons learned RAG system."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("LESSONS LEARNED RAG DEMO")
    print("=" * 80)

    # Initialize
    rag = LessonsLearnedRAG()

    print(f"\nLoaded {len(rag.lessons)} lessons")

    # Search demo
    print("\n" + "=" * 80)
    print("SEARCH: 'position size too large'")
    print("=" * 80)

    results = rag.search("position size too large", top_k=3)
    for lesson, score in results:
        print(f"\n[{score:.2f}] {lesson.title}")
        print(f"  Category: {lesson.category}")
        print(f"  Prevention: {lesson.prevention}")

    # Context for trade
    print("\n" + "=" * 80)
    print("CONTEXT FOR TRADE: SPY $1500 buy")
    print("=" * 80)

    context = rag.get_context_for_trade("SPY", "buy", 1500.0)
    print(f"\nRelevant lessons: {context['relevant_lessons']}")

    if context['warnings']:
        print("\nWarnings:")
        for w in context['warnings']:
            print(f"  [{w['severity'].upper()}] {w['title']}")
            print(f"    Prevention: {w['prevention']}")

    # Prevention checklist
    print("\n" + "=" * 80)
    print("PREVENTION CHECKLIST (size_error)")
    print("=" * 80)

    checklist = rag.get_prevention_checklist("size_error")
    for i, step in enumerate(checklist, 1):
        print(f"  {i}. {step}")
