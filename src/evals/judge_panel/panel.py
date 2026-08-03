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


def _default_summary(opinions: list[ExpertOpinion], vetoed: bool, passed: bool) -> str:
    parts = []
    for o in opinions:
        flag = "VETO" if o.veto else ("PASS" if o.passed else "FAIL")
        parts.append(f"{o.expert.value}={flag}(score={o.score:.2f})")
    head = "PASS" if passed else ("VETO" if vetoed else "FAIL")
    return f"{head}: " + "; ".join(parts)


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
        self.experts = experts or get_default_experts()
        self.narrative_fn = narrative_fn

    def run(self, payload: PanelInput) -> PanelVerdict:
        selected = self.router.select(payload.kind)
        opinions: list[ExpertOpinion] = []
        for name in selected:
            expert = self.experts.get(name)
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

        veto_reasons = []
        for o in opinions:
            if o.veto:
                veto_reasons.extend(o.findings)

        vetoed = bool(veto_reasons)
        all_passed = all(o.passed for o in opinions) and not vetoed
        # Majority of non-veto opinions if no hard veto — still require zero fails.
        scores = [o.score for o in opinions] or [0.0]
        score = sum(scores) / len(scores)

        if vetoed:
            passed = False
        else:
            passed = all_passed

        summary = _default_summary(opinions, vetoed, passed)
        if self.narrative_fn is not None:
            try:
                polished = self.narrative_fn(summary, opinions)
                # Narrative cannot claim PASS if panel failed.
                if not passed and re_claims_pass(polished):
                    summary = summary + " | narrative_stripped_false_pass"
                else:
                    summary = polished
            except Exception as exc:  # pragma: no cover - defensive
                summary = f"{summary} | narrative_error={exc}"

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
