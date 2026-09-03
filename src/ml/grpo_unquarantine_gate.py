"""GRPO RL Model Un-Quarantine & Safety Gate.

Tracks verified trade cohort outcomes and automatically un-quarantines
the GRPO Reinforcement Learning model when 30+ verified outcomes pass safety thresholds.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.ml.offline_policy_eval import OfflinePolicyEvaluator

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
STATUS_FILE = ROOT / "data" / "audit" / "grpo_quarantine_status.json"


@dataclass(frozen=True)
class GRPOQuarantineStatus:
    total_verified_outcomes: int
    required_outcomes: int
    win_rate_pct: float
    is_quarantined: bool
    status_message: str


class GRPOUnquarantineGate:
    """Manages ML model quarantine state based on verified trade cohorts."""

    def __init__(
        self,
        required_outcomes: int = 30,
        min_win_rate_pct: float = 75.0,
        *,
        status_file: Path | None = None,
        persist: bool = False,
    ):
        self.required_outcomes = required_outcomes
        self.min_win_rate_pct = min_win_rate_pct
        self.status_file = status_file or STATUS_FILE
        self.persist = persist

    def check_status(
        self, cohort_outcomes: list[dict[str, Any]] | None = None
    ) -> GRPOQuarantineStatus:
        outcomes = cohort_outcomes or []
        count = len(outcomes)

        if count == 0:
            status = GRPOQuarantineStatus(
                total_verified_outcomes=0,
                required_outcomes=self.required_outcomes,
                win_rate_pct=0.0,
                is_quarantined=True,
                status_message=f"Quarantined: 0/{self.required_outcomes} verified outcomes logged",
            )
            self._maybe_persist(status)
            return status

        wins = sum(1 for o in outcomes if o.get("profit_usd", 0.0) > 0.0 or o.get("won", False))
        win_rate = round((wins / count) * 100.0, 2)

        # Evaluate policy offline
        evaluator = OfflinePolicyEvaluator()
        ope_res = evaluator.evaluate_policy(outcomes, lambda x: 0.85)

        is_quarantined = (
            count < self.required_outcomes
            or win_rate < self.min_win_rate_pct
            or not ope_res.is_statistically_significant
        )

        if is_quarantined:
            msg = (
                f"Quarantined: {count}/{self.required_outcomes} verified outcomes "
                f"(Win Rate: {win_rate}%)"
            )
        else:
            msg = (
                f"UNQUARANTINED: {count} verified outcomes pass safety thresholds "
                f"(Win Rate: {win_rate}%)"
            )

        status = GRPOQuarantineStatus(
            total_verified_outcomes=count,
            required_outcomes=self.required_outcomes,
            win_rate_pct=win_rate,
            is_quarantined=is_quarantined,
            status_message=msg,
        )
        self._maybe_persist(status)
        return status

    def _maybe_persist(self, status: GRPOQuarantineStatus) -> None:
        if not self.persist:
            return
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        with self.status_file.open("w", encoding="utf-8") as handle:
            json.dump(asdict(status), handle, indent=2)
