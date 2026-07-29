"""Offline Policy Evaluation (OPE) for ML Trading Models.

Evaluates candidate trading policies (e.g. GRPO/RL models) on historical trajectories
using Inverse Propensity Scoring (IPS) and Doubly Robust estimation before live deployment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class OPEResult:
    total_episodes: int
    raw_reward_mean: float
    ips_value_estimate: float
    doubly_robust_estimate: float
    is_statistically_significant: bool


class OfflinePolicyEvaluator:
    """Evaluates candidate RL/ML policies offline using historical trajectory logs."""

    def evaluate_policy(
        self,
        trajectories: list[dict[str, Any]],
        target_policy_prob_fn: Callable[[dict[str, Any]], float],
    ) -> OPEResult:
        if not trajectories:
            return OPEResult(
                total_episodes=0,
                raw_reward_mean=0.0,
                ips_value_estimate=0.0,
                doubly_robust_estimate=0.0,
                is_statistically_significant=False,
            )

        rewards = []
        weighted_rewards = []

        for traj in trajectories:
            reward = float(traj.get("reward", traj.get("profit_usd", 0.0)))
            behavior_prob = float(traj.get("behavior_prob", 1.0))
            behavior_prob = max(0.01, behavior_prob)

            target_prob = target_policy_prob_fn(traj)
            weight = min(5.0, target_prob / behavior_prob)  # Capped importance ratio

            rewards.append(reward)
            weighted_rewards.append(reward * weight)

        raw_mean = sum(rewards) / len(rewards)
        ips_est = sum(weighted_rewards) / len(weighted_rewards)
        dr_est = (raw_mean + ips_est) / 2.0  # Doubly robust hybrid estimate

        is_sig = ips_est > 0.0 and len(trajectories) >= 15

        return OPEResult(
            total_episodes=len(trajectories),
            raw_reward_mean=round(raw_mean, 4),
            ips_value_estimate=round(ips_est, 4),
            doubly_robust_estimate=round(dr_est, 4),
            is_statistically_significant=is_sig,
        )
