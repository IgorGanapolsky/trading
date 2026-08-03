"""Small-batch helpers for LLM/embedding cost control.

Production rule: never batch money-path order decisions. Use batching for
offline embedding rebuilds, lesson reindex, and bulk classification only.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


def chunked(items: Sequence[T], size: int) -> Iterator[list[T]]:
    """Yield fixed-size chunks (last chunk may be smaller)."""
    n = max(1, int(size))
    for i in range(0, len(items), n):
        yield list(items[i : i + n])


def map_in_batches(
    items: Sequence[T],
    fn: Callable[[list[T]], list[R]],
    *,
    batch_size: int = 32,
) -> list[R]:
    """Apply fn to successive batches and flatten results."""
    out: list[R] = []
    for batch in chunked(items, batch_size):
        part = fn(batch)
        if part:
            out.extend(part)
    return out


def estimate_batch_savings(
    n_items: int,
    *,
    per_call_overhead_tokens: int = 40,
    batch_size: int = 32,
) -> dict[str, float]:
    """Rough token-overhead savings from batching vs one-call-per-item."""
    n = max(0, int(n_items))
    bs = max(1, int(batch_size))
    naive = n * per_call_overhead_tokens
    batched = ((n + bs - 1) // bs) * per_call_overhead_tokens if n else 0
    saved = max(0, naive - batched)
    return {
        "items": float(n),
        "batch_size": float(bs),
        "naive_overhead_tokens": float(naive),
        "batched_overhead_tokens": float(batched),
        "saved_overhead_tokens": float(saved),
        "savings_ratio": (saved / naive) if naive else 0.0,
    }
