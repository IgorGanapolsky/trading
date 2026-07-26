"""
Order Idempotency Engine.

Provides deterministic idempotency keys and state tracking for all trade
and order operations. Guarantees that network retries or multi-turn agent calls
never submit duplicate market or limit orders to the broker.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class IdempotencyRecord:
    key: str
    action_type: str
    payload_hash: str
    created_at: float
    status: str  # "pending", "completed", "failed"
    result: Optional[Dict[str, Any]] = None


class IdempotencyEngine:
    """Manages order-level idempotency state."""

    def __init__(self, ttl_seconds: float = 86400.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._records: Dict[str, IdempotencyRecord] = {}

    def generate_key(self, session_id: str, action_type: str, payload: Dict[str, Any]) -> str:
        """Generates a deterministic idempotency key for a given session, action, and payload."""
        payload_str = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()[:16]
        return f"idemp_{session_id}_{action_type}_{payload_hash}"

    def register_action(
        self, key: str, action_type: str, payload: Dict[str, Any]
    ) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        Registers an intended action.
        
        Returns (is_new, existing_result):
        - (True, None): Action is new and registered as pending. Proceed with execution.
        - (False, result): Action was already executed previously. Skip re-execution and return saved result.
        """
        self._cleanup_expired()
        
        if key in self._records:
            record = self._records[key]
            if record.status == "completed":
                return False, record.result
            if record.status == "pending":
                # Action is currently being executed in a concurrent process/thread
                return False, record.result or {"status": "in_progress", "key": key}

        payload_str = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()[:16]

        self._records[key] = IdempotencyRecord(
            key=key,
            action_type=action_type,
            payload_hash=payload_hash,
            created_at=time.time(),
            status="pending",
        )
        return True, None

    def mark_complete(self, key: str, result: Dict[str, Any]) -> None:
        """Marks an idempotency record as successfully completed."""
        if key in self._records:
            self._records[key].status = "completed"
            self._records[key].result = result

    def mark_failed(self, key: str) -> None:
        """Marks an idempotency record as failed so it can be safely retried."""
        if key in self._records:
            self._records.pop(key, None)

    def _cleanup_expired(self) -> None:
        """Removes expired records based on TTL."""
        now = time.time()
        expired_keys = [
            k for k, r in self._records.items() if (now - r.created_at) > self.ttl_seconds
        ]
        for k in expired_keys:
            del self._records[k]


_GLOBAL_IDEMPOTENCY_ENGINE = IdempotencyEngine()


def get_idempotency_engine() -> IdempotencyEngine:
    return _GLOBAL_IDEMPOTENCY_ENGINE
