"""GRPO Shadow Execution Evaluator.

Runs Group Relative Policy Optimization inference in non-blocking shadow mode
during dry-run ticks, tracking policy performance against baseline strategy rules
without risking live capital.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from src.ml.feature_extractor import FeatureExtractor

logger = logging.getLogger(__name__)


@dataclass
class ShadowEvaluation:
    timestamp: str
    symbol: str
    strategy: str
    market_features: Dict[str, Any]
    baseline_delta: float
    baseline_dte: int
    proposed_delta: float
    proposed_dte: int
    proposed_confidence: float
    delta_divergence: float
    dte_divergence: int
    status: str = "SHADOW_LOGGED"

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GRPOShadowEvaluator:
    """Evaluates GRPO trade decisions in shadow mode without executing orders."""

    def __init__(self, shadow_log_path: Optional[Path] = None):
        self.shadow_log_path = shadow_log_path or Path("data/audit/grpo_shadow_evaluations.jsonl")
        self.feature_extractor = FeatureExtractor()

    def evaluate_shadow_tick(
        self,
        symbol: str,
        strategy: str,
        snapshot: Dict[str, Any],
        baseline_delta: float = 0.15,
        baseline_dte: int = 35,
    ) -> ShadowEvaluation:
        """Run GRPO shadow evaluation for a single trading tick."""
        features = self.feature_extractor.extract_from_snapshot(snapshot)

        # Heuristic policy prediction stub (simulates GRPO Policy Network forward pass)
        # Higher VIX percentile slightly reduces short delta; higher term structure extends DTE
        delta_adj = -0.03 * (features.vix_percentile - 0.5)
        dte_adj = int(5 * (features.vix_term_structure - 1.0))

        proposed_delta = float(np.round(np.clip(baseline_delta + delta_adj, 0.05, 0.30), 2))
        proposed_dte = int(np.clip(baseline_dte + dte_adj, 14, 60))
        proposed_confidence = float(np.round(np.clip(0.60 + 0.2 * (features.iv_rank / 100.0), 0.0, 1.0), 2))

        eval_record = ShadowEvaluation(
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=symbol,
            strategy=strategy,
            market_features=features.as_dict(),
            baseline_delta=baseline_delta,
            baseline_dte=baseline_dte,
            proposed_delta=proposed_delta,
            proposed_dte=proposed_dte,
            proposed_confidence=proposed_confidence,
            delta_divergence=float(np.round(abs(proposed_delta - baseline_delta), 2)),
            dte_divergence=abs(proposed_dte - baseline_dte),
        )

        self._log_shadow_evaluation(eval_record)
        return eval_record

    def _log_shadow_evaluation(self, eval_record: ShadowEvaluation) -> None:
        """Log evaluation record to JSONL log file."""
        try:
            self.shadow_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.shadow_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(eval_record.as_dict()) + "\n")
        except Exception as e:
            logger.error("Failed to log shadow evaluation: %s", e)

    def read_shadow_evaluations(self, max_records: int = 100) -> List[Dict[str, Any]]:
        """Read historical shadow evaluation records."""
        if not self.shadow_log_path.exists():
            return []
        records = []
        try:
            with open(self.shadow_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        except Exception as e:
            logger.error("Failed reading shadow evaluation records: %s", e)
        return records[-max_records:]
