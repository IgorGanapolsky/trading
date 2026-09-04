"""JIT task→harness packs for trading ops (deterministic).

Process steal from JIT-Agent (arxiv:2608.25593 / Rohan Paul X 2026-09-02):
a smaller model with the *right task-specific harness* beats a stronger model
in a fat fixed harness. We do **not** train or vendor JIT-Agent.

Four-module harness artifact (paper protocol, mapped to ops):

* memory  — which ledgers / RAG surfaces to load
* plan    — ordered operator steps
* actions — allowed scripts / CLI commands
* skills  — skill routes to load (and hard forbids)

Selection is keyword/rule based and fail-closed for live execution.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class TaskClass(StrEnum):
    STATUS = "status"
    DRY_RUN = "dry_run"
    INVENTORY = "inventory"
    RAG_SEARCH = "rag_search"
    PR_HYGIENE = "pr_hygiene"
    RESIDUAL_IC = "residual_ic"
    BROKER_SYNC = "broker_sync"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HarnessPack:
    """Composable four-module harness for one task class."""

    task_class: TaskClass
    memory: tuple[str, ...]
    plan: tuple[str, ...]
    actions: tuple[str, ...]
    skills: tuple[str, ...]
    forbid: tuple[str, ...]
    token_budget_hint: int
    paper_only: bool = True
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["task_class"] = self.task_class.value
        return d

    def compact(self) -> str:
        lines = [
            f"task_class: {self.task_class.value}",
            f"paper_only: {self.paper_only}",
            f"token_budget_hint: {self.token_budget_hint}",
            "memory:",
            *[f"  - {m}" for m in self.memory],
            "plan:",
            *[f"  - {p}" for p in self.plan],
            "actions:",
            *[f"  - {a}" for a in self.actions],
            "skills:",
            *[f"  - {s}" for s in self.skills],
            "forbid:",
            *[f"  - {f}" for f in self.forbid],
        ]
        if self.rationale:
            lines.append(f"rationale: {self.rationale}")
        return "\n".join(lines)


# Shared hard forbids — always included.
_LIVE_FORBIDS = (
    "live order submit",
    "close_position outside guardian",
    "delete TRADING_HALTED",
    "force-push main",
    "hardcode Alpaca credentials",
)

_PACKS: dict[TaskClass, HarnessPack] = {
    TaskClass.STATUS: HarnessPack(
        task_class=TaskClass.STATUS,
        memory=(
            "data/system_state.json",
            "data/runtime/strategy_kill_switch.json",
            "data/put_credit_entries.json",
        ),
        plan=(
            "Read kill switch active_family + live_blocked",
            "Run spy_put_credit --status",
            "Cite equity/positions from system_state.json only",
        ),
        actions=(
            "python scripts/spy_put_credit.py --status",
            "python scripts/system_health_check.py",
        ),
        skills=("trading-ops", "alpaca-paper-trading"),
        forbid=_LIVE_FORBIDS + ("make dry-run unless asked",),
        token_budget_hint=2500,
        rationale="Read-only status; smallest memory surface.",
    ),
    TaskClass.DRY_RUN: HarnessPack(
        task_class=TaskClass.DRY_RUN,
        memory=(
            "data/runtime/strategy_kill_switch.json",
            "data/system_state.json",
            "data/put_credit_entries.json",
        ),
        plan=(
            "Confirm paper mode / live_blocked",
            "Audit open inventory (must be clean)",
            "Plan put-credit with --dry-run (no submit)",
            "State plan != executed trade",
        ),
        actions=(
            "python scripts/audit_open_inventory.py",
            "python scripts/spy_put_credit.py --dry-run",
            "make dry-run",
        ),
        skills=("trading-ops", "alpaca-paper-trading"),
        forbid=_LIVE_FORBIDS + ("omit --dry-run", "claim planned trade as filled"),
        token_budget_hint=4000,
        rationale="Paper plan path; inventory gate before risk.",
    ),
    TaskClass.INVENTORY: HarnessPack(
        task_class=TaskClass.INVENTORY,
        memory=(
            "data/system_state.json",
            "data/put_credit_entries.json",
            ".claude/rules/open-inventory-hygiene.md",
        ),
        plan=(
            "Run open inventory audit",
            "If exit 2 unclean: block new risk",
            "Residual IC exits only via residual_ic_manager",
        ),
        actions=(
            "python scripts/audit_open_inventory.py",
            "python scripts/residual_ic_manager.py --dry-run",
        ),
        skills=("trading-ops",),
        forbid=_LIVE_FORBIDS + ("freehand close legs", "new iron-condor entries"),
        token_budget_hint=3000,
        rationale="Inventory hygiene owns unclean-book decisions.",
    ),
    TaskClass.RAG_SEARCH: HarnessPack(
        task_class=TaskClass.RAG_SEARCH,
        memory=(
            "rag_knowledge/lessons_learned/",
            "docs/ZG_LOCAL_SEARCH.md",
            "data/trades.json (paired only)",
        ),
        plan=(
            "Prefer zg_search four-route local search",
            "Cite lesson IDs / path:line evidence",
            "No profitability claim without paired cohort n",
        ),
        actions=(
            "python scripts/zg_search.py --check-ready",
            'python scripts/zg_search.py "<query>"',
            'python scripts/zg_search.py --route rg "<symbol>"',
            'python scripts/graph_rag_query.py --query "<q>" --graph-only',
        ),
        skills=("trading-ops", "zg-local-first-search", "fleet-repo-intelligence"),
        forbid=_LIVE_FORBIDS + ("invent expectancy from 0 trades",),
        token_budget_hint=3500,
        rationale="Compact retrieval beats dumping full RAG into context.",
    ),
    TaskClass.PR_HYGIENE: HarnessPack(
        task_class=TaskClass.PR_HYGIENE,
        memory=(
            "docs/AGENT_COORDINATION.md",
            "Handoffs/linear-claims/ (vault)",
            ".github/pull_request_template.md",
        ),
        plan=(
            "List open PRs + required checks",
            "Resolve review threads before merge",
            "Bare Base SHA in PR body",
            "Merge only when required CI green",
        ),
        actions=(
            "gh pr list --state open",
            "gh pr checks <N>",
            "gh pr merge <N> --auto --squash",
            "make coordination-preflight",
        ),
        skills=(
            "trading-ops",
            "fleet-pr-hygiene",
            "trading-pr-base-sha-bare",
            "three-bus-ship-cycle",
            "multi-agent-coord",
        ),
        forbid=_LIVE_FORBIDS + ("gh pr merge --admin", "force-push"),
        token_budget_hint=5000,
        rationale="PR hygiene does not need trade ledgers or strategy code.",
    ),
    TaskClass.RESIDUAL_IC: HarnessPack(
        task_class=TaskClass.RESIDUAL_IC,
        memory=(
            "data/runtime/strategy_kill_switch.json",
            "data/system_state.json",
            ".claude/rules/kill-criteria.md",
        ),
        plan=(
            "Confirm IC new entries killed",
            "Dry-run residual_ic_manager only",
            "Do not revive ic_simple / iron_condor entries",
        ),
        actions=("python scripts/residual_ic_manager.py --dry-run",),
        skills=("trading-ops",),
        forbid=_LIVE_FORBIDS
        + (
            "new iron condor entries",
            "close outside residual_ic_manager / spy_put_credit manage-exits",
        ),
        token_budget_hint=3000,
        rationale="Exit-only residual inventory path.",
    ),
    TaskClass.BROKER_SYNC: HarnessPack(
        task_class=TaskClass.BROKER_SYNC,
        memory=("data/system_state.json", "data/trades.json"),
        plan=(
            "Refresh broker snapshot",
            "Refresh paired closed ledger",
            "Re-read system_state mtime before trading claims",
        ),
        actions=(
            "python scripts/sync_alpaca_state.py",
            "python scripts/sync_closed_positions.py",
        ),
        skills=("trading-ops", "alpaca-paper-trading"),
        forbid=_LIVE_FORBIDS + ("treat unpaired fills as trades",),
        token_budget_hint=3000,
        rationale="Sync mutates local ledgers only; still paper-scoped.",
    ),
}

_UNKNOWN = HarnessPack(
    task_class=TaskClass.UNKNOWN,
    memory=("skills/trading-ops/SKILL.md", "data/runtime/strategy_kill_switch.json"),
    plan=(
        "Rephrase into a known task class",
        "Default to STATUS read-only until classified",
    ),
    actions=("python scripts/spy_put_credit.py --status",),
    skills=("trading-ops",),
    forbid=_LIVE_FORBIDS
    + (
        "guess live submit",
        "load full repo into context",
    ),
    token_budget_hint=2000,
    rationale="Fail closed: unknown → status-only until reclassified.",
)

# Ordered rules: first match wins.
_RULES: tuple[tuple[TaskClass, tuple[str, ...]], ...] = (
    (
        TaskClass.PR_HYGIENE,
        (
            r"\bpr\b",
            r"pull request",
            r"merge",
            r"ci\b",
            r"greptile",
            r"branch hygiene",
            r"open prs",
            r"automerge",
        ),
    ),
    (
        TaskClass.RESIDUAL_IC,
        (
            r"residual.?ic",
            r"iron.?condor",
            r"\bic_simple\b",
            r"exit.?only.?ic",
        ),
    ),
    (
        TaskClass.INVENTORY,
        (
            r"inventory",
            r"orphan",
            r"unclean",
            r"lot.?mismatch",
            r"audit_open_inventory",
        ),
    ),
    (
        TaskClass.BROKER_SYNC,
        (
            r"sync.?alpaca",
            r"broker.?sync",
            r"refresh.?ledger",
            r"sync_closed",
            r"system_state",
        ),
    ),
    (
        TaskClass.DRY_RUN,
        (
            r"dry.?run",
            r"plan.?trade",
            r"put.?credit.*plan",
            r"spy_put_credit",
            r"\bmake dry-run\b",
        ),
    ),
    (
        TaskClass.RAG_SEARCH,
        (
            r"\brag\b",
            r"lesson",
            r"zg_search",
            r"search",
            r"graph.?rag",
            r"recall",
            r"why.*(kill|halt|stop)",
        ),
    ),
    (
        TaskClass.STATUS,
        (
            r"\bstatus\b",
            r"health",
            r"equity",
            r"positions",
            r"kill.?switch",
            r"how.*(account|doing)",
        ),
    ),
)


def classify_task(prompt: str) -> TaskClass:
    """Map free-text operator intent to a task class (first match)."""
    text = (prompt or "").strip().lower()
    if not text:
        return TaskClass.UNKNOWN
    for task_class, patterns in _RULES:
        for pat in patterns:
            if re.search(pat, text, flags=re.IGNORECASE):
                return task_class
    return TaskClass.UNKNOWN


def select_harness(prompt: str) -> HarnessPack:
    """Just-in-time harness selection for a trading ops prompt."""
    task_class = classify_task(prompt)
    if task_class == TaskClass.UNKNOWN:
        return _UNKNOWN
    return _PACKS[task_class]


def list_task_classes() -> list[dict[str, Any]]:
    """Catalog for --list / agent discovery."""
    out: list[dict[str, Any]] = []
    for tc, pack in _PACKS.items():
        out.append(
            {
                "task_class": tc.value,
                "token_budget_hint": pack.token_budget_hint,
                "paper_only": pack.paper_only,
                "skills": list(pack.skills),
                "actions_n": len(pack.actions),
            }
        )
    out.append(
        {
            "task_class": TaskClass.UNKNOWN.value,
            "token_budget_hint": _UNKNOWN.token_budget_hint,
            "paper_only": True,
            "skills": list(_UNKNOWN.skills),
            "actions_n": len(_UNKNOWN.actions),
        }
    )
    return out


def estimate_savings_vs_full_context(pack: HarnessPack, full_budget: int = 12000) -> dict[str, Any]:
    """Rough token-budget comparison vs loading a fat fixed harness."""
    used = pack.token_budget_hint
    saved = max(0, full_budget - used)
    pct = round(100.0 * saved / full_budget, 1) if full_budget else 0.0
    return {
        "full_budget": full_budget,
        "pack_budget": used,
        "saved_tokens_hint": saved,
        "saved_pct_hint": pct,
        "note": "Heuristic budget, not measured LLM tokens.",
    }
