#!/usr/bin/env python3
"""
WORKFLOW INTEGRITY TESTS

These tests verify that GitHub Actions workflows are properly configured
and will NOT silently fail. This catches the exact class of bug that
caused trading to be silently skipped for 30+ days.

CRITICAL: These tests MUST pass before any workflow changes are merged.

Test categories:
1. Output variable consistency - every `if: steps.X.outputs.Y` has a corresponding write
2. No dangerous fault tolerance - critical steps must not have continue-on-error
3. Condition completeness - all conditional paths must be covered
"""

import re
import sys
from pathlib import Path
from typing import NamedTuple

import yaml


class OutputReference(NamedTuple):
    """A reference to a step output in a workflow condition."""

    workflow: str
    job: str
    step: str
    output_name: str
    line_number: int


class OutputWrite(NamedTuple):
    """A write to GITHUB_OUTPUT in a workflow step."""

    workflow: str
    job: str
    step_id: str
    output_name: str
    line_number: int


def load_workflow(path: Path) -> dict:
    """Load a workflow YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def find_output_references(workflow_path: Path) -> list[OutputReference]:
    """Find all references to step outputs in workflow conditions."""
    references = []
    content = workflow_path.read_text()
    lines = content.split("\n")

    # Pattern: steps.STEP_ID.outputs.OUTPUT_NAME
    pattern = r"steps\.([a-zA-Z_][a-zA-Z0-9_-]*)\.outputs\.([a-zA-Z_][a-zA-Z0-9_]*)"

    workflow_name = workflow_path.name

    for line_num, line in enumerate(lines, 1):
        for match in re.finditer(pattern, line):
            step_id = match.group(1)
            output_name = match.group(2)
            references.append(
                OutputReference(
                    workflow=workflow_name,
                    job="",  # Could parse this but not critical
                    step=step_id,
                    output_name=output_name,
                    line_number=line_num,
                )
            )

    return references


# Known outputs that are set by external sources (Python scripts, actions, etc.)
KNOWN_EXTERNAL_OUTPUTS = {
    # Python script check_duplicate_execution.py writes these
    ("check_execution", "skip"),
    ("check_execution", "skip_reason"),
    # Python script validate_secrets.py writes this
    ("validate_secrets", "secrets_valid"),
    # GitHub Script actions set these via core.setOutput()
    ("check_status", "disabled_count"),
    ("check_status", "disabled_workflows"),
    ("health_check", "report"),
    # dependabot/fetch-metadata action sets these
    ("metadata", "dependency"),
    ("metadata", "update"),
    ("is_security", "is_security"),
}


def find_output_writes(workflow_path: Path) -> list[OutputWrite]:
    """Find all writes to GITHUB_OUTPUT in a workflow."""
    writes = []
    content = workflow_path.read_text()
    lines = content.split("\n")

    workflow_name = workflow_path.name

    # Pattern: OUTPUT_NAME=value >> $GITHUB_OUTPUT or >> "$GITHUB_OUTPUT"
    pattern = r'echo\s+["\']?([a-zA-Z_][a-zA-Z0-9_]*)=.*>>\s*\$?GITHUB_OUTPUT'

    current_step_id = None

    for line_num, line in enumerate(lines, 1):
        # Track current step ID
        id_match = re.search(r"^\s+id:\s*([a-zA-Z_][a-zA-Z0-9_-]*)", line)
        if id_match:
            current_step_id = id_match.group(1)

        # Find output writes
        for match in re.finditer(pattern, line):
            output_name = match.group(1)
            writes.append(
                OutputWrite(
                    workflow=workflow_name,
                    job="",
                    step_id=current_step_id or "unknown",
                    output_name=output_name,
                    line_number=line_num,
                )
            )

    return writes


def find_python_output_writes(workflow_path: Path) -> list[OutputWrite]:
    """Find Python code that writes to GITHUB_OUTPUT."""
    writes = []
    content = workflow_path.read_text()
    lines = content.split("\n")

    workflow_name = workflow_path.name

    # Pattern for Python: f.write(f"OUTPUT_NAME=...) or similar
    pattern = r'\.write\([^)]*["\']([a-zA-Z_][a-zA-Z0-9_]*)='

    current_step_id = None

    for line_num, line in enumerate(lines, 1):
        # Track current step ID
        id_match = re.search(r"^\s+id:\s*([a-zA-Z_][a-zA-Z0-9_-]*)", line)
        if id_match:
            current_step_id = id_match.group(1)

        for match in re.finditer(pattern, line):
            output_name = match.group(1)
            writes.append(
                OutputWrite(
                    workflow=workflow_name,
                    job="",
                    step_id=current_step_id or "unknown",
                    output_name=output_name,
                    line_number=line_num,
                )
            )

    return writes


class WorkflowIntegrityTests:
    """Tests for workflow integrity and silent failure prevention."""

    def __init__(self):
        self.workflows_dir = Path(__file__).parent.parent / ".github" / "workflows"
        self.critical_workflows = [
            "daily-trading.yml",
            "weekend-crypto-trading.yml",
            "ci.yml",
        ]

    def test_output_variable_consistency(self) -> tuple[bool, str]:
        """
        CRITICAL TEST: Verify every output reference has a corresponding write.

        This catches the exact bug that caused 30+ days of silent failures:
        - Workflow checked: steps.health_check.outputs.health_check_passed == 'true'
        - But health_check step NEVER wrote health_check_passed to GITHUB_OUTPUT
        - Result: Condition always false, trading silently skipped
        """
        errors = []

        for workflow_file in self.workflows_dir.glob("*.yml"):
            references = find_output_references(workflow_file)
            bash_writes = find_output_writes(workflow_file)
            python_writes = find_python_output_writes(workflow_file)
            all_writes = bash_writes + python_writes

            # Build set of (step_id, output_name) that are written
            written_outputs = {(w.step_id, w.output_name) for w in all_writes}

            for ref in references:
                # Skip known external outputs (set by Python scripts, actions, etc.)
                if (ref.step, ref.output_name) in KNOWN_EXTERNAL_OUTPUTS:
                    continue

                # Check if this output is ever written by the referenced step
                if (ref.step, ref.output_name) not in written_outputs:
                    # Check if any step writes this output (might be different ID)
                    any_write = any(w.output_name == ref.output_name for w in all_writes)
                    if not any_write:
                        errors.append(
                            f"{ref.workflow}:{ref.line_number} - "
                            f"steps.{ref.step}.outputs.{ref.output_name} "
                            f"is referenced but NEVER written to GITHUB_OUTPUT"
                        )

        if errors:
            return False, "Missing output writes:\n" + "\n".join(errors)

        return True, "All output references have corresponding writes"

    def test_critical_steps_no_fault_tolerance(self) -> tuple[bool, str]:
        """
        CRITICAL TEST: Trading execution steps must NOT have continue-on-error.

        If trading fails, we MUST know about it. Silent failures = missed trades.
        """
        errors = []

        critical_step_patterns = [
            r"Execute.*trading",
            r"Execute.*crypto",
            r"Validate secrets",
            r"Pre-market health check",
            r"Run tests",
        ]

        for workflow_name in self.critical_workflows:
            workflow_path = self.workflows_dir / workflow_name
            if not workflow_path.exists():
                continue

            content = workflow_path.read_text()
            lines = content.split("\n")

            current_step_name = None
            in_critical_step = False

            for line_num, line in enumerate(lines, 1):
                # Track step names
                name_match = re.search(r"^\s+-\s+name:\s*(.+)$", line)
                if name_match:
                    current_step_name = name_match.group(1).strip()
                    in_critical_step = any(
                        re.search(pattern, current_step_name, re.IGNORECASE)
                        for pattern in critical_step_patterns
                    )

                # Check for continue-on-error in critical steps
                if in_critical_step and "continue-on-error: true" in line:
                    errors.append(
                        f"{workflow_name}:{line_num} - "
                        f"CRITICAL step '{current_step_name}' has continue-on-error: true"
                    )

        if errors:
            return False, "Dangerous fault tolerance in critical steps:\n" + "\n".join(errors)

        return True, "No fault tolerance in critical steps"

    def test_trading_step_conditions_complete(self) -> tuple[bool, str]:
        """
        Test that trading execution conditions cover all cases.

        The trading step should execute if:
        - Not skipped (duplicate check passed)
        - Health check passed

        Both conditions MUST be explicitly set.
        """
        errors = []

        for workflow_name in ["daily-trading.yml", "weekend-crypto-trading.yml"]:
            workflow_path = self.workflows_dir / workflow_name
            if not workflow_path.exists():
                continue

            content = workflow_path.read_text()

            # Find the Execute trading step condition
            # Match "Execute daily trading" or "Execute weekend crypto trading"
            match = re.search(
                r"name:\s*Execute\s+(?:daily\s+|weekend\s+crypto\s+)?trading.*\n\s+(?:id:.*\n\s+)?if:\s*(.+)",
                content,
                re.IGNORECASE,
            )

            if not match:
                errors.append(f"{workflow_name}: No 'Execute trading' step found")
                continue

            condition = match.group(1)

            # Verify both required conditions are present
            if "skip" not in condition.lower():
                errors.append(f"{workflow_name}: Trading step missing skip check in condition")

            if "health_check" not in condition.lower():
                errors.append(f"{workflow_name}: Trading step missing health_check in condition")

        if errors:
            return False, "Incomplete trading conditions:\n" + "\n".join(errors)

        return True, "Trading step conditions are complete"

    def test_no_silent_exit_patterns(self) -> tuple[bool, str]:
        """
        Test that workflows don't have patterns that hide failures.

        Dangerous patterns:
        - `|| true` on critical commands
        - `|| exit 0` that converts failures to success
        - `set +e` without proper error handling
        """
        errors = []

        dangerous_patterns = [
            (
                r"python3?\s+scripts/autonomous_trader\.py.*\|\|\s*true",
                "autonomous_trader.py || true",
            ),
            (
                r"python3?\s+scripts/autonomous_trader\.py.*\|\|\s*exit\s+0",
                "autonomous_trader.py || exit 0",
            ),
        ]

        for workflow_name in self.critical_workflows:
            workflow_path = self.workflows_dir / workflow_name
            if not workflow_path.exists():
                continue

            content = workflow_path.read_text()
            lines = content.split("\n")

            for line_num, line in enumerate(lines, 1):
                for pattern, description in dangerous_patterns:
                    if re.search(pattern, line):
                        errors.append(
                            f"{workflow_name}:{line_num} - Dangerous pattern: {description}"
                        )

        if errors:
            return False, "Silent exit patterns found:\n" + "\n".join(errors)

        return True, "No silent exit patterns in critical workflows"

    def test_secrets_validation_fails_workflow(self) -> tuple[bool, str]:
        """
        Test that secrets validation failure actually fails the workflow.

        Previously, secrets validation always returned success even when
        secrets were missing, allowing the workflow to proceed without
        credentials.
        """
        for workflow_name in ["daily-trading.yml"]:
            workflow_path = self.workflows_dir / workflow_name
            if not workflow_path.exists():
                return False, f"{workflow_name} not found"

            content = workflow_path.read_text()

            # Check that secrets validation has exit 1 on failure
            if "secrets_valid=false" not in content:
                return False, f"{workflow_name}: No secrets_valid=false on failure"

            if "exit 1" not in content:
                return False, f"{workflow_name}: No exit 1 on secrets failure"

            # Check that subsequent jobs depend on secrets_valid
            if "secrets_valid == 'true'" not in content:
                return False, f"{workflow_name}: Jobs don't check secrets_valid"

        return True, "Secrets validation properly fails workflow"

    def run_all(self) -> list[tuple[str, bool, str]]:
        """Run all integrity tests."""
        tests = [
            ("Output Variable Consistency", self.test_output_variable_consistency),
            ("No Fault Tolerance in Critical Steps", self.test_critical_steps_no_fault_tolerance),
            ("Trading Conditions Complete", self.test_trading_step_conditions_complete),
            ("No Silent Exit Patterns", self.test_no_silent_exit_patterns),
            ("Secrets Validation Fails Workflow", self.test_secrets_validation_fails_workflow),
        ]

        results = []
        for test_name, test_func in tests:
            try:
                passed, message = test_func()
                results.append((test_name, passed, message))
            except Exception as e:
                results.append((test_name, False, f"Test exception: {e}"))

        return results


def main():
    """Run workflow integrity tests."""
    print("=" * 70)
    print("WORKFLOW INTEGRITY TESTS")
    print("Catches silent failures BEFORE they break trading for a month")
    print("=" * 70)
    print()

    tester = WorkflowIntegrityTests()
    results = tester.run_all()

    passed = 0
    failed = 0

    for test_name, passed_test, message in results:
        status = "PASS" if passed_test else "FAIL"
        icon = "✅" if passed_test else "❌"
        print(f"{icon} {status}: {test_name}")
        if not passed_test:
            for line in message.split("\n"):
                print(f"   {line}")
        if passed_test:
            passed += 1
        else:
            failed += 1

    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed > 0:
        print()
        print("❌ WORKFLOW INTEGRITY COMPROMISED")
        print("   Fix these issues BEFORE merging any workflow changes!")
        return 1

    print()
    print("✅ ALL WORKFLOW INTEGRITY TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
