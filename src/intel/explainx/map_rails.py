"""Map parsed ExplainX items onto existing trading rails. Never auto-install."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from src.intel.explainx.parse import TrendingItem

# Theater we refuse to copy. Do not dual-edit mac-yolo's hardcoded engine.
LOOKALIKE_SNIPPETS = (
    "explainx-trending-rag-engine",
    "tf-idf vectorization",
    "invented views",
    "k-means style topic clustering",
)

SKIP_TYPES = frozenset(
    {
        "workshop",
        "bootcamp",
        "course",
        "video",
        "skill",
        "mcp",
        "agent",
        "tool",
        "plugin",
    }
)


@dataclass(frozen=True)
class RailRule:
    rule_id: str
    rail: str
    disposition: str  # implement | map_existing | skip
    needles: tuple[str, ...]
    types: tuple[str, ...] = ()
    reason: str = ""
    existing: tuple[str, ...] = ()


RULES: tuple[RailRule, ...] = (
    RailRule(
        rule_id="limit_reset_two_ceilings",
        rail="two_ceiling_honesty",
        disposition="implement",
        needles=("limit-reset", "session limit", "weekly cap", "weekly limit still applies"),
        reason="Session/daily cap is not the cohort gate; resetting one does not raise the other.",
        existing=("src/intel/explainx/ceilings.py", "scripts/explainx_trending.py --ceilings"),
    ),
    RailRule(
        rule_id="commerce_planner_executor",
        rail="planner_executor_split",
        disposition="implement",
        needles=("commerce agent", "shopping agent", "merchant agent"),
        reason="Planner proposes; executor must stay policy-accurate. Not a checkout clone.",
        existing=("src/intel/explainx/harness_split.py", "scripts/spy_put_credit.py --dry-run"),
    ),
    RailRule(
        rule_id="show_me_evidence_cli",
        rail="evidence_json_cli",
        disposition="implement",
        needles=("/show-me", "show-me skill", "draw instead of ramble"),
        reason="Operator CLI prints JSON evidence, not a drawing skill and not a ramble.",
        existing=("scripts/explainx_trending.py",),
    ),
    RailRule(
        rule_id="grill_me_judge_panel",
        rail="judge_panel",
        disposition="map_existing",
        needles=("grill-me", "grill me"),
        reason="Do not auto-install third-party grill-me. Interrogate claims via judge_panel.",
        existing=("scripts/judge_panel.py",),
    ),
    RailRule(
        rule_id="agent_harness_survey",
        rail="planner_executor_split",
        disposition="map_existing",
        needles=("agent harness",),
        reason="Survey of harnesses maps to the planner vs executor split already stolen.",
        existing=("src/intel/explainx/harness_split.py",),
    ),
    RailRule(
        rule_id="skills_mcp_loops_workshop",
        rail="existing_operator_primitives",
        disposition="skip",
        needles=("skills, mcp", "free live hour", "agent skills: build a workflow"),
        types=("workshop",),
        reason="Workshop is not our product. Skills/MCP/loops already exist as operator primitives.",
        existing=("skills/trading-ops/SKILL.md",),
    ),
)


def _blob(item: TrendingItem) -> str:
    return " ".join(
        part.lower()
        for part in (item.name, item.href, item.description, item.type)
        if part
    )


def _match_rule(item: TrendingItem) -> RailRule | None:
    blob = _blob(item)
    item_type = (item.type or "").lower()
    for rule in RULES:
        if rule.types and item_type not in rule.types:
            continue
        if any(needle in blob for needle in rule.needles):
            return rule
    return None


def map_item(item: TrendingItem) -> dict[str, Any]:
    rule = _match_rule(item)
    if rule is None:
        skip_reason = (
            "untrusted third-party skill/MCP/agent/tool — never auto-install"
            if item.type in SKIP_TYPES
            else "no trading rail; ExplainX traffic is not lab ROI"
        )
        return {
            "rank": item.rank,
            "name": item.name,
            "href": item.href,
            "score": item.score,
            "type": item.type,
            "disposition": "skip",
            "rail": None,
            "reason": skip_reason,
            "existing": [],
            "auto_install": False,
        }
    return {
        "rank": item.rank,
        "name": item.name,
        "href": item.href,
        "score": item.score,
        "type": item.type,
        "disposition": rule.disposition,
        "rail": rule.rail,
        "reason": rule.reason,
        "existing": list(rule.existing),
        "auto_install": False,
        "rule_id": rule.rule_id,
    }


def map_items(items: Iterable[TrendingItem]) -> list[dict[str, Any]]:
    return [map_item(item) for item in items]


def lookalike_hits(source: str) -> list[str]:
    lowered = source.lower()
    return [snippet for snippet in LOOKALIKE_SNIPPETS if snippet in lowered]
