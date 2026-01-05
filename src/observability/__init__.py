"""Observability module for Deep Agent monitoring using LangSmith."""

from src.observability.langsmith_tracer import (
    LangSmithTracer,
    get_tracer,
    traceable_decision,
    traceable_signal,
    traceable_trade,
)

# Unified trade sync (Jan 2026) - syncs to LangSmith + ChromaDB RAG
from src.observability.trade_sync import (
    TradeSync,
    get_trade_sync,
    sync_trade,
)

__all__ = [
    "LangSmithTracer",
    "get_tracer",
    "traceable_decision",
    "traceable_signal",
    "traceable_trade",
    # Trade sync
    "TradeSync",
    "get_trade_sync",
    "sync_trade",
]
