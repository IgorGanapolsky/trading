"""
Learning Module - Trade Memory and Feedback Training.

Updated Jan 5, 2026:
- Added RLHFStorage (LanceDB) for RLHF trajectory storage
- Added BinaryRewardShaper for shaped rewards
- Added FeedbackTrainer for thumbs up/down training
- Connected feedback capture to RL training pipeline
"""

from src.learning.feedback_trainer import FeedbackTrainer
from src.learning.reward_shaper import BinaryRewardShaper
from src.learning.rlhf_storage import RLHFStorage, get_rlhf_storage, store_trade_trajectory
from src.learning.trade_memory import TradeMemory

__all__ = [
    "TradeMemory",
    "BinaryRewardShaper",
    "FeedbackTrainer",
    "RLHFStorage",
    "get_rlhf_storage",
    "store_trade_trajectory",
]
