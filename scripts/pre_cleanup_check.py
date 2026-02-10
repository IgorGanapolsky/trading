#!/usr/bin/env python3
"""
Pre-cleanup dependency check.

Usage:
  python3 scripts/pre_cleanup_check.py path/to/module.py

Prints any references to the module import path or basename so deletions are safe.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def module_from_path(path: Path) -> str | None:
    try:
        rel = path.relative_to(PROJECT_ROOT)
    except ValueError:
        return None
    if rel.suffix != ".py":
        return None
    return ".".join(rel.with_suffix("").parts)


def rg_search(pattern: str, exclude: Path | None = None) -> list[str]:
    try:
        cmd = ["rg", "-n", pattern, str(PROJECT_ROOT)]
        if exclude is not None:
            cmd.insert(1, f"--glob=!{exclude}")
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            return result.stdout.strip().splitlines()
    except FileNotFoundError:
        return ["rg not found; install ripgrep to run dependency search."]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Check for references before deletion")
    parser.add_argument("path", help="Path to module/file to check")
    args = parser.parse_args()

    target = Path(args.path)
    if not target.is_absolute():
        target = PROJECT_ROOT / target

    if not target.exists():
        print(f"ERROR: {target} not found")
        return 1

    module = module_from_path(target)
    basename = target.stem

    print("============================================")
    print("PRE-CLEANUP CHECK")
    print("============================================")
    print(f"Target: {target}")
    if module:
        print(f"Module: {module}")
    print(f"Basename: {basename}")
    print("")

    patterns = []
    if module:
        patterns.append(rf"(from|import)\s+{re.escape(module)}(\s|$|,)")
    patterns.append(rf"\\b{re.escape(basename)}\\b")

    findings: list[str] = []
    exclude = target.relative_to(PROJECT_ROOT)
    for pattern in patterns:
        matches = rg_search(pattern, exclude=exclude)
        findings.extend(matches)

    if findings:
        print("References found:")
        for line in findings:
            print(f"  {line}")
        print("")
        print("Result: NOT SAFE to delete without updating references.")
        return 2

    print("No references found.")
    print("Result: SAFE to delete (verify manually if needed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
