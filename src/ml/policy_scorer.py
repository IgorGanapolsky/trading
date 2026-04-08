"""Policy eligibility scoring built from registry status + model metrics."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional

from src.ml.policy_registry import PolicyRegistry


class PolicyScorer:
    """Deterministic scorer for deciding if a policy can be used in production."""

    def __init__(self, registry: PolicyRegistry, *, min_expected_return: float = 0.0) -> None:
        self.registry = registry
        self.min_expected_return = float(min_expected_return)

    def score(
        self,
        policy_name: str,
        *,
        model_metrics: Optional[Mapping[str, Any]] = None,
        as_of: Optional[datetime] = None,
    ) -> dict[str, Any]:
        metrics = dict(model_metrics or {})
        registry_status = self.registry.status(policy_name, as_of=as_of)
        expected_return_per_trade = float(
            metrics.get("expected_return_per_trade", metrics.get("expectancy", 0.0))
        )

        block_reasons = []

        if not registry_status["exists"]:
            block_reasons.append("missing_policy")
        if registry_status["exists"] and not registry_status["is_fresh"]:
            block_reasons.append("stale_registry")
        if registry_status["exists"] and not registry_status["sufficient_samples"]:
            block_reasons.append("insufficient_samples")
        if expected_return_per_trade <= self.min_expected_return:
            block_reasons.append("negative_expectancy")

        eligible = len(block_reasons) == 0
        if eligible:
            decision_summary = (
                f"ELIGIBLE: {policy_name} v{registry_status['version']} passes "
                "freshness, sample size, and expectancy checks."
            )
        else:
            joined_reasons = ",".join(block_reasons)
            decision_summary = f"INELIGIBLE: {joined_reasons}"

        return {
            "policy_name": policy_name,
            "eligible": eligible,
            "block_reasons": block_reasons,
            "decision_summary": decision_summary,
            "freshness_passed": registry_status["exists"] and registry_status["is_fresh"],
            "sample_size_passed": registry_status["exists"]
            and registry_status["sufficient_samples"],
            "expectancy_passed": expected_return_per_trade > self.min_expected_return,
            "expected_return_per_trade": expected_return_per_trade,
            "policy_status": registry_status,
        }
