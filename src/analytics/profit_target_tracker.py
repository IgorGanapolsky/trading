"""Profit target tracker for daily income and budget scaling recommendations."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from src.core.trading_constants import NORTH_STAR_DAILY_AFTER_TAX
except Exception:
    NORTH_STAR_DAILY_AFTER_TAX = 200.0


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


@dataclass
class ProfitTargetPlan:
    """Computed progress and budget recommendations toward daily profit goal."""

    current_daily_profit: float
    projected_daily_profit: float
    target_daily_profit: float
    target_gap: float
    current_daily_budget: float
    recommended_daily_budget: float | None
    scaling_factor: float | None
    avg_return_pct: float
    win_rate: float
    actions: list[str] = field(default_factory=list)
    recommended_allocations: dict[str, float] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProfitTargetTracker:
    """Compute a practical scaling plan from current paper-trading evidence."""

    def __init__(
        self,
        target_daily_profit: float | None = None,
        *,
        state_path: Path | None = None,
    ) -> None:
        self.target_daily_profit = float(
            target_daily_profit if target_daily_profit is not None else NORTH_STAR_DAILY_AFTER_TAX
        )
        self.state_path = state_path or Path(
            os.getenv("SYSTEM_STATE_PATH", "data/system_state.json")
        )

    def _load_state(self) -> dict[str, Any]:
        return _load_json(self.state_path)

    def _resolve_current_budget(self, state: dict[str, Any]) -> float:
        env_budget = os.getenv("DAILY_INVESTMENT")
        if env_budget is not None:
            parsed = _as_float(env_budget, 0.0)
            if parsed > 0:
                return parsed

        risk = state.get("risk", {}) if isinstance(state, dict) else {}
        risk_budget = _as_float(risk.get("daily_budget"), 0.0)
        if risk_budget > 0:
            return risk_budget

        # Derive from account risk envelope when explicit daily budget is unavailable.
        paper = state.get("paper_account", {}) if isinstance(state, dict) else {}
        paper_equity = _as_float(paper.get("equity"), 0.0)
        if paper_equity > 0:
            return round(paper_equity * 0.05, 2)

        # Conservative fallback used when we cannot infer equity.
        return 25.0

    def generate_plan(self) -> ProfitTargetPlan:
        state = self._load_state()
        paper = state.get("paper_account", {}) if isinstance(state, dict) else {}
        paper_trading = state.get("paper_trading", {}) if isinstance(state, dict) else {}

        current_daily_profit = _as_float(paper.get("daily_change"), 0.0)
        total_pl = _as_float(paper.get("total_pl"), 0.0)
        win_rate = _as_float(paper.get("win_rate"), 0.0)
        paper_day = max(1, _as_int(paper_trading.get("current_day"), 0))
        average_daily_profit = total_pl / paper_day

        # Blend today's result with long-horizon average to avoid overreacting.
        projected_daily_profit = (0.6 * average_daily_profit) + (0.4 * current_daily_profit)

        current_daily_budget = self._resolve_current_budget(state)
        if current_daily_budget > 0:
            avg_return_pct = (average_daily_profit / current_daily_budget) * 100.0
        else:
            avg_return_pct = 0.0

        target_gap = self.target_daily_profit - projected_daily_profit

        recommended_daily_budget: float | None = None
        scaling_factor: float | None = None
        if avg_return_pct > 0:
            recommended_daily_budget = self.target_daily_profit / (avg_return_pct / 100.0)
            scaling_factor = (
                recommended_daily_budget / current_daily_budget
                if current_daily_budget > 0
                else None
            )

        actions: list[str] = []
        if win_rate < 80.0:
            actions.append(
                f"Keep risk constrained until win rate improves (current {win_rate:.1f}% vs 80% target)."
            )

        if avg_return_pct <= 0:
            actions.append("Do not scale budget yet; improve expectancy and daily edge first.")
        elif target_gap > 0:
            actions.append(
                f"Projected daily profit is ${target_gap:.2f} below target; scale budget gradually."
            )
            if recommended_daily_budget is not None:
                actions.append(
                    f"Target daily budget: ${recommended_daily_budget:,.2f} "
                    f"({scaling_factor:.2f}x current)."
                )
        else:
            actions.append(
                "Projected daily profit meets target; hold sizing discipline and compound."
            )

        recommended_allocations: dict[str, float] = {}
        if recommended_daily_budget is not None and recommended_daily_budget > 0:
            recommended_allocations = {
                "options_income": round(recommended_daily_budget * 0.70, 2),
                "equity_momentum": round(recommended_daily_budget * 0.20, 2),
                "alternatives": round(recommended_daily_budget * 0.10, 2),
            }

        return ProfitTargetPlan(
            current_daily_profit=round(current_daily_profit, 2),
            projected_daily_profit=round(projected_daily_profit, 2),
            target_daily_profit=round(self.target_daily_profit, 2),
            target_gap=round(target_gap, 2),
            current_daily_budget=round(current_daily_budget, 2),
            recommended_daily_budget=round(recommended_daily_budget, 2)
            if recommended_daily_budget is not None
            else None,
            scaling_factor=round(scaling_factor, 2) if scaling_factor is not None else None,
            avg_return_pct=round(avg_return_pct, 2),
            win_rate=round(win_rate, 2),
            actions=actions,
            recommended_allocations=recommended_allocations,
        )
