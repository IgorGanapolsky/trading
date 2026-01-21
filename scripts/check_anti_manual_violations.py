#!/usr/bin/env python3
"""
Anti-Manual Mandate Violation Detector

This script scans Claude's outputs (commit messages, PR descriptions, etc.)
for forbidden phrases that indicate manual instructions to the CEO.

Per CLAUDE.md directive (Nov 19, 2025): "No manual anything!"

Usage:
    python scripts/check_anti_manual_violations.py [--file FILE]
    python scripts/check_anti_manual_violations.py --check-commits N
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Forbidden phrases that indicate manual instructions
FORBIDDEN_PATTERNS = [
    r"(?i)you need to",
    r"(?i)you should",
    r"(?i)you can run",
    r"(?i)you must",
    r"(?i)please run",
    r"(?i)run this command",
    r"(?i)run the following",
    r"(?i)execute this",
    r"(?i)manual steps",
    r"(?i)manually",
    r"(?i)when you have time",
    r"(?i)when you're ready",
    r"(?i)could you please",
    r"(?i)i need you to",
    r"(?i)please provide",
    r"(?i)your job:",
    r"(?i)option 1.*option 2.*manual",
    r"(?i)next steps:.*\n.*run",
    r"(?i)to do this.*run",
]

# Allowed contexts (false positive prevention)
ALLOWED_CONTEXTS = [
    r"(?i)the system will",
    r"(?i)ci will",
    r"(?i)automated",
    r"(?i)automatically",
    r"(?i)script runs",
    r"(?i)synced",  # Claude describing completed work (past tense)
    r"(?i)ran",  # Claude describing completed work
    r"(?i)executed",  # Claude describing completed work
    r"(?i)verified",  # Claude describing completed work
    r"(?i)i manually",  # Claude describing own action
    r"(?i)claude manually",  # Claude describing own action
]


def check_text(text: str, source: str = "input") -> list[dict]:
    """Check text for anti-manual violations."""
    violations = []

    for pattern in FORBIDDEN_PATTERNS:
        matches = list(re.finditer(pattern, text))
        for match in matches:
            # Check if it's in an allowed context
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end]

            is_allowed = any(re.search(allowed, context) for allowed in ALLOWED_CONTEXTS)

            if not is_allowed:
                violations.append(
                    {
                        "source": source,
                        "pattern": pattern,
                        "match": match.group(),
                        "context": context.strip(),
                        "position": match.start(),
                    }
                )

    return violations


def check_recent_commits(n: int = 10) -> list[dict]:
    """Check recent N commit messages for violations."""
    all_violations = []

    try:
        result = subprocess.run(
            ["git", "log", f"-{n}", "--format=%H|||%s|||%b"],
            capture_output=True,
            text=True,
            check=True,
        )

        for line in result.stdout.strip().split("\n"):
            if "|||" not in line:
                continue

            parts = line.split("|||")
            if len(parts) >= 2:
                commit_hash = parts[0][:8]
                subject = parts[1]
                body = parts[2] if len(parts) > 2 else ""

                full_message = f"{subject}\n{body}"
                violations = check_text(full_message, f"commit:{commit_hash}")
                all_violations.extend(violations)

    except subprocess.CalledProcessError as e:
        print(f"Warning: Could not check git commits: {e}", file=sys.stderr)

    return all_violations


def check_file(filepath: Path) -> list[dict]:
    """Check a file for violations."""
    if not filepath.exists():
        print(f"File not found: {filepath}", file=sys.stderr)
        return []

    text = filepath.read_text()
    return check_text(text, str(filepath))


def main():
    parser = argparse.ArgumentParser(description="Detect anti-manual mandate violations")
    parser.add_argument("--file", "-f", type=Path, help="File to check")
    parser.add_argument(
        "--check-commits",
        "-c",
        type=int,
        default=0,
        help="Check last N commits",
    )
    parser.add_argument("--ci", action="store_true", help="CI mode - exit 1 on violations")

    args = parser.parse_args()

    all_violations = []

    if args.file:
        all_violations.extend(check_file(args.file))

    if args.check_commits > 0:
        all_violations.extend(check_recent_commits(args.check_commits))

    # If no specific check requested, check recent commits
    if not args.file and args.check_commits == 0:
        all_violations.extend(check_recent_commits(5))

    # Report results
    if all_violations:
        print(f"\n🚨 Found {len(all_violations)} Anti-Manual Violations:\n")
        for v in all_violations:
            print(f"  Source: {v['source']}")
            print(f'  Match: "{v["match"]}"')
            print(f"  Context: ...{v['context']}...")
            print()

        if args.ci:
            print("❌ CI FAILED: Anti-manual mandate violations detected")
            print("See: rag_knowledge/lessons_learned/ll_017_anti_manual_violation_dec12.md")
            sys.exit(1)
    else:
        print("✅ No anti-manual violations detected")

    return len(all_violations)


if __name__ == "__main__":
    main()
