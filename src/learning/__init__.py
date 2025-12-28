"""
Learning Module - The Simplest System That Works

Based on December 2025 research:
- Thompson Sampling beats complex RL for <100 trades
- Simple SQLite memory beats 10,000 lines of RAG code
- Query before each trade (most systems skip this)
- Feedback loop: thumbs up/down → RL reward shaping (Dec 2025)

Total: ~500 lines (vs 272,000 lines that didn't work)
"""

from src.learning.thompson_sampler import ThompsonSampler
from src.learning.trade_memory import TradeMemory
from src.learning.feedback_processor import FeedbackProcessor
from src.learning.feedback_weighted_rag import FeedbackWeightedRAG
from src.learning.rl_feedback_connector import (
    RLFeedbackConnector,
    get_rl_feedback_connector,
    shape_reward_with_feedback,
)

__all__ = [
    "ThompsonSampler",
    "TradeMemory",
    "FeedbackProcessor",
    "FeedbackWeightedRAG",
    "RLFeedbackConnector",
    "get_rl_feedback_connector",
    "shape_reward_with_feedback",
]
