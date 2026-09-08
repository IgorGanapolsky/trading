"""AI Studio agent-environment FORMAT steal for trading.

Source: https://ai.google.dev/gemini-api/docs/aistudio-agents
(and https://aistudio.google.com/docs/agents).

Transferable mechanics only:
  - deny-by-default tool toggles
  - network domain allowlist
  - environment sources pack (AGENTS.md + SKILL.md)
  - explicit termination / stop criteria

We do **not** clone Antigravity, Vertex Agent Builder, Managed Agents API,
or billed AI Studio playground runs.
"""

from __future__ import annotations

import fnmatch
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

# Paper-safe operator tools. Anything else requires human / fails closed.
_DEFAULT_TOOL_ALLOWLIST = frozenset(
    {
        "read_file",
        "list_dir",
        "grep",
        "context_gist",
        "entry_challenges",
        "flux_graph",
        "infoq_agent_control_plane",
        "package_manager_honesty",
        "system_health_check",
        "spy_put_credit_status",
        "spy_put_credit_dry_run",
        "audit_open_inventory",
        "residual_ic_manager_dry_run",
        "aistudio_agent_env_doctor",
    }
)

_FORBIDDEN_TOOLS = frozenset(
    {
        "submit_order",
        "close_position",
        "liquidate",
        "live_submit",
        "cancel_all_orders",
        "force_push_main",
    }
)

# Egress domains trading automation may touch. Deny everything else.
_DEFAULT_NETWORK_ALLOWLIST = (
    "api.alpaca.markets",
    "paper-api.alpaca.markets",
    "github.com",
    "api.github.com",
    "raw.githubusercontent.com",
    "linear.app",
    "api.linear.app",
    "127.0.0.1",
    "localhost",
)


@dataclass(frozen=True)
class Dimension:
    name: str
    ok: bool
    detail: str
    failing: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["failing"] = list(self.failing)
        return d


@dataclass(frozen=True)
class AgentEnvironmentReport:
    ok: bool
    score: int
    max_score: int
    failing: tuple[str, ...]
    content_hash: str
    dimensions: dict[str, Dimension]
    not_cloned: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "score": self.score,
            "max_score": self.max_score,
            "failing": list(self.failing),
            "content_hash": self.content_hash,
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "not_cloned": list(self.not_cloned),
            "source": "aistudio-agents-format-steal",
        }


def _find_agents_md(root: Path) -> Path | None:
    for name in ("AGENTS.md", "Agents.md", "agents.md"):
        path = root / name
        if path.is_file():
            return path
    nested = root / ".agents" / "AGENTS.md"
    return nested if nested.is_file() else None


def _skill_md_paths(root: Path) -> list[Path]:
    found: list[Path] = []
    for base in (root / "skills", root / ".agents" / "skills"):
        if not base.is_dir():
            continue
        found.extend(sorted(base.glob("*/SKILL.md")))
    return found


def check_sources_pack(root: Path) -> Dimension:
    """AGENTS.md + at least one SKILL.md (AI Studio .agents sources FORMAT)."""

    agents = _find_agents_md(root)
    skills = _skill_md_paths(root)
    failing: list[str] = []
    if agents is None:
        failing.append("missing_AGENTS_md")
    if not skills:
        failing.append("missing_skill_md")
    detail = f"agents_md={agents.relative_to(root) if agents else 'missing'} skills={len(skills)}"
    return Dimension(
        name="sources_pack",
        ok=not failing,
        detail=detail,
        failing=tuple(failing),
    )


def check_tool_allowlist(
    proposed_tools: Iterable[str],
    *,
    allowlist: Iterable[str] | None = None,
) -> Dimension:
    """Deny-by-default tool toggles (AI Studio tool configuration FORMAT)."""

    allowed = frozenset(allowlist) if allowlist is not None else _DEFAULT_TOOL_ALLOWLIST
    proposed = [t.strip() for t in proposed_tools if str(t).strip()]
    failing: list[str] = []
    if not proposed:
        failing.append("empty_tool_set")
    forbidden_hit = sorted({t for t in proposed if t in _FORBIDDEN_TOOLS})
    unknown = sorted({t for t in proposed if t not in allowed and t not in _FORBIDDEN_TOOLS})
    if forbidden_hit:
        failing.append("forbidden_tools:" + ",".join(forbidden_hit))
    if unknown:
        failing.append("undeclared_tools:" + ",".join(unknown))
    return Dimension(
        name="tool_allowlist",
        ok=not failing,
        detail=f"proposed={len(proposed)} allowed_pool={len(allowed)}",
        failing=tuple(failing),
    )


def _domain_allowed(domain: str, patterns: tuple[str, ...]) -> bool:
    """Match hostname only; reject URL userinfo authority tricks."""

    candidate = domain.strip().lower()
    if not candidate:
        return False
    parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
    if parsed.username is not None or parsed.password is not None:
        return False
    host = (parsed.hostname or "").rstrip(".")
    if not host:
        return False
    for pattern in patterns:
        p = pattern.lower()
        if host == p or host.endswith("." + p) or fnmatch.fnmatch(host, p):
            return True
    return False


def check_network_allowlist(
    proposed_domains: Iterable[str],
    *,
    allowlist: Iterable[str] | None = None,
) -> Dimension:
    """Fail closed on undeclared egress domains."""

    patterns = tuple(allowlist) if allowlist is not None else _DEFAULT_NETWORK_ALLOWLIST
    proposed = [d.strip() for d in proposed_domains if str(d).strip()]
    failing: list[str] = []
    if not proposed:
        # Empty is ok for offline-only operator packs.
        return Dimension(
            name="network_allowlist",
            ok=True,
            detail="no_egress_requested",
            failing=(),
        )
    denied = sorted({d for d in proposed if not _domain_allowed(d, patterns)})
    if denied:
        failing.append("denied_domains:" + ",".join(denied))
    return Dimension(
        name="network_allowlist",
        ok=not failing,
        detail=f"proposed={len(proposed)} patterns={len(patterns)}",
        failing=tuple(failing),
    )


def check_termination_criteria(
    *,
    stop_when: str,
    acceptance_criteria: Iterable[str],
    out_of_scope: str = "",
) -> Dimension:
    """Narrow tasks need explicit stop conditions (AI Studio cost FORMAT)."""

    acs = [a.strip() for a in acceptance_criteria if str(a).strip()]
    stop = (stop_when or "").strip()
    out = (out_of_scope or "").strip()
    failing: list[str] = []
    if not stop and not out:
        failing.append("missing_stop_or_out_of_scope")
    if len(acs) < 1:
        failing.append("need_at_least_one_acceptance_criterion")
    return Dimension(
        name="termination_criteria",
        ok=not failing,
        detail=f"stop={'set' if stop or out else 'missing'} acs={len(acs)}",
        failing=tuple(failing),
    )


_NOT_CLONED = (
    "Google AI Studio Playground",
    "Antigravity managed agent",
    "Vertex Agent Builder",
    "Managed Agents API",
    "billed Gemini agent sandbox",
)


def diagnose_agent_environment(
    root: Path | str,
    *,
    proposed_tools: Iterable[str] | None = None,
    proposed_domains: Iterable[str] | None = None,
    stop_when: str = "doctor exits; do not call Gemini sandbox",
    acceptance_criteria: Iterable[str] | None = None,
    out_of_scope: str = "Antigravity; Vertex Agent Builder; billed AI Studio runs",
    tool_allowlist: Iterable[str] | None = None,
    network_allowlist: Iterable[str] | None = None,
) -> AgentEnvironmentReport:
    """Run the four-dimension doctor. Exit-ready via CLI."""

    base = Path(root)
    tools = list(
        proposed_tools
        if proposed_tools is not None
        else (
            "context_gist",
            "entry_challenges",
            "system_health_check",
            "spy_put_credit_dry_run",
            "aistudio_agent_env_doctor",
        )
    )
    domains = list(proposed_domains) if proposed_domains is not None else []
    acs = list(
        acceptance_criteria
        if acceptance_criteria is not None
        else ("tests pass", "CLI fail-closed on undeclared tool/domain")
    )

    dims = {
        "sources_pack": check_sources_pack(base),
        "tool_allowlist": check_tool_allowlist(tools, allowlist=tool_allowlist),
        "network_allowlist": check_network_allowlist(domains, allowlist=network_allowlist),
        "termination_criteria": check_termination_criteria(
            stop_when=stop_when,
            acceptance_criteria=acs,
            out_of_scope=out_of_scope,
        ),
    }
    failing = tuple(name for name, dim in dims.items() if not dim.ok)
    score = sum(1 for dim in dims.values() if dim.ok)
    payload = "|".join(
        [
            str(base.resolve()),
            *tools,
            *domains,
            stop_when,
            out_of_scope,
            *acs,
            *failing,
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return AgentEnvironmentReport(
        ok=not failing,
        score=score,
        max_score=len(dims),
        failing=failing,
        content_hash=digest,
        dimensions=dims,
        not_cloned=_NOT_CLONED,
    )
