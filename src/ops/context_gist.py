"""Deterministic context gisting for trading agent sessions.

FORMAT steal from Shopify Gisting + Ricardo Ferreira context engineering
(InfoQ 2026-09-08): compress dumps to in/out scope + acceptance criteria under
a hard token budget. We do **not** train learned tokens, vendor Shopify, or
add Redis summarization.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any

# Rough chars-per-token for budget math (deterministic, not a tokenizer claim).
_CHARS_PER_TOKEN = 4
_DEFAULT_BUDGET = 1200


@dataclass(frozen=True)
class ContextGist:
    """Bounded session pack: goal, constraints, ACs, dropped noise."""

    in_scope: str
    out_scope: str
    acceptance_criteria: tuple[str, ...]
    goal: str
    constraints: tuple[str, ...]
    token_budget: int
    estimated_tokens: int
    dropped_sections: tuple[str, ...]
    content_hash: str
    ok: bool
    failing: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["acceptance_criteria"] = list(self.acceptance_criteria)
        d["constraints"] = list(self.constraints)
        d["dropped_sections"] = list(self.dropped_sections)
        d["failing"] = list(self.failing)
        return d

    def compact(self) -> str:
        lines = [
            f"goal: {self.goal}",
            f"in_scope: {self.in_scope}",
            f"out_scope: {self.out_scope}",
            "acceptance_criteria:",
            *[f"  - {ac}" for ac in self.acceptance_criteria],
            "constraints:",
            *[f"  - {c}" for c in self.constraints],
            f"token_budget: {self.token_budget}",
            f"estimated_tokens: {self.estimated_tokens}",
            f"ok: {self.ok}",
        ]
        if self.dropped_sections:
            lines.append("dropped_sections:")
            lines.extend(f"  - {s}" for s in self.dropped_sections)
        if self.failing:
            lines.append("failing:")
            lines.extend(f"  - {f}" for f in self.failing)
        return "\n".join(lines)


_NEWSLETTER_NOISE = (
    "sponsored by",
    "save your seat",
    "download the report",
    "unsubscribe",
    "qcon san francisco",
    "view it in your browser",
    "tiger data",
    "moderne",
    "harness webinar",
)


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN) if text else 0


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _is_noise(section: str) -> bool:
    lowered = section.lower()
    return any(marker in lowered for marker in _NEWSLETTER_NOISE)


def gist_context(
    *,
    goal: str,
    in_scope: str,
    out_scope: str,
    acceptance_criteria: list[str] | tuple[str, ...],
    constraints: list[str] | tuple[str, ...] | None = None,
    extras: list[str] | tuple[str, ...] | None = None,
    token_budget: int = _DEFAULT_BUDGET,
) -> ContextGist:
    """Build a fail-closed gist. Requires in/out + ≥2 ACs within budget."""

    budget = int(token_budget)
    goal_c = _clean(goal)
    in_c = _clean(in_scope)
    out_c = _clean(out_scope)
    acs = tuple(_clean(a) for a in acceptance_criteria if _clean(a))
    cons = tuple(_clean(c) for c in (constraints or ()) if _clean(c))
    dropped: list[str] = []
    kept_extras: list[str] = []
    for raw in extras or ():
        piece = _clean(raw)
        if not piece:
            continue
        if _is_noise(piece):
            dropped.append(f"noise:{piece[:48]}")
            continue
        kept_extras.append(piece)

    failing: list[str] = []
    if not in_c:
        failing.append("missing_in_scope")
    if not out_c:
        failing.append("missing_out_scope")
    if len(acs) < 2:
        failing.append("need_at_least_two_acceptance_criteria")
    if budget < 200:
        failing.append("token_budget_too_small")

    # Pack under budget: goal/in/out/ACs first, then constraints, then extras.
    core_parts = [
        f"goal:{goal_c}",
        f"in:{in_c}",
        f"out:{out_c}",
        *[f"ac:{a}" for a in acs],
    ]
    used = estimate_tokens("\n".join(core_parts))
    final_constraints: list[str] = []
    for c in cons:
        cost = estimate_tokens(c) + 2
        if used + cost > budget:
            dropped.append(f"constraint:{c[:48]}")
            continue
        final_constraints.append(c)
        used += cost
    for e in kept_extras:
        cost = estimate_tokens(e) + 2
        if used + cost > budget:
            dropped.append(f"extra:{e[:48]}")
            continue
        final_constraints.append(f"extra:{e}")
        used += cost

    if used > budget:
        failing.append("over_token_budget")

    payload = "|".join(
        [
            goal_c,
            in_c,
            out_c,
            *acs,
            *final_constraints,
            str(budget),
            *dropped,
            *failing,
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    ok = not failing
    return ContextGist(
        in_scope=in_c,
        out_scope=out_c,
        acceptance_criteria=acs,
        goal=goal_c or "(unset)",
        constraints=tuple(final_constraints),
        token_budget=budget,
        estimated_tokens=used,
        dropped_sections=tuple(dropped),
        content_hash=digest,
        ok=ok,
        failing=tuple(failing),
    )
