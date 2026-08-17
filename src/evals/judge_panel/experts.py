"""Mixture-of-Experts specialists (deterministic + optional LLM narrative).

Experts are pure functions of PanelInput. They never call brokers or submit orders.
"""

from __future__ import annotations

import re
from typing import Callable, Protocol

from src.evals.judge_panel.models import (
    ExpertName,
    ExpertOpinion,
    PanelInput,
    TaskKind,
)

# --- patterns ----------------------------------------------------------------

# Completion / edge claims that require evidence tokens nearby.
_CLAIM_MARKERS = re.compile(
    r"\b("
    r"ci\s+green|all\s+green|shipped|verified|done\s+merging|"
    r"expectancy\s*>\s*0|profit\s*factor\s*>\s*1|edge\s+proven|"
    r"profitable|live\s+ready|ready\s+for\s+live"
    r")\b",
    re.IGNORECASE,
)

# Tokens that count as evidence (SHA, run id, ledger cite, file path cite).
_EVIDENCE_TOKENS = re.compile(
    r"("
    r"\b[0-9a-f]{7,40}\b|"  # git sha
    r"\brun[\s_#-]*\d{5,}\b|"  # gh run
    r"\b#\d{3,}\b|"  # PR number
    r"system_state\.json|trades\.json|put_credit_entries\.json|"
    r"expectancy\s*[:=]\s*-?\$?\d|equity\s*[:=]\s*\$?\d|"
    r"n\s*=\s*\d+|sample\s*=\s*\d+"
    r")",
    re.IGNORECASE,
)

# Risk / policy violations in prose or diffs.
_RISK_VIOLATIONS: list[tuple[str, re.Pattern[str]]] = [
    (
        "IC_NEW_ENTRY",
        re.compile(
            r"("
            r"open\s+new\s+iron\s*condor|"
            r"resume\s+iron\s*condor|"
            r"ic_simple\.py\s+--mode\s+(scan|execute|autonomous)|"
            r"re-?enable\s+iron\s*condor|"
            r"new\s+ic\s+entr"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "LIVE_CAPITAL",
        re.compile(
            r"("
            r"deploy\s+live\s+capital|"
            r"live\s+account\s+entr|"
            r"remove\s+live_blocked|"
            r"live_blocked\s*=\s*false"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "HALT_TAMPER",
        re.compile(
            r"("
            r"rm\s+.*TRADING_HALTED|"
            r"delete\s+.*TRADING_HALTED|"
            r"clear\s+the\s+halt|"
            r"remove\s+data/TRADING_HALTED"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "CREDENTIAL_HARDCODE",
        re.compile(
            r"("
            r"(?:APCA_API_KEY_ID|ALPACA(?:_PAPER_TRADING)?_API_KEY)"
            r"\s*=\s*['\"](?!\$\{)[^'\"]+['\"]|"
            r"(?:APCA_API_SECRET_KEY|ALPACA(?:_PAPER_TRADING)?_SECRET_KEY)"
            r"\s*=\s*['\"](?!\$\{)[^'\"]+['\"]|"
            r"sk_live_[A-Za-z0-9]{10,}|"
            r"ghp_[A-Za-z0-9]{20,}"
            r")",
        ),
    ),
    (
        "LLM_TRADE_COUNCIL",
        re.compile(
            r"("
            r"llm\s+council\s+approves?\s+(the\s+)?trade|"
            r"judge\s+panel\s+says?\s+buy|"
            r"moe\s+entry\s+signal|"
            r"restore\s+trade_opinion\s+council"
            r")",
            re.IGNORECASE,
        ),
    ),
]

_OTHER_AGENT = re.compile(
    r"\b(codex|claude-code|grok|hermes|antigravity|cursor|gemini)\b",
    re.IGNORECASE,
)


class Expert(Protocol):
    name: ExpertName

    def evaluate(self, payload: PanelInput) -> ExpertOpinion: ...


def _primary_corpus(payload: PanelInput) -> str:
    """Return only the material owned by the claim or change under review."""
    parts = [payload.text, payload.diff, payload.claim]
    return "\n".join(p for p in parts if p)


class RiskRulesExpert:
    """Policy / kill-switch / credential / IC-kill specialist."""

    name = ExpertName.RISK_RULES

    def evaluate(self, payload: PanelInput) -> ExpertOpinion:
        body = _primary_corpus(payload)
        findings: list[str] = []
        cites: list[str] = []
        veto = False

        for code, pattern in _RISK_VIOLATIONS:
            m = pattern.search(body)
            if m:
                matched = "[REDACTED]" if code == "CREDENTIAL_HARDCODE" else repr(m.group(0))
                findings.append(f"{code}: matched {matched}")
                cites.append(f"risk_pattern:{code}")
                # All listed patterns are hard vetoes.
                veto = True

        if payload.kind is TaskKind.TRADE_ENTRY:
            findings.append(
                "TRADE_ENTRY_ROUTE: panel refuses qualitative entry approval; "
                "mandatory_trade_gate + kill switch own execution."
            )
            cites.append("policy:trade_opinion_bypassed")
            # Trade entry is never "passed" by this panel — risk expert fails the LLM path.
            return ExpertOpinion(
                expert=self.name,
                score=0.0,
                passed=False,
                findings=findings,
                evidence_cites=cites,
                veto=True,
            )

        if veto:
            return ExpertOpinion(
                expert=self.name,
                score=0.0,
                passed=False,
                findings=findings or ["risk veto"],
                evidence_cites=cites,
                veto=True,
            )

        return ExpertOpinion(
            expert=self.name,
            score=1.0,
            passed=True,
            findings=findings or ["no hard risk pattern matched"],
            evidence_cites=cites or ["risk_scan:clean"],
            veto=False,
        )


class EvidenceExpert:
    """Requires evidence tokens when strong claims are made."""

    name = ExpertName.EVIDENCE

    def evaluate(self, payload: PanelInput) -> ExpertOpinion:
        body = _primary_corpus(payload)
        claims = _CLAIM_MARKERS.findall(body)
        evidence = _EVIDENCE_TOKENS.findall(body)
        findings: list[str] = []
        cites: list[str] = []

        if not claims:
            return ExpertOpinion(
                expert=self.name,
                score=1.0,
                passed=True,
                findings=["no strong completion/edge claims detected"],
                evidence_cites=["evidence_scan:no_claims"],
                veto=False,
            )

        findings.append(f"claims_detected={claims}")
        if evidence:
            cites.extend(f"evidence:{e}" for e in evidence[:12])
            return ExpertOpinion(
                expert=self.name,
                score=0.9,
                passed=True,
                findings=findings + [f"evidence_tokens={evidence[:12]}"],
                evidence_cites=cites,
                veto=False,
            )

        findings.append("UNVERIFIED_CLAIM: strong claim without SHA / run id / ledger cite / n=")
        # Unverified claim is a fail but not always a policy veto (soft fail).
        # Edge-profit claims without numbers get a veto.
        edge_like = any(
            re.search(r"expectancy|profit\s*factor|edge\s+proven|profitable|live\s+ready", c, re.I)
            for c in claims
        )
        return ExpertOpinion(
            expert=self.name,
            score=0.15,
            passed=False,
            findings=findings,
            evidence_cites=["evidence_scan:missing"],
            veto=bool(edge_like),
        )


class CoordinationExpert:
    """Flags multi-agent lane collisions from claim text / file lists."""

    name = ExpertName.COORDINATION

    def evaluate(self, payload: PanelInput) -> ExpertOpinion:
        findings: list[str] = []
        cites: list[str] = []
        other = payload.other_agent_claims or ""
        me = (payload.agent or "unknown").lower()
        claimed = [c.strip() for c in payload.claimed_files if c.strip()]

        if not other and not claimed:
            return ExpertOpinion(
                expert=self.name,
                score=0.85,
                passed=True,
                findings=["no foreign claims supplied; coordination check limited"],
                evidence_cites=["coord:no_foreign_claims"],
                veto=False,
            )

        # Detect another agent marked In Progress on overlapping paths or same repo scope.
        foreign_agents = {
            m.group(1).lower() for m in _OTHER_AGENT.finditer(other) if m.group(1).lower() != me
        }
        if me in foreign_agents:
            foreign_agents.discard(me)

        overlap: list[str] = []
        for path in claimed:
            if path and path in other:
                overlap.append(path)

        in_progress_foreign = bool(
            re.search(r"in\s*progress|owns|claimed", other, re.I) and foreign_agents
        )

        if overlap and in_progress_foreign:
            findings.append(
                f"LANE_COLLISION: files {overlap} appear in foreign claim by {sorted(foreign_agents)}"
            )
            cites.append("coord:file_overlap")
            return ExpertOpinion(
                expert=self.name,
                score=0.0,
                passed=False,
                findings=findings,
                evidence_cites=cites,
                veto=True,
            )

        if in_progress_foreign and re.search(r"\btrading\b", other, re.I):
            # Soft warning if foreign agent is on trading but files don't overlap.
            findings.append(
                f"FOREIGN_TRADING_ACTIVITY: {sorted(foreign_agents)} — verify Linear/vault before shared files"
            )
            cites.append("coord:foreign_trading")
            return ExpertOpinion(
                expert=self.name,
                score=0.55,
                passed=True,
                findings=findings,
                evidence_cites=cites,
                veto=False,
            )

        findings.append("no hard coordination collision detected")
        cites.append("coord:clean")
        return ExpertOpinion(
            expert=self.name,
            score=1.0,
            passed=True,
            findings=findings,
            evidence_cites=cites,
            veto=False,
        )


class ResearchCriticExpert:
    """Adversarial critic for quantitative strategy research proposals and candidate tournaments."""

    name = ExpertName.RESEARCH_CRITIC

    def evaluate(self, payload: PanelInput) -> ExpertOpinion:
        from src.evals.research_critic import evaluate_strategy_candidate

        body = _primary_corpus(payload)
        if not body:
            return ExpertOpinion(
                expert=self.name,
                score=0.0,
                passed=False,
                findings=["no strategy content provided to evaluate"],
                evidence_cites=["research_critic:empty"],
                veto=True,
            )

        verdict = evaluate_strategy_candidate(body)
        findings = [f"{f.code}: {f.message}" for f in verdict.findings]
        cites = [f"critic:{f.code}" for f in verdict.findings] or ["critic:clean"]

        return ExpertOpinion(
            expert=self.name,
            score=verdict.score,
            passed=verdict.passed,
            findings=findings or ["strategy spec passed adversarial critique"],
            evidence_cites=cites,
            veto=verdict.vetoed,
        )


DEFAULT_EXPERTS: dict[ExpertName, Expert] = {
    ExpertName.RISK_RULES: RiskRulesExpert(),
    ExpertName.EVIDENCE: EvidenceExpert(),
    ExpertName.COORDINATION: CoordinationExpert(),
    ExpertName.RESEARCH_CRITIC: ResearchCriticExpert(),
}


def get_default_experts() -> dict[ExpertName, Expert]:
    return dict(DEFAULT_EXPERTS)


# Optional narrative LLM — cannot override veto; used only for judge_summary polish.
NarrativeJudgeFn = Callable[[str, list[ExpertOpinion]], str]
