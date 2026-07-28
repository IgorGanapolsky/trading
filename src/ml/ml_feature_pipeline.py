"""ML Feature & Evaluation Pipeline.

Unified orchestration pipeline connecting FeatureExtractor, Thompson Sampler,
and GRPOShadowEvaluator for operational trade signal generation and evaluation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.ml.feature_extractor import FeatureExtractor, MarketFeatures
from src.ml.grpo_shadow_evaluator import GRPOShadowEvaluator, ShadowEvaluation

logger = logging.getLogger(__name__)


class MLFeaturePipeline:
    """Orchestrates market feature extraction, trade confidence, and shadow GRPO inference."""

    def __init__(self, shadow_evaluator: Optional[GRPOShadowEvaluator] = None):
        self.feature_extractor = FeatureExtractor()
        self.shadow_evaluator = shadow_evaluator or GRPOShadowEvaluator()

    def process_tick(
        self,
        symbol: str,
        strategy: str,
        market_snapshot: Dict[str, Any],
        baseline_delta: float = 0.15,
        baseline_dte: int = 35,
    ) -> Dict[str, Any]:
        """Process a market tick: extract features, run shadow GRPO eval, and return pipeline metadata."""
        features: MarketFeatures = self.feature_extractor.extract_from_snapshot(market_snapshot)
        shadow_eval: ShadowEvaluation = self.shadow_evaluator.evaluate_shadow_tick(
            symbol=symbol,
            strategy=strategy,
            snapshot=market_snapshot,
            baseline_delta=baseline_delta,
            baseline_dte=baseline_dte,
        )

        return {
            "symbol": symbol,
            "strategy": strategy,
            "features": features.as_dict(),
            "feature_vector_shape": list(features.to_vector().shape),
            "shadow_evaluation": shadow_eval.as_dict(),
            "pipeline_status": "OK",
        }
