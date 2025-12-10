"""
Profit Target Tracker
---------------------

Provides a lightweight analytics utility that inspects the latest
`data/system_state.json` snapshot and generates an actionable plan for hitting
the North Star goal of $100/day in net income.

Usage:
    python scripts/generate_profit_target_report.py --target 100
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ProfitPlan:
    """Container describing the path to the daily profit target."""

    current_daily_profit: float
    projected_daily_profit: float
    target_daily_profit: float
    target_gap: float
    current_daily_budget: float
    recommended_daily_budget: float | None
    scaling_factor: float | None
    avg_return_pct: float
    win_rate: float | None
    recommended_allocations: dict[str, float]
    actions: list[str]


class ProfitTargetTracker:
    """Analyze the latest system state and chart the path to the daily goal."""

    def __init__(
        self,
        state_path: str | Path = "data/system_state.json",
        target_daily_profit: float = 100.0,
        state_override: dict[str, Any] | None = None,
    ) -> None:
        self.state_path = Path(state_path)
        self.target_daily_profit = target_daily_profit
        self._state = state_override or self._load_state()

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            raise FileNotFoundError(
                f"System state file not found at {self.state_path}. "
                "Run the daily trading workflow before generating the report."
            )
        return json.loads(self.state_path.read_text())

    # ---- Helper calculations -------------------------------------------------

    def _days_elapsed(self) -> int:
        return max(1, int(self._state.get("challenge", {}).get("current_day", 1)))

    def _total_pl(self) -> float:
        return float(self._state.get("account", {}).get("total_pl", 0.0))

    def _avg_return_pct(self) -> float:
        return float(self._state.get("performance", {}).get("avg_return", 0.0))

    def _win_rate(self) -> float | None:
        win_rate = self._state.get("performance", {}).get("win_rate")
        return float(win_rate) if win_rate is not None else None

    def _current_daily_budget(self) -> float:
        strategies = self._state.get("strategies", {})
        total = 0.0
        for strat in strategies.values():
            status = strat.get("status", "active")
            if status in {"tracking", "paused"}:
                continue
            total += float(strat.get("daily_amount", 0.0))
        return total

    def _active_strategy_weights(self) -> dict[str, float]:
        strategies = self._state.get("strategies", {})
        active = {
            name: strat
            for name, strat in strategies.items()
            if strat.get("status", "active") not in {"tracking", "paused"}
        }

        if not active:
            return {}

        total_allocation = sum(strat.get("allocation", 0.0) or 0.0 for strat in active.values())
        if total_allocation <= 0:
            total_allocation = sum(
                float(strat.get("daily_amount", 0.0)) for strat in active.values()
            )

        if total_allocation <= 0:
            return {}

        weights: dict[str, float] = {}
        for name, strat in active.items():
            weight = strat.get("allocation")
            if weight is None or weight == 0:
                daily_amount = float(strat.get("daily_amount", 0.0))
                weight = daily_amount / total_allocation if total_allocation else 0.0
            weights[name] = float(weight)
        weight_sum = sum(weights.values())
        if 0 < weight_sum != 1:
            weights = {k: v / weight_sum for k, v in weights.items()}
        return weights

    # ---- Public API ----------------------------------------------------------

    def current_daily_profit(self) -> float:
        return self._total_pl() / self._days_elapsed()

    def projected_daily_profit(self) -> float:
        avg_return_ratio = self._avg_return_pct() / 100.0
        return self._current_daily_budget() * avg_return_ratio

    def recommended_daily_budget(self) -> float | None:
        avg_return_pct = self._avg_return_pct()
        if avg_return_pct <= 0:
            return None
        return self.target_daily_profit / (avg_return_pct / 100.0)

    def generate_plan(self) -> ProfitPlan:
        current_daily_profit = self.current_daily_profit()
        projected_daily_profit = self.projected_daily_profit()
        current_budget = self._current_daily_budget()
        avg_return_pct = self._avg_return_pct()
        target_gap = self.target_daily_profit - projected_daily_profit

        recommended_budget = self.recommended_daily_budget()
        scaling_factor = (
            recommended_budget / current_budget
            if recommended_budget and current_budget > 0
            else None
        )

        allocations: dict[str, float] = {}
        if recommended_budget and recommended_budget > 0:
            for name, weight in self._active_strategy_weights().items():
                allocations[name] = round(recommended_budget * weight, 2)

        actions = self._build_actions(
            recommended_budget=recommended_budget,
            scaling_factor=scaling_factor,
            avg_return_pct=avg_return_pct,
        )

        return ProfitPlan(
            current_daily_profit=current_daily_profit,
            projected_daily_profit=projected_daily_profit,
            target_daily_profit=self.target_daily_profit,
            target_gap=target_gap,
            current_daily_budget=current_budget,
            recommended_daily_budget=recommended_budget,
            scaling_factor=scaling_factor,
            avg_return_pct=avg_return_pct,
            win_rate=self._win_rate(),
            recommended_allocations=allocations,
            actions=actions,
        )

    def _build_actions(
        self,
        recommended_budget: float | None,
        scaling_factor: float | None,
        avg_return_pct: float,
    ) -> list[str]:
        actions: list[str] = []
        if avg_return_pct <= 0:
            actions.append(
                "Improve strategy edge before scaling capital: avg return is ≤ 0%. "
                "Run signal-quality diagnostics and tighten risk controls."
            )
        if recommended_budget is None:
            actions.append(
                "Collect five more profitable sessions before attempting capital scaling."
            )
        else:
            actions.append(
                f"Increase blended daily budget to ${recommended_budget:,.2f} "
                f"(current projection ${self.projected_daily_profit():.2f}/day)."
            )
            if scaling_factor and scaling_factor > 1:
                actions.append(
                    f"Scale each active strategy by {scaling_factor:.1f}x while "
                    "respecting its allocation weight."
                )

        if not actions:
            actions.append("Maintain current allocation; target is on track.")
        return actions

    def write_report(self, output_path: str | Path) -> None:
        plan = self.generate_plan()
        payload = {
            "current_daily_profit": plan.current_daily_profit,
            "projected_daily_profit": plan.projected_daily_profit,
            "target_daily_profit": plan.target_daily_profit,
            "target_gap": plan.target_gap,
            "current_daily_budget": plan.current_daily_budget,
            "recommended_daily_budget": plan.recommended_daily_budget,
            "scaling_factor": plan.scaling_factor,
            "avg_return_pct": plan.avg_return_pct,
            "win_rate": plan.win_rate,
            "recommended_allocations": plan.recommended_allocations,
            "actions": plan.actions,
        }
        Path(output_path).write_text(json.dumps(payload, indent=2))


__all__ = ["ProfitPlan", "ProfitTargetTracker"]
