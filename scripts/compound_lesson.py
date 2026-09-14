#!/usr/bin/env python3
"""Compound Engineering fourth step FORMAT (Every / AI Engineer Substack).

Each unit of engineering work makes the next easier.
Write every correction into a durable compound log that future agents read.
Detects repeat corrections (same slug) so you know when compounding is paying off.

Not an Every plugin install. Complements `.claude/rules/compound-engineering.md`.

EXIT 0. With --strict: EXIT 2 if repeat without --force.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOUND = ROOT / ".planning" / "COMPOUND.md"
RULES_HINT = ROOT / ".claude" / "rules" / "compound-engineering.md"


def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:80] or "lesson"


def _existing_slugs(text: str) -> set[str]:
    return set(re.findall(r"^### slug:\s*(\S+)", text, re.M))


def record(
    *,
    slug: str,
    correction: str,
    prevention: str,
    evidence: str,
    severity: int = 3,
    force: bool = False,
) -> dict:
    COMPOUND.parent.mkdir(parents=True, exist_ok=True)
    slug = _slugify(slug)
    prior = COMPOUND.read_text() if COMPOUND.exists() else ""
    if not prior:
        prior = (
            "# COMPOUND — lessons that make the next run easier\n\n"
            "Stolen format: Compound Engineering fourth step "
            "(plan → work → review → **compound**).\n"
            "Also see `.claude/rules/compound-engineering.md` (Fix→Test→Prevent→Memory→Verify).\n\n"
        )
    repeats = slug in _existing_slugs(prior)
    if repeats and not force:
        return {
            "ok": False,
            "repeat": True,
            "slug": slug,
            "path": str(COMPOUND),
            "message": (
                "Same correction twice — compound is paying for itself. "
                "Promote to .claude/rules/ or a runtime guard; pass --force to re-append."
            ),
            "stolen_format": "Compound Engineering (Every / Substack comparison)",
        }

    ts = datetime.now(UTC).isoformat()
    block = f"""
### slug: {slug}
- ts: {ts}
- severity: {severity}
- correction: {correction.strip()}
- prevention: {prevention.strip()}
- evidence: {evidence.strip()}
- next_agent_must: Read this before repeating the mistake

"""
    COMPOUND.write_text(prior.rstrip() + "\n" + block)
    return {
        "ok": True,
        "repeat": repeats,
        "slug": slug,
        "path": str(COMPOUND),
        "rules_hint": str(RULES_HINT),
        "stolen_format": "Compound Engineering fourth step",
        "ts": ts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--correction", required=True)
    parser.add_argument("--prevention", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--severity", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    out = record(
        slug=args.slug,
        correction=args.correction,
        prevention=args.prevention,
        evidence=args.evidence,
        severity=args.severity,
        force=args.force,
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out.get("ok"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
