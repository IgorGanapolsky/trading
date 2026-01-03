"""
Learning Module - Trade Memory and Feedback Training.

Updated Jan 1, 2026:
- Added BinaryRewardShaper for shaped rewards
- Added FeedbackTrainer for thumbs up/down training
- Connected feedback capture to RL training pipeline
"""

from src.learning.feedback_trainer import FeedbackTrainer
from src.learning.reward_shaper import BinaryRewardShaper
from src.learning.trade_memory import TradeMemory

__all__ = [
    "TradeMemory",
    "BinaryRewardShaper",
    "FeedbackTrainer",
]
