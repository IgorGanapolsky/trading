#!/usr/bin/env python3
"""Emit repo change classifications for GitHub Actions routing."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.change_detection import classify_changed_paths, get_changed_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Repository root path.")
    parser.add_argument("--base-ref", default="HEAD~1", help="Base git ref for diff comparison.")
    parser.add_argument("--head-ref", default="HEAD", help="Head git ref for diff comparison.")
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        default=[],
        help="Explicit changed path (repeatable). Skips git diff when provided.",
    )
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="Write classification fields to $GITHUB_OUTPUT.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    changed_paths = args.paths or get_changed_paths(
        repo_root=repo_root,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
    )
    classification = classify_changed_paths(changed_paths)
    payload = classification.to_output_map()

    if args.github_output:
        output_path = os.environ.get("GITHUB_OUTPUT")
        if not output_path:
            print("GITHUB_OUTPUT is required with --github-output", file=sys.stderr)
            return 1
        with open(output_path, "a", encoding="utf-8") as handle:
            for key, value in payload.items():
                handle.write(f"{key}={value}\n")

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
