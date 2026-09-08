"""PR risk classifier for AI-vs-human review routing.

FORMAT steal from InfoQ Culture & Methods (2026-09-08): skip peer review on
low-risk PRs and use AI approvals when owners/tests cover them. We map that to
path-based risk for trading — never billed Copilot Code Review spend.

High-risk paths (broker, risk constants, live gates) always require human review.
Scripts/docs/RAG-only paths may allow existing CI AI review after tests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any, Iterable

# Paths that touch capital, credentials, or kill-switch semantics.
_HUMAN_GLOBS = (
    "src/risk/",
    "src/safety/",
    "src/core/trading_constants.py",
    "src/core/active_strategy.py",
    "src/utils/alpaca_client.py",
    "data/runtime/strategy_kill_switch.json",
    "data/TRADING_HALTED",
    ".github/workflows/",
    "scripts/spy_put_credit.py",
    "scripts/residual_ic_manager.py",
    "scripts/sync_alpaca_state.py",
)

# Explicit allowlist only — never a blanket scripts/ prefix (submit_order etc.).
_AI_OK_PREFIXES = (
    "docs/",
    "rag_knowledge/",
    "skills/",
    "tests/",
    "src/ops/",
    "src/rag/",
    "README.md",
    "CONTRIBUTING.md",
    "Makefile",
    "AGENTS.md",
    "Claude.md",
    "GEMINI.md",
)

_AI_OK_SCRIPTS = (
    "scripts/context_gist.py",
    "scripts/entry_challenges.py",
    "scripts/flux_graph.py",
    "scripts/infoq_agent_control_plane.py",
    "scripts/package_manager_honesty.py",
)

_BILLED_REVIEW_MARKERS = (
    "copilot code review",
    "billed per review",
    "github copilot autoreview paid",
)


@dataclass(frozen=True)
class PrRiskDecision:
    allow_ai_approve: bool
    require_human: bool
    risk: str  # low | high
    matched_human_paths: tuple[str, ...]
    matched_ai_paths: tuple[str, ...]
    unknown_paths: tuple[str, ...]
    forbid_billed_copilot_review: bool
    ok: bool
    failing: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for key in (
            "matched_human_paths",
            "matched_ai_paths",
            "unknown_paths",
            "failing",
        ):
            d[key] = list(d[key])
        return d


def _norm(path: str) -> str | None:
    """Normalize POSIX relative paths. Reject absolute and root-escaping paths."""

    p = path.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if not p or p.startswith("/") or p.startswith("~") or (len(p) >= 2 and p[1] == ":"):
        return None
    parts: list[str] = []
    for part in PurePosixPath(p).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
            continue
        parts.append(part)
    return "/".join(parts) if parts else None


def _matches_human(path: str) -> bool:
    for pattern in _HUMAN_GLOBS:
        if pattern.endswith("/"):
            if path.startswith(pattern):
                return True
            continue
        if path == pattern:
            return True
        # basename equality for deeply nested copies of the same file
        if PurePosixPath(path).name == PurePosixPath(pattern).name and path.endswith(pattern):
            return True
    return False


def _matches_ai_ok(path: str) -> bool:
    if path in _AI_OK_SCRIPTS:
        return True
    for prefix in _AI_OK_PREFIXES:
        if prefix.endswith("/"):
            if path.startswith(prefix):
                return True
        elif path == prefix:
            return True
    return False


def classify_pr_paths(
    paths: Iterable[str],
    *,
    propose_billed_copilot: bool = False,
) -> PrRiskDecision:
    """Classify changed paths. Fail closed on unknown or billed review."""

    human: list[str] = []
    ai_ok: list[str] = []
    unknown: list[str] = []
    for raw in paths:
        path = _norm(raw)
        if path is None:
            unknown.append(raw.strip().replace("\\", "/") or "(invalid_path)")
            continue
        if path.endswith("/"):
            continue
        if _matches_human(path):
            human.append(path)
        elif _matches_ai_ok(path):
            ai_ok.append(path)
        else:
            unknown.append(path)

    failing: list[str] = []
    if propose_billed_copilot:
        failing.append("billed_copilot_review_forbidden")
    if unknown:
        failing.append("unknown_paths_require_human")

    require_human = bool(human) or bool(unknown) or propose_billed_copilot
    allow_ai = (not require_human) and bool(ai_ok) and not failing
    risk = "high" if require_human else "low"
    if not ai_ok and not human and not unknown:
        failing.append("empty_path_set")
        require_human = True
        allow_ai = False
        risk = "high"

    # Honest high-risk (known human paths) is ok; unknown / billed review is not.
    ok = not bool(unknown) and not propose_billed_copilot and bool(ai_ok or human)

    return PrRiskDecision(
        allow_ai_approve=allow_ai,
        require_human=require_human,
        risk=risk,
        matched_human_paths=tuple(sorted(set(human))),
        matched_ai_paths=tuple(sorted(set(ai_ok))),
        unknown_paths=tuple(sorted(set(unknown))),
        forbid_billed_copilot_review=True,
        ok=ok,
        failing=tuple(failing),
    )


def mentions_billed_review(text: str) -> bool:
    lowered = (text or "").lower()
    return any(m in lowered for m in _BILLED_REVIEW_MARKERS)
