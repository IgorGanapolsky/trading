"""
Learning Module - The Simplest System That Works

Based on December 2025 research:
- Thompson Sampling beats complex RL for <100 trades
- Simple SQLite memory beats 10,000 lines of RAG code
- Query before each trade (most systems skip this)

Total: ~250 lines (vs 272,000 lines that didn't work)
"""

from src.learning.thompson_sampler import ThompsonSampler
from src.learning.trade_memory import TradeMemory

__all__ = ["ThompsonSampler", "TradeMemory"]
