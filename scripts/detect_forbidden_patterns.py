#!/usr/bin/env python3
"""
Forbidden Pattern Detector

Scans codebase for patterns that should NOT exist based on CEO directives.
Runs as pre-commit hook and CI gate.

Forbidden Patterns (Dec 16, 2025):
- Disabled features that haven't been removed

Usage:
    python scripts/detect_forbidden_patterns.py
    python scripts/detect_forbidden_patterns.py --fix  # Show what to delete
"""

import argparse
import re
import sys
from pathlib import Path

# Forbidden patterns with explanations
FORBIDDEN_PATTERNS = {
    # Empty - all forbidden patterns were crypto-related and have been removed
}

# File extensions to scan
SCANNABLE_EXTENSIONS = {".py", ".yml", ".yaml", ".json", ".sh"}

# Directories to skip entirely
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox"}


def should_scan_file(file_path: Path, exclude_dirs: list, exclude_files: list) -> bool:
    """Determine if a file should be scanned."""
    # Check extension
    if file_path.suffix not in SCANNABLE_EXTENSIONS:
        return False

    # Check if in excluded directory
    for exclude_dir in exclude_dirs:
        if exclude_dir in file_path.parts:
            return False

    # Check if excluded file
    return file_path.name not in exclude_files


def scan_file(file_path: Path, patterns: list) -> list:
    """Scan a single file for forbidden patterns."""
    matches = []
    try:
        content = file_path.read_text(errors="ignore")
        for i, line in enumerate(content.split("\n"), 1):
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    matches.append(
                        {"file": str(file_path), "line": i, "content": line.strip()[:100], "pattern": pattern}
                    )
    except Exception:
        pass  # Skip files that can't be read
    return matches


def scan_codebase(forbidden_config: dict) -> dict:
    """Scan entire codebase for forbidden patterns."""
    results = {}

    for category, config in forbidden_config.items():
        results[category] = {
            "reason": config["reason"],
            "matches": [],
        }

        # Walk the codebase
        for file_path in Path(".").rglob("*"):
            if file_path.is_file():
                # Skip certain directories
                if any(skip_dir in file_path.parts for skip_dir in SKIP_DIRS):
                    continue

                if should_scan_file(
                    file_path, config.get("exclude_dirs", []), config.get("exclude_files", [])
                ):
                    matches = scan_file(file_path, config["patterns"])
                    results[category]["matches"].extend(matches)

    return results


def main():
    parser = argparse.ArgumentParser(description="Detect forbidden patterns in codebase")
    parser.add_argument("--fix", action="store_true", help="Show fix suggestions")
    parser.add_argument("--strict", action="store_true", help="Exit with error on matches")
    args = parser.parse_args()

    print("=" * 60)
    print("FORBIDDEN PATTERN DETECTOR")
    print("=" * 60)
    print()

    results = scan_codebase(FORBIDDEN_PATTERNS)
    total_matches = 0

    for category, data in results.items():
        matches = data["matches"]
        if matches:
            print(f"❌ {category.upper()}: {len(matches)} violations found")
            print(f"   Reason: {data['reason']}")
            print()

            # Group by file
            by_file = {}
            for match in matches:
                file = match["file"]
                if file not in by_file:
                    by_file[file] = []
                by_file[file].append(match)

            for file, file_matches in by_file.items():
                print(f"   {file}:")
                for m in file_matches[:5]:  # Limit to 5 per file
                    print(f"      Line {m['line']}: {m['content'][:60]}...")
                if len(file_matches) > 5:
                    print(f"      ... and {len(file_matches) - 5} more")
                print()

            total_matches += len(matches)

            if args.fix:
                print(f"   FIX: Delete or modify these files to remove {category} code")
                print()
        else:
            print(f"✅ {category.upper()}: No violations found")

    print("=" * 60)

    if total_matches > 0:
        print(f"RESULT: {total_matches} forbidden pattern(s) found")
        print()
        print("These patterns violate CEO directives and must be removed.")
        if args.strict:
            sys.exit(1)
    else:
        print("RESULT: Codebase clean ✅")

    return total_matches


if __name__ == "__main__":
    main()
