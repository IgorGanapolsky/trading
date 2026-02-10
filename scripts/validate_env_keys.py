#!/usr/bin/env python3
"""
Validate environment keys against .env.example.

Default behavior: warn-only and exit 0.
Use --strict to exit non-zero if required keys are missing.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip()
    return values


def load_example_keys(example_path: Path) -> list[str]:
    keys: list[str] = []
    if not example_path.exists():
        return keys
    for raw in example_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        keys.append(key)
    return keys


def is_placeholder(value: str) -> bool:
    lowered = value.lower()
    placeholders = (
        "your_",
        "_here",
        "changeme",
        "replace_me",
        "todo",
        "example",
    )
    return any(token in lowered for token in placeholders)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate env keys")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to .env file (default: .env)",
    )
    parser.add_argument(
        "--example-file",
        default=".env.example",
        help="Path to .env.example file (default: .env.example)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any keys are missing",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / args.env_file
    example_path = project_root / args.example_file

    env_values = parse_env_file(env_path)
    example_keys = load_example_keys(example_path)

    combined = {**env_values, **os.environ}

    missing: list[str] = []
    placeholder: list[str] = []
    for key in example_keys:
        val = combined.get(key)
        if not val:
            missing.append(key)
        elif is_placeholder(val):
            placeholder.append(key)

    print("=== ENV VALIDATION ===")
    print(f"Example keys: {len(example_keys)}")
    print(f"Missing keys: {len(missing)}")
    print(f"Placeholder values: {len(placeholder)}")

    if missing:
        print("\nMissing:")
        for key in missing:
            print(f"  - {key}")

    if placeholder:
        print("\nPlaceholder:")
        for key in placeholder:
            print(f"  - {key}")

    if args.strict and (missing or placeholder):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
