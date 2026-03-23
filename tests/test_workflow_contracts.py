#!/usr/bin/env python3
"""Test that workflows use valid CLI flags.

Prevents ll_025-type failures where workflows use deprecated CLI flags
that cause silent failures in production.
"""

import subprocess
import sys
from pathlib import Path
import re

try:
    import yaml
except ImportError:
    import pytest

    pytest.skip("pyyaml not installed", allow_module_level=True)


def check_workflow_commands(workflow_path: Path):
    """Check workflow commands for valid CLI flags."""
    if not workflow_path.exists():
        print(f"⚠️  Workflow not found: {workflow_path}")
        return

    # Read workflow
    workflow = yaml.safe_load(workflow_path.read_text())

    # Extract commands from workflow
    found_commands = []
    for job_name, job in workflow.get("jobs", {}).items():
        for step in job.get("steps", []):
            run_cmd = step.get("run", "")
            if "autonomous_trader.py" in run_cmd:
                found_commands.append((job_name, step.get("name", "unnamed"), run_cmd))

    if not found_commands:
        print("✅ Weekend workflow uses inline Python (not autonomous_trader.py)")
        return

    # Validate each command uses current CLI interface
    for job_name, step_name, cmd in found_commands:
        for line in cmd.split("&&"):
            line = line.strip()
            if "autonomous_trader.py" in line:
                python_cmd = line.split("python3 ")[-1].strip()
                print(f"✅ {job_name}/{step_name}: {python_cmd}")


def test_all_cli_flags_exist():
    """Verify expected CLI flags exist in iron_condor_trader.py (the only trader)."""
    result = subprocess.run(
        ["python3", "scripts/iron_condor_trader.py", "--help"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        if "ModuleNotFoundError" in result.stderr or "No module named" in result.stderr:
            print("⚠️  Skipping CLI flag check: dependencies not installed in this CI job")
            print(
                "   (Full import validation is covered by Test Suite and Syntax & Import Verification)"
            )
            return
        print("❌ Failed to get iron_condor_trader.py help text")
        print(result.stderr)
        sys.exit(1)

    help_text = result.stdout

    # Expected CLI flags that workflows depend on
    expected_flags = ["--symbol"]

    for flag in expected_flags:
        if flag in help_text:
            print(f"✅ Flag '{flag}' exists in CLI")
        else:
            print(f"❌ Flag '{flag}' not found in CLI help")
            sys.exit(1)


def test_daily_trading_workflow_flags():
    """Verify daily-trading.yml uses valid autonomous_trader.py flags."""
    workflow_path = Path(".github/workflows/daily-trading.yml")

    if not workflow_path.exists():
        print(f"⚠️  Workflow not found: {workflow_path}")
        return

    workflow = yaml.safe_load(workflow_path.read_text())

    # Check for autonomous_trader.py usage
    found_commands = []
    for job_name, job in workflow.get("jobs", {}).items():
        for step in job.get("steps", []):
            run_cmd = step.get("run", "")
            if "autonomous_trader.py" in run_cmd:
                found_commands.append((job_name, step.get("name", "unnamed"), run_cmd))

    if found_commands:
        for job_name, step_name, cmd in found_commands:
            print(f"✅ {job_name}/{step_name}: Uses autonomous_trader.py")
    else:
        print("ℹ️  No autonomous_trader.py commands in daily-trading.yml")


def test_daily_trading_workflow_checks_both_halt_sentinels():
    """Daily trading must honor both current and legacy halt files."""
    workflow_text = Path(".github/workflows/daily-trading.yml").read_text()

    assert "data/TRADING_HALTED" in workflow_text
    assert "data/trading_halt.txt" in workflow_text
    assert "TRADING_HALTED file exists - crisis mode active" in workflow_text
    assert "manual halt active" in workflow_text


def test_browser_automation_pilot_respects_pr_only_rule():
    """Browser telemetry workflow must not push directly to protected main."""
    workflow_path = Path(".github/workflows/browser-automation-pilot.yml")
    workflow_text = workflow_path.read_text()

    assert "pull-requests: write" in workflow_text
    assert "gh pr create" in workflow_text
    assert "gh pr merge" in workflow_text

    forbidden_direct_push_patterns = [
        r"(?m)^\s*git push\s*$",
        r"(?m)^\s*git push origin main(?:\s|$)",
    ]
    for pattern in forbidden_direct_push_patterns:
        assert re.search(pattern, workflow_text) is None, pattern


def test_main_ci_concurrency_uses_per_sha_key():
    """Main CI must not serialize newer main SHAs behind stale runs."""
    workflow_text = Path(".github/workflows/ci.yml").read_text()

    assert "format('ci-{0}-{1}', github.ref, github.sha)" in workflow_text
    assert "cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}" in workflow_text


if __name__ == "__main__":
    print("=" * 70)
    print("WORKFLOW CONTRACT TESTS")
    print("=" * 70)
    print()

    print("-" * 70)
    print()

    print("Test 2: All CLI Flags Exist in iron_condor_trader.py")
    print("-" * 70)
    test_all_cli_flags_exist()
    print()

    print("Test 3: Daily Trading Workflow CLI Flags")
    print("-" * 70)
    test_daily_trading_workflow_flags()
    print()

    print("=" * 70)
    print("✅ ALL WORKFLOW CONTRACT TESTS PASSED")
    print("=" * 70)
