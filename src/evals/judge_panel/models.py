"""Shared types for the judge panel / MoE router."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskKind(StrEnum):
    """What the panel is judging."""

    CLAIM_AUDIT = "claim_audit"
    PR_AUDIT = "pr_audit"
    COORD_AUDIT = "coord_audit"
    # Explicit: never an LLM trade council — risk expert only + structural refuse.
    TRADE_ENTRY = "trade_entry"
    STRATEGY_RESEARCH = "strategy_research"


class ExpertName(StrEnum):
    RISK_RULES = "risk_rules"
    EVIDENCE = "evidence"
    COORDINATION = "coordination"
    RESEARCH_CRITIC = "research_critic"


@dataclass(frozen=True)
class ExpertOpinion:
    expert: ExpertName
    score: float  # 0.0–1.0 (higher = healthier)
    passed: bool
    findings: list[str] = field(default_factory=list)
    evidence_cites: list[str] = field(default_factory=list)
    veto: bool = False  # hard fail; judge cannot override

    def to_dict(self) -> dict[str, Any]:
        return {
            "expert": self.expert.value,
            "score": self.score,
            "passed": self.passed,
            "findings": list(self.findings),
            "evidence_cites": list(self.evidence_cites),
            "veto": self.veto,
        }


@dataclass
class PanelInput:
    """Bundle of material for experts to inspect."""

    kind: TaskKind
    text: str = ""
    diff: str = ""
    claim: str = ""
    agent: str = "unknown"
    other_agent_claims: str = ""
    claimed_files: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PanelVerdict:
    kind: TaskKind
    passed: bool
    score: float
    vetoed: bool
    veto_reasons: list[str]
    experts_used: list[str]
    opinions: list[ExpertOpinion]
    judge_summary: str
    hard_rules_note: str = (
        "Deterministic risk gates always veto. "
        "This panel does not approve trade entries, size, or expectancy claims without ledger math."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "passed": self.passed,
            "score": self.score,
            "vetoed": self.vetoed,
            "veto_reasons": list(self.veto_reasons),
            "experts_used": list(self.experts_used),
            "opinions": [o.to_dict() for o in self.opinions],
            "judge_summary": self.judge_summary,
            "hard_rules_note": self.hard_rules_note,
        }
