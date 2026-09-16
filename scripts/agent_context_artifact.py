#!/usr/bin/env python3
"""Wisdom.ai FORMAT steal: context as a reusable agent artifact, not metadata.

Sources:
  https://music.youtube.com/watch?v=lRuI0imju0Y
  https://www.wisdom.ai/

Steal: tribal knowledge becomes a lintable pack (goal, constraints, sources,
freshness, verifier) for *agent* consumers. Semantic layer / ACE / Foundry /
Snowflake OSI are the wrong product for this paper lab.

Do not clone Wisdom.ai, Adaptive Context Engine, Palantir Foundry, or OSI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REQUIRED = ("id", "consumer", "goal", "constraints", "sources", "freshness_max_hours", "verifier")
WRONG_FIT_REQUIRED = "wisdom_ai"
SOURCES = (
    "https://music.youtube.com/watch?v=lRuI0imju0Y",
    "https://www.wisdom.ai/",
)
REFUSES = (
    "do_not_clone_wisdom_ai",
    "do_not_clone_palantir_foundry",
    "do_not_clone_snowflake_osi",
    "context_is_a_product_not_metadata",
    "agent_consumer_not_human_dashboard",
)


def lint(pack: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for key in REQUIRED:
        if key not in pack or pack[key] in (None, "", [], {}):
            errors.append(f"missing:{key}")
    if pack.get("consumer") != "agent":
        errors.append("consumer_must_be_agent")
    constraints = pack.get("constraints")
    if not isinstance(constraints, list) or not constraints:
        errors.append("constraints_must_be_nonempty_list")
    sources = pack.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("sources_must_be_nonempty_list")
    else:
        for i, src in enumerate(sources):
            if not isinstance(src, dict) or not (src.get("path") or src.get("url")):
                errors.append(f"source_{i}_needs_path_or_url")
    hours = pack.get("freshness_max_hours")
    if not isinstance(hours, (int, float)) or hours <= 0:
        errors.append("freshness_max_hours_must_be_positive")
    wrong = pack.get("wrong_fit") or []
    if WRONG_FIT_REQUIRED not in wrong:
        errors.append("must_declare_wisdom_ai_wrong_fit")
    return {
        "ok": not errors,
        "errors": errors,
        "id": pack.get("id"),
        "consumer": pack.get("consumer"),
        "framework": "agent_context_artifact",
        "stolen_format": (
            "Soham Mazumdar / Wisdom.ai episode: context as product for agents; "
            "reusable artifacts not tacit knowledge; Wisdom.ai is the wrong SKU here"
        ),
        "refuses": list(REFUSES),
        "sources": list(SOURCES),
    }


def load_pack(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    li = sub.add_parser("lint", help="validate an agent context pack")
    li.add_argument("--pack", required=True, type=Path)
    args = p.parse_args(argv)
    report = lint(load_pack(args.pack))
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
