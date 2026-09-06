"""JIT task→harness packs for trading ops (deterministic).

Process steal from JIT-Agent (arxiv:2608.25593v2, Sept 2026): harness quality
can dominate model quality. We do **not** train or vendor JIT-Agent.

Four-module artifact (JIT protocol → trading ops):

* memory     — which ledgers / RAG surfaces to load
* plan       — ordered operator steps (planning)
* actions    — allowed scripts / CLI commands (action loop)
* capability — skills allowlist + forbid denylist (tool_policy)

Sept 2026 standards we implement here (not clones):

* Task-specific packs beat fat fixed runtimes
* Lazy / minimal skill surface (in-repo skills only)
* Deterministic fail-closed capability gates (paper-only forbids)
* Selection receipts for archive/eval (logs/, not model training)
* Explicit intent-conflict resolution in the classifier

Selection is keyword/rule based and fail-closed for live execution.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
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
        # JIT-Agent capability/tool_policy module = skills allow + forbid deny
        d["capability"] = {"skills": list(self.skills), "forbid": list(self.forbid)}
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
        skills=("trading-ops",),
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
        skills=("trading-ops",),
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
        skills=("trading-ops",),
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
        skills=("trading-ops",),
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
            "Prefer reading existing data/system_state.json (no live sync)",
            "Refresh paired closed ledger via paper client only",
            "Re-read system_state mtime before trading claims",
            "Do not run sync_alpaca_state.py (live branch when brokerage env present)",
        ),
        actions=(
            "python scripts/spy_put_credit.py --status",
            "python scripts/sync_closed_positions.py",
        ),
        skills=("trading-ops",),
        forbid=_LIVE_FORBIDS
        + (
            "treat unpaired fills as trades",
            "python scripts/sync_alpaca_state.py",
            "live brokerage sync",
        ),
        token_budget_hint=3000,
        rationale="Paper-scoped ledger refresh; never invoke live sync_alpaca_state.",
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
            r"spy_put_credit(?!.*--status)",
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


@dataclass(frozen=True)
class ClassificationResult:
    """Classifier output with explicit conflict notes (Sept 2026 harness honesty)."""

    task_class: TaskClass
    conflict_note: str = ""
    matched_intents: tuple[str, ...] = ()


def _detect_intents(text: str) -> list[str]:
    """Detect intents from the same `_RULES` patterns used for classification."""
    found: list[str] = []
    # Extra dry-run / --status markers used for conflict policy.
    extras = (
        ("dry_run", (r"--dry-run",)),
        ("status", (r"--status\b",)),
    )
    for name, pats in extras:
        if any(re.search(p, text, flags=re.IGNORECASE) for p in pats):
            found.append(name)
    for task_class, patterns in _RULES:
        name = task_class.value
        if name in found:
            continue
        if any(re.search(p, text, flags=re.IGNORECASE) for p in patterns):
            found.append(name)
    return found


def classify_task(prompt: str) -> TaskClass:
    """Map free-text operator intent to a task class (first match)."""
    return classify_with_meta(prompt).task_class


def classify_with_meta(prompt: str) -> ClassificationResult:
    """Classify with conflict notes when multiple intents appear."""
    text = (prompt or "").strip().lower()
    if not text:
        return ClassificationResult(TaskClass.UNKNOWN)
    intents = tuple(_detect_intents(text))
    conflict_note = ""

    # Explicit dry-run language (not bare spy_put_credit) vs --status.
    explicit_dry = bool(re.search(r"dry.?run|--dry-run", text))
    has_status_flag = bool(re.search(r"--status\b", text))
    has_status = "status" in intents or has_status_flag

    # --status without explicit dry-run → STATUS even if spy_put_credit is present
    # (flag may appear before the command name).
    if has_status_flag and not explicit_dry:
        return ClassificationResult(TaskClass.STATUS, conflict_note, intents)

    # Conflict policy: explicit dry-run wins over status when both present.
    if explicit_dry and has_status:
        conflict_note = (
            "conflict: dry_run+status → selected dry_run "
            "(plan path includes status reads; status-only pack would omit --dry-run)"
        )
        return ClassificationResult(TaskClass.DRY_RUN, conflict_note, intents)

    for task_class, patterns in _RULES:
        for pat in patterns:
            if re.search(pat, text, flags=re.IGNORECASE):
                return ClassificationResult(task_class, conflict_note, intents)
    return ClassificationResult(TaskClass.UNKNOWN, conflict_note, intents)


def select_harness(prompt: str) -> HarnessPack:
    """Just-in-time harness selection for a trading ops prompt."""
    meta = classify_with_meta(prompt)
    if meta.task_class == TaskClass.UNKNOWN:
        return _UNKNOWN
    return _PACKS[meta.task_class]


_SECRETISH = re.compile(r"(?i)\b(api[_-]?key|secret|token|password|authorization)\b\s*[:=]?\s*\S+")


def redact_prompt_for_receipt(prompt: str) -> str:
    """Strip credential-shaped tokens before writing selection archives."""
    return _SECRETISH.sub(r"\1=[REDACTED]", prompt or "")


def pack_fingerprint(pack: HarnessPack) -> str:
    """Stable short hash of pack contents for receipts/archive."""
    payload = json.dumps(pack.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def missing_action_scripts(pack: HarnessPack, *, repo_root: Path | None = None) -> list[str]:
    """Return action command scripts that do not exist under repo_root."""
    root = repo_root or Path(__file__).resolve().parents[2]
    missing: list[str] = []
    for action in pack.actions:
        # Extract first scripts/*.py or make target path when present
        m = re.search(r"scripts/[\w./-]+\.py", action)
        if not m:
            continue
        rel = m.group(0)
        if not (root / rel).is_file():
            missing.append(rel)
    return missing


def selection_receipt(
    prompt: str,
    *,
    repo_root: Path | None = None,
    full_budget: int = 12000,
) -> dict[str, Any]:
    """Full selection artifact: pack + capability + conflicts + savings + fingerprint."""
    meta = classify_with_meta(prompt)
    pack = _UNKNOWN if meta.task_class == TaskClass.UNKNOWN else _PACKS[meta.task_class]
    savings = estimate_savings_vs_full_context(pack, full_budget=full_budget)
    missing_skills = unresolved_skills(pack, repo_root=repo_root)
    missing_scripts = missing_action_scripts(pack, repo_root=repo_root)
    return {
        "prompt": redact_prompt_for_receipt(prompt),
        "task_class": pack.task_class.value,
        "matched_intents": list(meta.matched_intents),
        "conflict_note": meta.conflict_note,
        "pack": pack.to_dict(),
        "fingerprint": pack_fingerprint(pack),
        "savings_hint": savings,
        "capability_ok": not missing_skills and not missing_scripts,
        "unresolved_skills": missing_skills,
        "missing_action_scripts": missing_scripts,
        "standards": {
            "source": "arxiv:2608.25593v2 + Sept 2026 harness craft (deterministic)",
            "modules": ["memory", "plan", "actions", "capability"],
            "train_jit_agent": False,
        },
    }


def append_selection_receipt(receipt: dict[str, Any], *, repo_root: Path | None = None) -> Path:
    """Append one JSONL receipt under logs/ (gitignored archive; not training)."""
    root = repo_root or Path(__file__).resolve().parents[2]
    path = root / "logs" / "jit_harness_receipts.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        **receipt,
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    return path


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


def repo_skill_roots(repo_root: Path | None = None) -> tuple[Path, ...]:
    """In-repo skill directories used for readiness honesty."""
    root = repo_root or Path(__file__).resolve().parents[2]
    return (root / "skills",)


def resolve_skill(name: str, repo_root: Path | None = None) -> Path | None:
    """Return SKILL.md path if `name` exists under an in-repo skills root."""
    for base in repo_skill_roots(repo_root):
        candidate = base / name / "SKILL.md"
        if candidate.is_file():
            return candidate
    return None


def unresolved_skills(
    pack: HarnessPack | None = None, *, repo_root: Path | None = None
) -> list[str]:
    """Skill names referenced by packs that lack an in-repo SKILL.md."""
    packs = [pack] if pack is not None else [*_PACKS.values(), _UNKNOWN]
    missing: list[str] = []
    seen: set[str] = set()
    for p in packs:
        for name in p.skills:
            if name in seen:
                continue
            seen.add(name)
            if resolve_skill(name, repo_root) is None:
                missing.append(name)
    return missing


def readiness_report(repo_root: Path | None = None) -> dict[str, Any]:
    """Catalog readiness: skills + action scripts must resolve in-repo."""
    missing = unresolved_skills(repo_root=repo_root)
    missing_scripts: list[str] = []
    seen: set[str] = set()
    for pack in [*_PACKS.values(), _UNKNOWN]:
        for rel in missing_action_scripts(pack, repo_root=repo_root):
            if rel not in seen:
                seen.add(rel)
                missing_scripts.append(rel)
    return {
        "ready": not missing and not missing_scripts,
        "source": "arxiv:2608.25593v2 process steal (deterministic, Sept 2026)",
        "task_classes": list_task_classes(),
        "unresolved_skills": missing,
        "missing_action_scripts": missing_scripts,
        "skill_roots": [str(p) for p in repo_skill_roots(repo_root)],
    }


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
