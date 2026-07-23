"""ML Module - Gemini/GenAI Integration and GRPO Trade Learning.

Provides:
- GENAI_AVAILABLE flag for health checks
- GRPOTradeLearner for verifiable reward-based policy learning
- TradeConfidenceModel for Thompson Sampling-based confidence
- MarketRegimeClassifier for unsupervised regime detection
"""

from importlib.util import find_spec

try:
    # Availability checks must not import the deprecated SDK, emit warnings,
    # initialize clients, or create any other package side effects.
    GENAI_AVAILABLE = find_spec("google.generativeai") is not None
except (ImportError, ModuleNotFoundError, ValueError):
    GENAI_AVAILABLE = False

# GRPO Trade Learning
from src.ml.grpo_trade_learner import (
    TORCH_AVAILABLE,
    GRPOTradeLearner,
    TradeFeatures,
    TradeParams,
    get_optimal_trade_params,
    train_grpo_model,
)

# Market Regime Classification
from src.ml.market_regime import (
    MarketRegime,
    MarketRegimeClassifier,
    get_regime_signal,
)
from src.ml.policy_registry import PolicyRegistry
from src.ml.policy_scorer import PolicyScorer

# Trade Confidence (Thompson Sampling)
from src.ml.trade_confidence import (
    TradeConfidenceModel,
    get_trade_confidence_model,
    sample_trade_confidence,
)

__all__ = [
    # Availability flags
    "GENAI_AVAILABLE",
    "TORCH_AVAILABLE",
    # GRPO
    "GRPOTradeLearner",
    "TradeFeatures",
    "TradeParams",
    "get_optimal_trade_params",
    "train_grpo_model",
    # Trade Confidence
    "TradeConfidenceModel",
    "get_trade_confidence_model",
    "sample_trade_confidence",
    # Policy gating
    "PolicyRegistry",
    "PolicyScorer",
    # Market Regime
    "MarketRegimeClassifier",
    "MarketRegime",
    "get_regime_signal",
]
