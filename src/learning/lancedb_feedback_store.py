"""
LanceDB Feedback Store - Vector database for RLHF training data.

Provides:
1. Semantic search over feedback history
2. Time-travel queries for debugging model drift
3. Fast incremental updates (optimized for RLHF)
4. Model checkpoint versioning
5. Context-aware feedback retrieval

Replaces flat JSON files with vector database for richer context matching.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import lancedb
from fastembed import TextEmbedding

logger = logging.getLogger(__name__)


class LanceDBFeedbackStore:
    """
    Vector database for RLHF feedback storage and retrieval.

    Uses LanceDB for:
    - Fast semantic search over feedback contexts
    - Time-travel queries (see feedback at any checkpoint)
    - Multimodal storage (embeddings + metadata + raw context)
    - Efficient incremental updates
    """

    def __init__(
        self,
        db_path: str = "data/lancedb_feedback",
        table_name: str = "feedback_v1",
        embedding_model: str = "BAAI/bge-small-en-v1.5",
    ):
        """
        Initialize LanceDB feedback store.

        Args:
            db_path: Path to LanceDB database directory
            table_name: Table name for feedback storage
            embedding_model: FastEmbed model for semantic search
        """
        self.db_path = Path(db_path)
        self.table_name = table_name

        # Initialize LanceDB connection
        self.db = lancedb.connect(str(self.db_path))

        # Initialize FastEmbed for semantic search
        self.embedder = TextEmbedding(model_name=embedding_model)

        # Create or open table
        self._init_table()

        logger.info(
            "LanceDB feedback store initialized: %s (table: %s)",
            self.db_path,
            self.table_name,
        )

    def _init_table(self) -> None:
        """Initialize or open feedback table."""
        try:
            # Try to open existing table
            self.table = self.db.open_table(self.table_name)
            logger.info("Opened existing table: %s (%d records)", self.table_name, len(self.table))
        except Exception:
            # Create new table with schema
            logger.info("Creating new table: %s", self.table_name)
            # Will create on first insert
            self.table = None

    def add_feedback(
        self,
        feedback_id: str,
        is_positive: bool,
        context: dict[str, Any],
        reward: float,
        model_checkpoint: dict[str, float],
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """
        Add feedback to vector database.

        Args:
            feedback_id: Unique feedback identifier
            is_positive: True for thumbs up, False for thumbs down
            context: Decision context (strategy, market conditions, etc.)
            reward: Shaped reward value
            model_checkpoint: Current model state (alpha, beta, feature_weights)
            timestamp: ISO format timestamp (defaults to now)

        Returns:
            Inserted record metadata
        """
        timestamp = timestamp or datetime.now().isoformat()

        # Serialize context for embedding
        context_text = self._context_to_text(context)

        # Generate embedding
        embedding = list(self.embedder.embed([context_text]))[0].tolist()

        # Prepare record
        record = {
            "feedback_id": feedback_id,
            "timestamp": timestamp,
            "is_positive": is_positive,
            "reward": reward,
            "context_text": context_text,
            "context_json": json.dumps(context),
            "vector": embedding,
            "model_alpha": model_checkpoint.get("alpha", 1.0),
            "model_beta": model_checkpoint.get("beta", 1.0),
            "feature_weights": json.dumps(model_checkpoint.get("feature_weights", {})),
        }

        # Insert or update table
        if self.table is None:
            # Create table on first insert
            self.table = self.db.create_table(self.table_name, data=[record])
            logger.info("Created table %s with first record", self.table_name)
        else:
            # Append to existing table
            self.table.add([record])

        logger.debug(
            "Added feedback: %s (%s) at %s",
            feedback_id,
            "positive" if is_positive else "negative",
            timestamp,
        )

        return record

    def search_similar_contexts(
        self,
        query_context: dict[str, Any],
        limit: int = 10,
        filter_positive: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar feedback contexts using semantic search.

        Args:
            query_context: Context to find similar feedback for
            limit: Maximum number of results
            filter_positive: Filter by feedback type (None = all)

        Returns:
            List of similar feedback records with distance scores
        """
        if self.table is None:
            return []

        # Convert query context to text and embed
        query_text = self._context_to_text(query_context)
        query_embedding = list(self.embedder.embed([query_text]))[0].tolist()

        # Build filter if needed
        where_clause = None
        if filter_positive is not None:
            where_clause = f"is_positive = {filter_positive}"

        # Semantic search
        results = (
            self.table.search(query_embedding)
            .where(where_clause) if where_clause else self.table.search(query_embedding)
        ).limit(limit).to_list()

        logger.debug(
            "Found %d similar contexts (filter_positive=%s)",
            len(results),
            filter_positive,
        )

        return results

    def get_feedback_at_checkpoint(
        self,
        alpha: float,
        beta: float,
        tolerance: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Time-travel query: Get feedback from when model was at specific checkpoint.

        Useful for debugging model drift - "What feedback did we see when alpha=10?"

        Args:
            alpha: Model alpha value at checkpoint
            beta: Model beta value at checkpoint
            tolerance: Tolerance for checkpoint matching

        Returns:
            Feedback records near that checkpoint
        """
        if self.table is None:
            return []

        # Query by model checkpoint values
        results = (
            self.table
            .search()
            .where(
                f"model_alpha >= {alpha - tolerance} AND model_alpha <= {alpha + tolerance} "
                f"AND model_beta >= {beta - tolerance} AND model_beta <= {beta + tolerance}"
            )
            .to_list()
        )

        logger.info(
            "Time-travel query: Found %d records at checkpoint α=%.1f, β=%.1f",
            len(results),
            alpha,
            beta,
        )

        return results

    def get_recent_feedback(
        self,
        limit: int = 100,
        filter_positive: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get most recent feedback records.

        Args:
            limit: Maximum number of results
            filter_positive: Filter by feedback type (None = all)

        Returns:
            Recent feedback records, newest first
        """
        if self.table is None:
            return []

        # Build filter
        where_clause = None
        if filter_positive is not None:
            where_clause = f"is_positive = {filter_positive}"

        # Query with filter
        query = self.table.search()
        if where_clause:
            query = query.where(where_clause)

        results = query.limit(limit).to_list()

        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return results[:limit]

    def get_statistics(self) -> dict[str, Any]:
        """Get feedback store statistics."""
        if self.table is None:
            return {
                "total_feedback": 0,
                "positive": 0,
                "negative": 0,
                "satisfaction_rate": 0.0,
                "table_exists": False,
            }

        all_feedback = self.table.search().to_list()
        positive_count = sum(1 for f in all_feedback if f.get("is_positive", False))
        negative_count = len(all_feedback) - positive_count

        return {
            "total_feedback": len(all_feedback),
            "positive": positive_count,
            "negative": negative_count,
            "satisfaction_rate": (
                100 * positive_count / len(all_feedback) if len(all_feedback) > 0 else 0.0
            ),
            "table_exists": True,
            "db_path": str(self.db_path),
            "table_name": self.table_name,
        }

    def _context_to_text(self, context: dict[str, Any]) -> str:
        """
        Convert context dict to text for embedding.

        Prioritizes key fields that affect decision quality.
        """
        parts = []

        # Decision type (most important)
        if "decision_type" in context:
            parts.append(f"Decision: {context['decision_type']}")

        # Market conditions
        if "market_regime" in context:
            parts.append(f"Market: {context['market_regime']}")

        if "volatility" in context:
            parts.append(f"Volatility: {context['volatility']:.2%}")

        # Strategy info
        if "strategy" in context:
            parts.append(f"Strategy: {context['strategy']}")

        if "signal_strength" in context:
            parts.append(f"Signal: {context['signal_strength']}")

        # Trade details
        if "ticker" in context:
            parts.append(f"Ticker: {context['ticker']}")

        if "action" in context:
            parts.append(f"Action: {context['action']}")

        # Fallback: serialize entire context
        if not parts:
            parts.append(json.dumps(context))

        return " | ".join(parts)


def get_feedback_store() -> LanceDBFeedbackStore:
    """
    Get singleton feedback store instance.

    Returns:
        Initialized LanceDB feedback store
    """
    return LanceDBFeedbackStore()
