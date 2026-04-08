#!/usr/bin/env python3
"""Fail when public-facing copy drifts into stale or misleading claims."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REQUIRED_FILES = [
    "README.md",
    "docs/index.md",
    "docs/LIVE_STRATEGY.md",
    "docs/data/public_status.json",
    "wiki/Home.md",
    "wiki/Progress-Dashboard.md",
    "wiki/Development-Engine-and-Evidence.md",
    ".github/public/about.txt",
]

BANNED_PATTERNS = [
    r"Paper-trading SPY iron condors \(15-delta, 30-45 DTE\)\. Validating strategy on 30 trades before scaling\.",
    r"Current Status \(Mar \d{1,2}, 2026\)",
    r"Trade 1 of 30",
    r"80%\+ win rate",
    r"Last Updated:\s*2026-03-23",
    r"Current Position \(Trade 1 of 30\)",
]


def find_violations(repo_root: Path) -> list[str]:
    violations: list[str] = []

    for rel in REQUIRED_FILES:
        path = repo_root / rel
        if not path.exists():
            violations.append(f"Missing required public surface file: {rel}")

    index_path = repo_root / "docs/index.md"
    if index_path.exists():
        index_text = index_path.read_text(encoding="utf-8")
        if "/data/public_status.json" not in index_text:
            violations.append("docs/index.md must fetch docs/data/public_status.json")

    about_path = repo_root / ".github/public/about.txt"
    if about_path.exists():
        about_text = about_path.read_text(encoding="utf-8").strip()
        if len(about_text) > 160:
            violations.append(".github/public/about.txt exceeds GitHub About description limits")

    for rel in REQUIRED_FILES:
        path = repo_root / rel
        if not path.exists() or path.suffix == ".json":
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in BANNED_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                violations.append(f"{rel} contains stale public copy matching: {pattern}")

    public_status_path = repo_root / "docs/data/public_status.json"
    if public_status_path.exists():
        try:
            status = json.loads(public_status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            violations.append(f"docs/data/public_status.json is invalid JSON: {exc}")
        else:
            required_keys = {"generated_at_et", "paper", "ledger", "gate", "links"}
            missing = required_keys - set(status)
            if missing:
                violations.append(
                    f"docs/data/public_status.json missing required keys: {sorted(missing)}"
                )

    return violations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check public copy freshness and congruence.")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    violations = find_violations(repo_root)
    if violations:
        for violation in violations:
            print(f"ERROR: {violation}")
        return 1
    print("Public copy freshness checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
