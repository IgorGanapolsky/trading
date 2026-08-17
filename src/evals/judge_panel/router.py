"""Mixture-of-Experts router: task kind → expert set."""

from __future__ import annotations

from src.evals.judge_panel.models import ExpertName, TaskKind


class ExpertRouter:
    """Route work to the minimum expert set (cost-aware MoE)."""

    _MAP: dict[TaskKind, tuple[ExpertName, ...]] = {
        TaskKind.CLAIM_AUDIT: (ExpertName.EVIDENCE, ExpertName.RISK_RULES),
        TaskKind.PR_AUDIT: (
            ExpertName.RISK_RULES,
            ExpertName.EVIDENCE,
            ExpertName.COORDINATION,
        ),
        TaskKind.COORD_AUDIT: (ExpertName.COORDINATION, ExpertName.RISK_RULES),
        # Trade entry: risk only — never spin a full council.
        TaskKind.TRADE_ENTRY: (ExpertName.RISK_RULES,),
        TaskKind.STRATEGY_RESEARCH: (
            ExpertName.RESEARCH_CRITIC,
            ExpertName.RISK_RULES,
        ),
    }

    def select(self, kind: TaskKind) -> tuple[ExpertName, ...]:
        return self._MAP[kind]
