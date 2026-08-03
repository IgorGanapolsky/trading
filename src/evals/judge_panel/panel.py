"""Judge panel: aggregate expert opinions with hard-veto priority."""

from __future__ import annotations

from typing import Iterable, Optional

from src.evals.judge_panel.experts import (
    NarrativeJudgeFn,
    get_default_experts,
)
from src.evals.judge_panel.models import (
    ExpertName,
    ExpertOpinion,
    PanelInput,
    PanelVerdict,
    TaskKind,
)
from src.evals.judge_panel.router import ExpertRouter


def _opinion_flag(opinion: ExpertOpinion) -> str:
    if opinion.veto:
        return "VETO"
    if opinion.passed:
        return "PASS"
    return "FAIL"


def _verdict_head(passed: bool, vetoed: bool) -> str:
    if passed:
        return "PASS"
    if vetoed:
        return "VETO"
    return "FAIL"


def _default_summary(opinions: list[ExpertOpinion], vetoed: bool, passed: bool) -> str:
    parts = [f"{o.expert.value}={_opinion_flag(o)}(score={o.score:.2f})" for o in opinions]
    head = _verdict_head(passed, vetoed)
    return f"{head}: " + "; ".join(parts)


def _collect_opinions(
    selected: tuple[ExpertName, ...],
    experts: dict[ExpertName, object],
    payload: PanelInput,
) -> list[ExpertOpinion]:
    opinions: list[ExpertOpinion] = []
    for name in selected:
        expert = experts.get(name)
        if expert is None:
            opinions.append(
                ExpertOpinion(
                    expert=name,
                    score=0.0,
                    passed=False,
                    findings=[f"missing expert: {name.value}"],
                    veto=True,
                )
            )
            continue
        opinions.append(expert.evaluate(payload))  # type: ignore[attr-defined]
    return opinions


def _aggregate(opinions: list[ExpertOpinion]) -> tuple[bool, bool, float, list[str]]:
    veto_reasons: list[str] = []
    for o in opinions:
        if o.veto:
            veto_reasons.extend(o.findings)
    vetoed = bool(veto_reasons)
    scores = [o.score for o in opinions] or [0.0]
    score = sum(scores) / len(scores)
    all_passed = all(o.passed for o in opinions) and not vetoed
    passed = False if vetoed else all_passed
    return passed, vetoed, score, veto_reasons


def _apply_narrative(
    summary: str,
    passed: bool,
    narrative_fn: NarrativeJudgeFn | None,
    opinions: list[ExpertOpinion],
) -> str:
    if narrative_fn is None:
        return summary
    try:
        polished = narrative_fn(summary, opinions)
    except Exception as exc:  # pragma: no cover - defensive
        return f"{summary} | narrative_error={exc}"
    # Narrative cannot claim PASS if panel failed.
    if not passed and re_claims_pass(polished):
        return summary + " | narrative_stripped_false_pass"
    return polished


class JudgePanel:
    """
    LLM-as-Judge style panel backed by MoE specialists.

    The optional narrative_fn may polish the summary string only.
    It cannot flip a veto or invent a pass when experts failed.
    """

    def __init__(
        self,
        router: Optional[ExpertRouter] = None,
        experts: Optional[dict[ExpertName, object]] = None,
        narrative_fn: Optional[NarrativeJudgeFn] = None,
    ) -> None:
        self.router = router or ExpertRouter()
        # Allow empty dict to mean "no experts" (must not fall back via `or`).
        self.experts = get_default_experts() if experts is None else experts
        self.narrative_fn = narrative_fn

    def run(self, payload: PanelInput) -> PanelVerdict:
        selected = self.router.select(payload.kind)
        opinions = _collect_opinions(selected, self.experts, payload)
        passed, vetoed, score, veto_reasons = _aggregate(opinions)
        summary = _default_summary(opinions, vetoed, passed)
        summary = _apply_narrative(summary, passed, self.narrative_fn, opinions)

        return PanelVerdict(
            kind=payload.kind,
            passed=passed,
            score=round(score, 4),
            vetoed=vetoed,
            veto_reasons=veto_reasons,
            experts_used=[n.value for n in selected],
            opinions=opinions,
            judge_summary=summary,
        )


def re_claims_pass(text: str) -> bool:
    """True if narrative text falsely asserts a panel pass."""
    if not text:
        return False
    upper = text.strip().upper()
    return upper.startswith("PASS") or "PANEL PASS" in upper


def run_panel(
    kind: TaskKind | str,
    *,
    text: str = "",
    diff: str = "",
    claim: str = "",
    agent: str = "grok",
    other_agent_claims: str = "",
    claimed_files: Optional[Iterable[str]] = None,
    narrative_fn: Optional[NarrativeJudgeFn] = None,
) -> PanelVerdict:
    """Convenience entrypoint for CLI and tests."""
    if isinstance(kind, str):
        kind = TaskKind(kind)
    payload = PanelInput(
        kind=kind,
        text=text,
        diff=diff,
        claim=claim,
        agent=agent,
        other_agent_claims=other_agent_claims,
        claimed_files=list(claimed_files or []),
    )
    return JudgePanel(narrative_fn=narrative_fn).run(payload)
