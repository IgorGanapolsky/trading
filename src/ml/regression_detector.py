"""
ML-based Regression Detector

Uses vector embeddings to detect potential regressions by comparing:
1. Code changes against known bug patterns
2. New errors against historical errors
3. Performance metrics against expected baselines

This creates a learned model of "what goes wrong" and flags similar patterns.

Author: Trading System
Created: December 2025
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Try to load embedding models
EMBEDDINGS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer

    EMBEDDINGS_AVAILABLE = True
except ImportError:
    pass


@dataclass
class RegressionPattern:
    """A learned pattern that indicates potential regression."""

    pattern_id: str
    description: str
    embedding: np.ndarray | None
    severity: str  # "low", "medium", "high", "critical"
    category: str  # "performance", "error", "logic", "data"
    occurrences: int
    last_seen: str
    prevention: str


@dataclass
class RegressionAlert:
    """Alert when regression pattern is detected."""

    pattern_id: str
    similarity: float
    description: str
    severity: str
    prevention: str
    context: dict[str, Any]


class RegressionDetector:
    """
    ML-powered regression detection using vector similarity.

    Maintains a database of known regression patterns and compares
    new code/errors/metrics against them.
    """

    def __init__(self, patterns_path: str | Path | None = None):
        self.patterns_path = Path(patterns_path or "data/regression_patterns.json")
        self.patterns: list[RegressionPattern] = []
        self.model = None
        self.similarity_threshold = 0.75

        if EMBEDDINGS_AVAILABLE:
            try:
                self.model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("RegressionDetector initialized with embeddings")
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")

        self._load_patterns()

    def _load_patterns(self) -> None:
        """Load regression patterns from disk."""
        if not self.patterns_path.exists():
            self.patterns = []
            return

        try:
            with open(self.patterns_path) as f:
                data = json.load(f)

            self.patterns = []
            for p in data.get("patterns", []):
                embedding = None
                if p.get("embedding"):
                    embedding = np.array(p["embedding"])

                self.patterns.append(RegressionPattern(
                    pattern_id=p["pattern_id"],
                    description=p["description"],
                    embedding=embedding,
                    severity=p["severity"],
                    category=p["category"],
                    occurrences=p.get("occurrences", 1),
                    last_seen=p.get("last_seen", ""),
                    prevention=p.get("prevention", ""),
                ))

            logger.info(f"Loaded {len(self.patterns)} regression patterns")

        except Exception as e:
            logger.warning(f"Failed to load patterns: {e}")
            self.patterns = []

    def _save_patterns(self) -> None:
        """Save regression patterns to disk."""
        self.patterns_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "description": p.description,
                    "embedding": p.embedding.tolist() if p.embedding is not None else None,
                    "severity": p.severity,
                    "category": p.category,
                    "occurrences": p.occurrences,
                    "last_seen": p.last_seen,
                    "prevention": p.prevention,
                }
                for p in self.patterns
            ],
            "updated_at": datetime.utcnow().isoformat(),
        }

        with open(self.patterns_path, "w") as f:
            json.dump(data, f, indent=2)

    def _encode(self, text: str) -> np.ndarray | None:
        """Encode text to embedding vector."""
        if not self.model:
            return None
        try:
            return self.model.encode(text, normalize_embeddings=True)
        except Exception as e:
            logger.debug(f"Encoding failed: {e}")
            return None

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return float(np.dot(a, b))

    def learn_pattern(
        self,
        description: str,
        severity: str = "medium",
        category: str = "error",
        prevention: str = "",
    ) -> str:
        """
        Learn a new regression pattern from an observed issue.

        Called when:
        - A bug is fixed
        - An anomaly is detected
        - A test fails
        """
        pattern_id = f"pattern_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{len(self.patterns)}"

        embedding = self._encode(description)

        # Check if similar pattern already exists
        for existing in self.patterns:
            if existing.embedding is not None and embedding is not None:
                similarity = self._cosine_similarity(existing.embedding, embedding)
                if similarity > 0.9:
                    # Update existing pattern
                    existing.occurrences += 1
                    existing.last_seen = datetime.utcnow().isoformat()
                    self._save_patterns()
                    logger.info(f"Updated existing pattern: {existing.pattern_id}")
                    return existing.pattern_id

        # Add new pattern
        pattern = RegressionPattern(
            pattern_id=pattern_id,
            description=description,
            embedding=embedding,
            severity=severity,
            category=category,
            occurrences=1,
            last_seen=datetime.utcnow().isoformat(),
            prevention=prevention,
        )
        self.patterns.append(pattern)
        self._save_patterns()

        logger.info(f"Learned new pattern: {pattern_id}")
        return pattern_id

    def check_for_regression(
        self,
        context: str,
        category: str | None = None,
    ) -> list[RegressionAlert]:
        """
        Check if given context matches known regression patterns.

        Args:
            context: Text describing the current situation (error, code change, etc.)
            category: Optional category filter

        Returns:
            List of RegressionAlert for matching patterns
        """
        if not self.patterns:
            return []

        embedding = self._encode(context)
        if embedding is None:
            # Fall back to keyword matching
            return self._keyword_check(context, category)

        alerts = []
        for pattern in self.patterns:
            if category and pattern.category != category:
                continue

            if pattern.embedding is None:
                continue

            similarity = self._cosine_similarity(embedding, pattern.embedding)
            if similarity >= self.similarity_threshold:
                alerts.append(RegressionAlert(
                    pattern_id=pattern.pattern_id,
                    similarity=similarity,
                    description=pattern.description,
                    severity=pattern.severity,
                    prevention=pattern.prevention,
                    context={"category": pattern.category, "occurrences": pattern.occurrences},
                ))

        # Sort by similarity
        alerts.sort(key=lambda x: x.similarity, reverse=True)
        return alerts[:5]  # Top 5 matches

    def _keyword_check(self, context: str, category: str | None) -> list[RegressionAlert]:
        """Fallback keyword-based matching when embeddings unavailable."""
        context_lower = context.lower()
        alerts = []

        for pattern in self.patterns:
            if category and pattern.category != category:
                continue

            # Simple keyword matching
            desc_words = set(pattern.description.lower().split())
            context_words = set(context_lower.split())
            common = desc_words & context_words

            if len(common) >= 3:  # At least 3 common words
                similarity = len(common) / max(len(desc_words), 1)
                if similarity >= 0.3:
                    alerts.append(RegressionAlert(
                        pattern_id=pattern.pattern_id,
                        similarity=similarity,
                        description=pattern.description,
                        severity=pattern.severity,
                        prevention=pattern.prevention,
                        context={"category": pattern.category, "match_type": "keyword"},
                    ))

        alerts.sort(key=lambda x: x.similarity, reverse=True)
        return alerts[:5]

    def check_error(self, error_message: str, traceback: str = "") -> list[RegressionAlert]:
        """Check if an error matches known regression patterns."""
        context = f"Error: {error_message}\n{traceback}"
        return self.check_for_regression(context, category="error")

    def check_performance(
        self,
        metric_name: str,
        current_value: float,
        expected_value: float,
    ) -> list[RegressionAlert]:
        """Check if performance degradation matches known patterns."""
        degradation = (expected_value - current_value) / max(expected_value, 1e-6)
        if degradation > 0.1:  # >10% degradation
            context = f"Performance regression in {metric_name}: {degradation*100:.1f}% degradation"
            return self.check_for_regression(context, category="performance")
        return []

    def get_summary(self) -> dict[str, Any]:
        """Get summary of learned patterns."""
        by_category = {}
        by_severity = {}

        for p in self.patterns:
            by_category[p.category] = by_category.get(p.category, 0) + 1
            by_severity[p.severity] = by_severity.get(p.severity, 0) + 1

        return {
            "total_patterns": len(self.patterns),
            "by_category": by_category,
            "by_severity": by_severity,
            "embeddings_available": EMBEDDINGS_AVAILABLE,
        }


# Singleton instance
_detector: RegressionDetector | None = None


def get_regression_detector() -> RegressionDetector:
    """Get or create singleton regression detector."""
    global _detector
    if _detector is None:
        _detector = RegressionDetector()
    return _detector
