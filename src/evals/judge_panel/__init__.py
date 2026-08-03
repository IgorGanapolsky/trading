"""LLM-as-Judge panel with Mixture-of-Experts routing.

Purpose
-------
Audit **agent claims, PRs, and multi-agent coordination** — not trade entries.

Hard rule: deterministic risk gates always veto qualitative scores.
Trade-entry routing is risk-only and never "LLM-approves" size/delta.

See scripts/judge_panel.py and tests/test_judge_panel.py.
"""

from __future__ import annotations

from src.evals.judge_panel.models import (
    ExpertName,
    ExpertOpinion,
    PanelVerdict,
    TaskKind,
)
from src.evals.judge_panel.panel import JudgePanel, run_panel
from src.evals.judge_panel.router import ExpertRouter

__all__ = [
    "ExpertName",
    "ExpertOpinion",
    "ExpertRouter",
    "JudgePanel",
    "PanelVerdict",
    "TaskKind",
    "run_panel",
]
