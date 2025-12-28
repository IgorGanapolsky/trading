"""
Learning Module - Trade Memory System

Simplified Dec 28, 2025:
- Removed dead RLHF/feedback infrastructure (never integrated)
- Kept only TradeMemory which is actively used

The feedback system was aspirational code that was never connected
to the trading pipeline. Deleted to reduce complexity.
"""

from src.learning.trade_memory import TradeMemory

__all__ = [
    "TradeMemory",
]
