"""Unit tests for IdempotencyEngine."""

from __future__ import annotations

from src.execution.idempotency_engine import IdempotencyEngine, get_idempotency_engine


def test_idempotency_key_generation() -> None:
    engine = IdempotencyEngine()
    payload = {"symbol": "SPY", "qty": 10, "side": "buy"}
    key1 = engine.generate_key("sess_001", "order_submit", payload)
    key2 = engine.generate_key("sess_001", "order_submit", payload)
    assert key1 == key2
    assert key1.startswith("idemp_sess_001_order_submit_")


def test_idempotency_prevents_duplicate_execution() -> None:
    engine = IdempotencyEngine()
    payload = {"symbol": "SPY", "qty": 10, "side": "buy"}
    key = engine.generate_key("sess_002", "order_submit", payload)

    # First call: registered as new
    is_new, result = engine.register_action(key, "order_submit", payload)
    assert is_new is True
    assert result is None

    # Mark complete
    order_result = {"order_id": "ord_12345", "status": "submitted"}
    engine.mark_complete(key, order_result)

    # Second call: detected as duplicate, returns saved result
    is_new2, result2 = engine.register_action(key, "order_submit", payload)
    assert is_new2 is False
    assert result2 == order_result


def test_idempotency_retry_on_failure() -> None:
    engine = IdempotencyEngine()
    payload = {"symbol": "AAPL", "qty": 5, "side": "buy"}
    key = engine.generate_key("sess_003", "order_submit", payload)

    is_new, _ = engine.register_action(key, "order_submit", payload)
    assert is_new is True

    # Mark failed
    engine.mark_failed(key)

    # Retry: allowed as new
    is_new2, _ = engine.register_action(key, "order_submit", payload)
    assert is_new2 is True


def test_singleton_accessor() -> None:
    e1 = get_idempotency_engine()
    e2 = get_idempotency_engine()
    assert e1 is e2
