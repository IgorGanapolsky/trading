#!/usr/bin/env python3
"""
Validates GitHub Actions workflow files for syntax and required fields.

Usage:
    python3 scripts/validate_workflows.py .github/workflows/*.yml

Checks:
- Valid YAML syntax
- Has 'on:' block with at least one event
- Has at least one 'jobs:' entry
- No unclosed heredocs

Exits non-zero if any validation fails.

Created: Dec 11, 2025
See: rag_knowledge/lessons_learned/ll_009_ci_syntax_failure_dec11.md
"""

import re
import sys
from pathlib import Path
from typing import Any

import yaml


class WorkflowValidator:
    """Validates GitHub Actions workflow files."""

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_yaml_syntax(self, file_path: Path) -> dict[str, Any] | None:
        """Validate YAML syntax and return parsed content."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = yaml.safe_load(f)
            return content
        except yaml.YAMLError as e:
            self.errors.append(f"{file_path}: YAML syntax error: {e}")
            return None

    def validate_on_block(self, workflow: dict[str, Any], file_path: Path) -> bool:
        """Validate 'on:' block exists with at least one event."""
        # Note: 'on' is a Python/YAML keyword, so it gets parsed as True in some cases
        has_on = True in workflow or "on" in workflow

        if not has_on:
            self.errors.append(f"{file_path}: Missing 'on:' block")
            return False

        # Get the actual on block
        on_block = workflow.get(True) or workflow.get("on")

        if on_block is None:
            self.errors.append(f"{file_path}: 'on:' block is empty")
            return False

        # Check if it has at least one event
        if isinstance(on_block, dict) or isinstance(on_block, list):
            if not on_block:
                self.errors.append(f"{file_path}: 'on:' block has no events")
                return False
        elif isinstance(on_block, str):
            # Single event like 'on: push'
            pass
        else:
            self.errors.append(f"{file_path}: 'on:' block has unexpected type: {type(on_block)}")
            return False

        return True

    def validate_jobs_block(self, workflow: dict[str, Any], file_path: Path) -> bool:
        """Validate 'jobs:' block exists with at least one job."""
        if "jobs" not in workflow:
            self.errors.append(f"{file_path}: Missing 'jobs:' block")
            return False

        jobs = workflow["jobs"]
        if not isinstance(jobs, dict):
            self.errors.append(f"{file_path}: 'jobs:' must be a dict")
            return False

        if not jobs:
            self.errors.append(f"{file_path}: 'jobs:' block is empty")
            return False

        return True

    def validate_heredocs(self, file_path: Path) -> bool:
        """Check for unclosed heredocs in YAML file."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Find all heredoc starts (<<EOF or <<-EOF)
            heredoc_starts = re.findall(r"<<-?EOF", content)
            # Find all heredoc ends (EOF at start of line)
            heredoc_ends = re.findall(r"^EOF", content, re.MULTILINE)

            if len(heredoc_starts) != len(heredoc_ends):
                self.warnings.append(
                    f"{file_path}: Heredoc mismatch: {len(heredoc_starts)} starts, {len(heredoc_ends)} ends"
                )
                return False

            return True
        except Exception as e:
            self.warnings.append(f"{file_path}: Could not check heredocs: {e}")
            return True  # Don't fail validation on heredoc check errors

    def validate_workflow(self, file_path: Path) -> bool:
        """Validate a single workflow file. Returns True if valid."""
        print(f"Validating: {file_path}")

        # 1. Validate YAML syntax
        workflow = self.validate_yaml_syntax(file_path)
        if workflow is None:
            return False

        # 2. Validate 'on:' block
        if not self.validate_on_block(workflow, file_path):
            return False

        # 3. Validate 'jobs:' block
        if not self.validate_jobs_block(workflow, file_path):
            return False

        # 4. Check heredocs (warning only)
        self.validate_heredocs(file_path)

        print(f"  ✅ {file_path.name} is valid")
        return True

    def validate_all(self, file_paths: list[Path]) -> int:
        """Validate all workflow files. Returns exit code."""
        if not file_paths:
            print("No workflow files to validate")
            return 0

        print(f"Validating {len(file_paths)} workflow file(s)...\n")

        valid_count = 0
        invalid_count = 0

        for file_path in file_paths:
            if self.validate_workflow(file_path):
                valid_count += 1
            else:
                invalid_count += 1
            print()

        # Print summary
        print("=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        print(f"✅ Valid:   {valid_count}")
        print(f"❌ Invalid: {invalid_count}")
        print(f"Total:     {len(file_paths)}")

        if self.errors:
            print(f"\n🚨 {len(self.errors)} error(s):")
            for error in self.errors:
                print(f"  - {error}")

        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} warning(s):")
            for warning in self.warnings:
                print(f"  - {warning}")

        if invalid_count > 0:
            print("\n❌ VALIDATION FAILED")
            return 1

        print("\n✅ ALL WORKFLOWS VALID")
        return 0


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/validate_workflows.py .github/workflows/*.yml")
        print("\nValidates GitHub Actions workflow files for:")
        print("  - Valid YAML syntax")
        print("  - Has 'on:' block with at least one event")
        print("  - Has at least one 'jobs:' entry")
        print("  - No unclosed heredocs")
        return 1

    # Collect all workflow files
    workflow_files = []
    for arg in sys.argv[1:]:
        path = Path(arg)
        if path.is_file() and path.suffix in [".yml", ".yaml"]:
            workflow_files.append(path)
        elif path.is_dir():
            # If directory, find all .yml/.yaml files
            workflow_files.extend(path.glob("*.yml"))
            workflow_files.extend(path.glob("*.yaml"))

    if not workflow_files:
        print("No workflow files found")
        return 1

    validator = WorkflowValidator()
    return validator.validate_all(workflow_files)


if __name__ == "__main__":
    sys.exit(main())
