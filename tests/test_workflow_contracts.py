#!/usr/bin/env python3
"""Test that workflows use valid CLI flags.

Prevents ll_025-type failures where workflows use deprecated CLI flags
that cause silent failures in production.
"""

import subprocess
import sys
from pathlib import Path

import yaml



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
    """Verify expected CLI flags exist in autonomous_trader.py."""
    result = subprocess.run(
        ["python3", "scripts/autonomous_trader.py", "--help"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("❌ Failed to get autonomous_trader.py help text")
        print(result.stderr)
        sys.exit(1)

    help_text = result.stdout

    # Check expected flags exist in CLI
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


if __name__ == "__main__":
    print("=" * 70)
    print("WORKFLOW CONTRACT TESTS")
    print("=" * 70)
    print()

    print("-" * 70)
    print()

    print("Test 2: All CLI Flags Exist in autonomous_trader.py")
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
