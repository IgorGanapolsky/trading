"""Strategy Research Critic: Adversarial critique engine for candidate strategies.

Inspired by multi-agent trading research patterns (Deep Agents / LangChain):
The Critic actively stress-tests proposed strategy configurations, indicators,
and rules against verified empirical failure modes (10-wide wings, IC complexity,
sub-24h churn, multi-contract scaling, unhedged exposure, low-IV vulnerability).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CriticFinding:
    code: str
    severity: str  # "VETO", "WARNING", "INFO"
    message: str
    rationale: str


@dataclass(frozen=True)
class CriticVerdict:
    passed: bool
    score: float  # 0.0 to 1.0
    vetoed: bool
    findings: list[CriticFinding] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "VETO" if self.vetoed else ("PASS" if self.passed else "FAIL")
        findings_str = "; ".join(f"[{f.severity}] {f.code}: {f.message}" for f in self.findings)
        return f"{status} (score={self.score:.2f}): {findings_str or 'Clean strategy spec'}"


class StrategyResearchCritic:
    """Adversarial critic for quantitative strategy proposals and tournament candidates."""

    _FORBIDDEN_KEYWORDS = [
        (
            "KILLED_FAMILY_IC",
            re.compile(r"\b(iron\s*condor|ic_simple|short\s+strangle)\b", re.I),
            "VETO",
            "Iron condor family is killed due to historical -$7,731 realized loss cluster.",
        ),
        (
            "TEN_WIDE_WINGS",
            re.compile(
                r"\b(10-wide|10\s*\$?\s*wide|\$10\s+spread|wing\s*width\s*[:=]\s*10)\b", re.I
            ),
            "VETO",
            "10-wide wings create excessive tail risk for small capital cohorts.",
        ),
        (
            "SUB_24H_CHURN",
            re.compile(r"\b(intraday\s+exit|scalp|exit\s+under\s+24h|day\s*trad)\b", re.I),
            "VETO",
            "Theta strategies fail under sub-24h churn (historical win rate 9.6% on <24h exits).",
        ),
        (
            "UNHEDGED_SHORT",
            re.compile(r"\b(naked\s+put|naked\s+call|unhedged\s+short)\b", re.I),
            "VETO",
            "All short options must be defined-risk with protective long wings on the same side.",
        ),
        (
            "MULTI_LOT_SCALING",
            re.compile(
                r"\b(scale\s+to\s+\d+\s+contracts|size\s*[:=]\s*[2-9]\d*|contracts\s*[:=]\s*[2-9]\d*)\b",
                re.I,
            ),
            "VETO",
            "Multi-contract scaling is strictly blocked until n>=30 paper edge verification passes.",
        ),
    ]

    def evaluate_text(self, text: str) -> CriticVerdict:
        """Critique freeform strategy text, rule definitions, or PR descriptions."""
        if not text.strip():
            return CriticVerdict(
                passed=False,
                score=0.0,
                vetoed=True,
                findings=[
                    CriticFinding(
                        "EMPTY_SPEC",
                        "VETO",
                        "Strategy specification is empty",
                        "Cannot evaluate empty spec",
                    )
                ],
                recommendations=["Provide explicit strategy entry, exit, and risk parameters."],
            )

        findings: list[CriticFinding] = []
        recommendations: list[str] = []
        vetoed = False

        for code, pattern, sev, reason in self._FORBIDDEN_KEYWORDS:
            if pattern.search(text):
                findings.append(
                    CriticFinding(code, sev, f"Matched forbidden pattern '{code}'", reason)
                )
                recommendations.append(reason)
                if sev == "VETO":
                    vetoed = True

        # Check for positive requirements
        has_regime_gate = bool(re.search(r"regime|ivr|iv\s*rank|vix|200-?dma", text, re.I))
        if not has_regime_gate:
            findings.append(
                CriticFinding(
                    "MISSING_REGIME_GATE",
                    "WARNING",
                    "No market regime filter specified (IVR >= 30, VIX <= 30, SPY > 200-DMA)",
                    "Credit spreads suffer severe drawdown when opened during low-IV complacency or extreme volatility shocks.",
                )
            )
            recommendations.append("Add explicit IV Rank (IVR >= 30) and VIX regime filters.")

        has_defined_exit = bool(re.search(r"take\s*profit|stop\s*loss|7\s*dte|exit", text, re.I))
        if not has_defined_exit:
            findings.append(
                CriticFinding(
                    "UNDEFINED_EXIT",
                    "VETO",
                    "Missing explicit take-profit, stop-loss, or time-exit rules",
                    "Strategies without deterministic exit boundaries suffer severe tail losses.",
                )
            )
            vetoed = True

        score = 0.0 if vetoed else (0.7 if any(f.severity == "WARNING" for f in findings) else 1.0)
        passed = not vetoed and score >= 0.7

        return CriticVerdict(
            passed=passed,
            score=score,
            vetoed=vetoed,
            findings=findings,
            recommendations=recommendations,
        )

    def evaluate_candidate_spec(self, candidate: dict[str, Any]) -> CriticVerdict:
        """Critique a structured candidate from strategy_candidate_tournament.json."""
        strategy_id = candidate.get("strategy_id", "unknown")
        rules = candidate.get("rules", {})
        rules_text = " ".join(f"{k}: {v}" for k, v in rules.items())
        hypothesis = candidate.get("hypothesis", "")
        full_text = f"strategy_id: {strategy_id}\nhypothesis: {hypothesis}\n{rules_text}"

        verdict = self.evaluate_text(full_text)
        return verdict


def evaluate_strategy_candidate(spec: dict[str, Any] | str) -> CriticVerdict:
    """Convenience entrypoint for strategy candidate review."""
    critic = StrategyResearchCritic()
    if isinstance(spec, dict):
        return critic.evaluate_candidate_spec(spec)
    return critic.evaluate_text(str(spec))
