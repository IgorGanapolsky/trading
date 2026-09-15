#!/usr/bin/env python3
"""AGENTS.md / CLAUDE.md health (DAIR.AI / ETH Zurich AGENTbench FORMAT).

Source: academy.dair.ai/dashboard/resources/agents-md-evaluation
Paper: arXiv:2602.11988 — human-written context +4%; LLM-generated −2%;
all context files add ~20% inference cost. Redundancy with README hurts.

Steal (not a clone of AGENTbench):
  - Prefer human, non-obvious tooling/conventions over README restatement
  - Bound file size (cost floor)
  - Flag LLM-generator tells / directory-tour fluff

EXIT 0 when ok. EXIT 2 with --strict on breaches.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Soft budgets — trading Agents.md is already dense; warn before ballooning.
DEFAULT_MAX_CHARS = 12_000
DEFAULT_MAX_README_OVERLAP = 0.35  # Jaccard on word tokens vs README

LLM_TELLS = [
    re.compile(r"\bthis (repository|repo|project) (is|provides|contains)\b", re.I),
    re.compile(r"\boverview of (the )?codebase\b", re.I),
    re.compile(r"\bdirectory structure\b", re.I),
    re.compile(r"\bhere is a (comprehensive|complete) (guide|overview)\b", re.I),
]

# Signals of non-obvious, additive guidance (what human files tend to encode).
ADDITIVE_MARKERS = [
    re.compile(r"\bmake (check|dry-run)\b", re.I),
    re.compile(r"\bspy_put_credit\b"),
    re.compile(r"\bworktree\b", re.I),
    re.compile(r"\bLinear\b"),
    re.compile(r"\bkill.?switch\b", re.I),
    re.compile(r"\bpaper only\b", re.I),
    re.compile(r"\bnever (hardcode|auto-send|force-push)\b", re.I),
]


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z0-9_]{3,}", text)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def evaluate(
    *,
    root: Path = ROOT,
    max_chars: int = DEFAULT_MAX_CHARS,
    max_readme_overlap: float = DEFAULT_MAX_README_OVERLAP,
) -> dict:
    candidates = [
        root / "Agents.md",
        root / "AGENTS.md",
        root / "Claude.md",
        root / "CLAUDE.md",
        root / ".claude" / "CLAUDE.md",
    ]
    readme = root / "README.md"
    readme_tok = (
        _tokens(readme.read_text(encoding="utf-8", errors="replace")) if readme.exists() else set()
    )

    files: list[dict] = []
    breaches: list[dict] = []
    seen_inode: set[Path] = set()
    for path in candidates:
        if not path.exists():
            continue
        resolved = path.resolve()
        if resolved in seen_inode:
            continue  # macOS case-insensitive: Agents.md == AGENTS.md
        seen_inode.add(resolved)
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(root))
        chars = len(text)
        tok = _tokens(text)
        overlap = _jaccard(tok, readme_tok) if readme_tok else 0.0
        tells = [p.pattern for p in LLM_TELLS if p.search(text)]
        additive = [p.pattern for p in ADDITIVE_MARKERS if p.search(text)]
        row = {
            "path": rel,
            "chars": chars,
            "readme_overlap": round(overlap, 3),
            "llm_tells": tells,
            "additive_markers": len(additive),
            "ok": True,
        }
        if chars > max_chars:
            row["ok"] = False
            breaches.append(
                {
                    "path": rel,
                    "metric": "chars",
                    "value": chars,
                    "threshold": max_chars,
                    "why": "DAIR/ETH: every context file adds ~20% inference cost — keep minimal",
                }
            )
        if overlap > max_readme_overlap and chars > 2000:
            row["ok"] = False
            breaches.append(
                {
                    "path": rel,
                    "metric": "readme_overlap",
                    "value": round(overlap, 3),
                    "threshold": max_readme_overlap,
                    "why": (
                        "DAIR/ETH: LLM-style README restatement hurts (−2%); "
                        "encode non-obvious tooling only"
                    ),
                }
            )
        if tells and len(additive) < 2:
            row["ok"] = False
            breaches.append(
                {
                    "path": rel,
                    "metric": "llm_tells_without_additive",
                    "value": tells,
                    "why": "Looks like generator fluff without project-specific rails",
                }
            )
        if len(additive) == 0 and chars > 500:
            breaches.append(
                {
                    "path": rel,
                    "metric": "missing_additive_markers",
                    "severity": "warn",
                    "why": "No non-obvious tooling markers found — may be overview-only",
                }
            )
        files.append(row)

    warn_only = [b for b in breaches if b.get("severity") == "warn"]
    hard = [b for b in breaches if b.get("severity") != "warn"]
    return {
        "ok": len(hard) == 0,
        "framework": "agents_md_health",
        "stolen_format": (
            "DAIR.AI agents-md-evaluation / ETH Zurich arXiv:2602.11988 — "
            "human-specific +4%, LLM-redundant −2%, cost floor ~20%"
        ),
        "source": {
            "academy": "https://academy.dair.ai/dashboard/resources/agents-md-evaluation",
            "paper": "https://arxiv.org/abs/2602.11988",
        },
        "files": files,
        "breaches": hard,
        "warnings": warn_only,
        "practices": {
            "prefer": "Minimal, specific, non-obvious tooling/conventions (human-authored)",
            "never": "Auto-generate AGENTS.md that restates README / directory tours",
        },
        "ts": datetime.now(UTC).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    p.add_argument("--max-readme-overlap", type=float, default=DEFAULT_MAX_README_OVERLAP)
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    out = evaluate(max_chars=args.max_chars, max_readme_overlap=args.max_readme_overlap)
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
