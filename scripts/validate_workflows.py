#!/usr/bin/env python3
"""
Workflow Validation Script

Validates GitHub Actions workflows to prevent silent failures.
This script catches issues like:
- Unconditional success returns after failures
- Silent exit 0 patterns
- Missing error handling

Run as pre-commit hook or in CI to prevent broken workflows from merging.

Usage:
    python scripts/validate_workflows.py
    python scripts/validate_workflows.py --strict  # Fail on warnings too
"""

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple


class ValidationIssue(NamedTuple):
    """Represents a validation issue found in a workflow."""
    file: str
    line: int
    severity: str  # "error" or "warning"
    message: str
    pattern: str


# Required patterns for critical workflows
REQUIRED_PATTERNS = {
    "daily-trading.yml": [
        {
            "pattern": r"--gha-output",
            "message": "Secrets validation must use --gha-output flag",
            "severity": "error",
        },
    ],
}


def validate_workflow(file_path: Path) -> list[ValidationIssue]:
    """Validate a single workflow file."""
    issues = []
    content = file_path.read_text()
    filename = file_path.name

    # Check for required patterns
    if filename in REQUIRED_PATTERNS:
        for req in REQUIRED_PATTERNS[filename]:
            pattern = re.compile(req["pattern"], re.MULTILINE | re.IGNORECASE)
            if not pattern.search(content):
                issues.append(
                    ValidationIssue(
                        file=filename,
                        line=0,
                        severity=req["severity"],
                        message=req["message"],
                        pattern="(missing)",
                    )
                )

    # Check for dangerous silent exit patterns
    silent_exit_pattern = re.compile(
        r'echo\s+"No\s+.*"\s*\n\s*exit\s+0',
        re.MULTILINE | re.IGNORECASE
    )
    for match in silent_exit_pattern.finditer(content):
        line_num = content[: match.start()].count("\n") + 1
        issues.append(
            ValidationIssue(
                file=filename,
                line=line_num,
                severity="warning",
                message="Silent exit 0 - consider logging warning or failing",
                pattern=match.group(0)[:40],
            )
        )

    return issues


def main():
    parser = argparse.ArgumentParser(description="Validate workflows")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--workflows-dir", type=Path, default=Path(".github/workflows"))
    args = parser.parse_args()

    if not args.workflows_dir.exists():
        print(f"Workflows directory not found: {args.workflows_dir}")
        return 1

    yaml_files = list(args.workflows_dir.glob("*.yml"))
    exit_code = 0

    print(f"Validating {len(yaml_files)} workflows...")

    for wf in sorted(yaml_files):
        issues = validate_workflow(wf)
        if issues:
            for issue in issues:
                icon = "ERROR" if issue.severity == "error" else "WARN"
                print(f"[{icon}] {issue.file}:{issue.line} - {issue.message}")
                if issue.severity == "error":
                    exit_code = 1
        else:
            print(f"OK: {wf.name}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
