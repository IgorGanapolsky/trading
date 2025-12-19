"""
Pipeline Checkpoint System for Trading Gates.

Implements LangGraph-style checkpointing for fault-tolerant trade execution:
- Checkpoint after expensive gates (Momentum, Sentiment, Risk)
- Resume from last successful checkpoint on failure
- Full audit trail of gate decisions

Based on LangGraph checkpointing patterns (Dec 2025).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Checkpoint storage location
CHECKPOINT_DB = Path(os.getenv("CHECKPOINT_DB", "data/checkpoints/pipeline.db"))


@dataclass
class PipelineCheckpoint:
    """Snapshot of pipeline state at a checkpoint."""

    thread_id: str  # Unique execution ID (e.g., "trade:AAPL:2025-12-16T14:30:00")
    checkpoint_id: str  # Sequential checkpoint ID (e.g., "gate_1_momentum")
    gate_index: int  # Gate number (0, 1, 1.5, 2, 3, 3.5, 4)
    gate_name: str  # Human-readable gate name
    ticker: str
    context_json: str  # Serialized TradeContext
    results_json: str  # Serialized list[GateResult]
    created_at: str  # ISO timestamp
    status: str  # "success", "failed", "in_progress"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PipelineCheckpointer:
    """
    SQLite-based checkpointer for trading gate pipeline.

    Provides:
    - save_checkpoint(): Persist state after each gate
    - get_latest_checkpoint(): Resume from last successful checkpoint
    - get_checkpoint_history(): Full audit trail
    """

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else CHECKPOINT_DB
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Create checkpoint table if not exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    gate_index REAL NOT NULL,
                    gate_name TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    results_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    UNIQUE(thread_id, checkpoint_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_thread_id ON checkpoints(thread_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ticker_date ON checkpoints(ticker, created_at)
            """)
            conn.commit()

    def generate_thread_id(self, ticker: str, strategy: str = "gate_pipeline") -> str:
        """Generate unique thread ID for a trade execution."""
        timestamp = datetime.now(timezone.utc).isoformat()
        return f"trade:{strategy}:{ticker}:{timestamp}"

    def save_checkpoint(
        self,
        thread_id: str,
        gate_index: float,
        gate_name: str,
        ticker: str,
        context: Any,
        results: list[Any],
        status: str = "success",
    ) -> PipelineCheckpoint:
        """
        Save a checkpoint after a gate execution.

        Args:
            thread_id: Unique execution ID
            gate_index: Gate number (0, 1, 1.5, 2, 3, 3.5, 4)
            gate_name: Human-readable gate name
            ticker: Stock symbol
            context: TradeContext dataclass
            results: List of GateResult dataclasses
            status: "success", "failed", or "in_progress"

        Returns:
            PipelineCheckpoint with saved data
        """
        checkpoint_id = f"gate_{gate_index}_{gate_name}"
        created_at = datetime.now(timezone.utc).isoformat()

        # Serialize context and results
        context_dict = self._serialize_context(context)
        results_list = [self._serialize_result(r) for r in results]

        checkpoint = PipelineCheckpoint(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            gate_index=gate_index,
            gate_name=gate_name,
            ticker=ticker,
            context_json=json.dumps(context_dict),
            results_json=json.dumps(results_list),
            created_at=created_at,
            status=status,
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO checkpoints
                (thread_id, checkpoint_id, gate_index, gate_name, ticker,
                 context_json, results_json, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    checkpoint.thread_id,
                    checkpoint.checkpoint_id,
                    checkpoint.gate_index,
                    checkpoint.gate_name,
                    checkpoint.ticker,
                    checkpoint.context_json,
                    checkpoint.results_json,
                    checkpoint.created_at,
                    checkpoint.status,
                ),
            )
            conn.commit()

        logger.debug(
            "Checkpoint saved: %s gate=%s status=%s",
            thread_id,
            gate_name,
            status,
        )
        return checkpoint

    def get_latest_checkpoint(self, thread_id: str) -> PipelineCheckpoint | None:
        """Get the most recent successful checkpoint for a thread."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM checkpoints
                WHERE thread_id = ? AND status = 'success'
                ORDER BY gate_index DESC
                LIMIT 1
            """,
                (thread_id,),
            )
            row = cursor.fetchone()

        if row:
            d = dict(row)
            d.pop("id", None)  # Remove auto-generated ID
            return PipelineCheckpoint(**d)
        return None

    def get_checkpoint_at_gate(
        self, thread_id: str, gate_index: float
    ) -> PipelineCheckpoint | None:
        """Get checkpoint at a specific gate."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM checkpoints
                WHERE thread_id = ? AND gate_index = ?
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (thread_id, gate_index),
            )
            row = cursor.fetchone()

        if row:
            d = dict(row)
            d.pop("id", None)
            return PipelineCheckpoint(**d)
        return None

    def get_checkpoint_history(self, thread_id: str) -> list[PipelineCheckpoint]:
        """Get all checkpoints for a thread (audit trail)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM checkpoints
                WHERE thread_id = ?
                ORDER BY gate_index ASC
            """,
                (thread_id,),
            )
            rows = cursor.fetchall()

        return [
            PipelineCheckpoint(**{k: v for k, v in dict(row).items() if k != "id"}) for row in rows
        ]

    def get_recent_checkpoints(
        self, ticker: str | None = None, limit: int = 50
    ) -> list[PipelineCheckpoint]:
        """Get recent checkpoints, optionally filtered by ticker."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if ticker:
                cursor = conn.execute(
                    """
                    SELECT * FROM checkpoints
                    WHERE ticker = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (ticker, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM checkpoints
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (limit,),
                )
            rows = cursor.fetchall()

        return [
            PipelineCheckpoint(**{k: v for k, v in dict(row).items() if k != "id"}) for row in rows
        ]

    def cleanup_old_checkpoints(self, days_to_keep: int = 30) -> int:
        """Remove checkpoints older than specified days."""
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_to_keep)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM checkpoints
                WHERE created_at < ?
            """,
                (cutoff,),
            )
            deleted = cursor.rowcount
            conn.commit()

        logger.info("Cleaned up %d old checkpoints (older than %d days)", deleted, days_to_keep)
        return deleted

    def _serialize_context(self, context: Any) -> dict[str, Any]:
        """Serialize TradeContext to dict."""
        if hasattr(context, "__dataclass_fields__"):
            return asdict(context)
        if hasattr(context, "to_dict"):
            return context.to_dict()
        return {"raw": str(context)}

    def _serialize_result(self, result: Any) -> dict[str, Any]:
        """Serialize GateResult to dict."""
        if hasattr(result, "to_dict"):
            return result.to_dict()
        if hasattr(result, "__dataclass_fields__"):
            d = asdict(result)
            # Convert Enum to string
            if "status" in d and hasattr(d["status"], "value"):
                d["status"] = d["status"].value
            return d
        return {"raw": str(result)}


# Singleton instance
_checkpointer: PipelineCheckpointer | None = None


def get_checkpointer() -> PipelineCheckpointer:
    """Get or create global checkpointer instance."""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = PipelineCheckpointer()
        logger.info("Pipeline checkpointer initialized: %s", _checkpointer.db_path)
    return _checkpointer


# Gate checkpoint configuration
# Which gates should trigger checkpoints (expensive/critical gates)
CHECKPOINT_GATES = {
    1: "momentum",  # After momentum analysis (expensive)
    3: "sentiment",  # After LLM sentiment (costs money)
    4: "risk",  # After risk sizing (prevents duplicate orders)
}


def should_checkpoint(gate_index: float) -> bool:
    """Check if we should save a checkpoint at this gate."""
    return gate_index in CHECKPOINT_GATES
