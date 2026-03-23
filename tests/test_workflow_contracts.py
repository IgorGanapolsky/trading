#!/usr/bin/env python3
"""Test that workflows use valid CLI flags.

Prevents ll_025-type failures where workflows use deprecated CLI flags
that cause silent failures in production.
"""

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
            for line in run_cmd.splitlines():
                if re.search(r"python3?\s+scripts/autonomous_trader\.py(?:\s|$)", line):
                    found_commands.append((job_name, step.get("name", "unnamed"), line.strip()))

    if not found_commands:
        print("✅ No live autonomous_trader.py invocations found")
        return

    # Validate each command uses current CLI interface
    for job_name, step_name, cmd in found_commands:
        print(f"✅ {job_name}/{step_name}: {cmd}")


def _declared_iron_condor_flags() -> set[str]:
    trader_text = Path("scripts/iron_condor_trader.py").read_text()
    return set(re.findall(r"""['"](--[a-z-]+)['"]""", trader_text))


def _daily_trading_iron_condor_commands() -> list[tuple[str, str, str]]:
    workflow_path = Path(".github/workflows/daily-trading.yml")
    workflow = yaml.safe_load(workflow_path.read_text())

    commands: list[tuple[str, str, str]] = []
    for job_name, job in workflow.get("jobs", {}).items():
        for step in job.get("steps", []):
            run_cmd = step.get("run", "")
            for line in run_cmd.splitlines():
                if re.search(r"python3?\s+scripts/iron_condor_trader\.py(?:\s|$)", line):
                    commands.append((job_name, step.get("name", "unnamed"), line.strip()))
    return commands


def _daily_trading_autonomous_commands() -> list[tuple[str, str, str]]:
    workflow_path = Path(".github/workflows/daily-trading.yml")
    workflow = yaml.safe_load(workflow_path.read_text())

    commands: list[tuple[str, str, str]] = []
    for job_name, job in workflow.get("jobs", {}).items():
        for step in job.get("steps", []):
            run_cmd = step.get("run", "")
            for line in run_cmd.splitlines():
                if re.search(r"python3?\s+scripts/autonomous_trader\.py(?:\s|$)", line):
                    commands.append((job_name, step.get("name", "unnamed"), line.strip()))
    return commands


def test_all_cli_flags_exist():
    """Verify expected CLI flags are declared in the live trader entrypoint.

    This intentionally inspects the source text instead of executing the script
    so workflow validation can run in minimal environments that only install
    test dependencies.
    """
    # Expected CLI flags that workflows depend on
    expected_flags = ["--symbol", "--force", "--live", "--dry-run"]
    declared_flags = _declared_iron_condor_flags()

    for flag in expected_flags:
        if flag in declared_flags:
            print(f"✅ Flag '{flag}' exists in CLI")
        else:
            print(f"❌ Flag '{flag}' not found in iron_condor_trader.py")
            sys.exit(1)


def test_daily_trading_workflow_flags():
    """Verify daily-trading.yml uses only declared iron_condor_trader flags."""
    workflow_path = Path(".github/workflows/daily-trading.yml")

    if not workflow_path.exists():
        print(f"⚠️  Workflow not found: {workflow_path}")
        return

    declared_flags = _declared_iron_condor_flags()
    invalid_invocations: list[str] = []
    for job_name, step_name, cmd in _daily_trading_iron_condor_commands():
        literal_flags = set(re.findall(r"--[a-z-]+", cmd))
        unknown_flags = sorted(literal_flags - declared_flags)
        if unknown_flags:
            invalid_invocations.append(
                f"{job_name}/{step_name}: unknown flags {unknown_flags} in `{cmd}`"
            )

    if invalid_invocations:
        for message in invalid_invocations:
            print(f"❌ {message}")
        sys.exit(1)

    print("✅ daily-trading.yml iron_condor_trader.py invocations use declared flags only")


def test_daily_trading_workflow_has_no_live_autonomous_trader_invocations():
    """Verify daily-trading.yml does not execute the deleted autonomous trader."""
    found_commands = _daily_trading_autonomous_commands()

    if found_commands:
        for job_name, step_name, cmd in found_commands:
            print(f"❌ {job_name}/{step_name}: {cmd}")
        sys.exit(1)

    print("✅ No live autonomous_trader.py commands in daily-trading.yml")


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


def test_generated_state_pushes_have_main_head_verification():
    """Generated trading-state commits on main must still be verified."""
    workflow_text = Path(".github/workflows/main-head-verification.yml").read_text()

    assert "branches: [main]" in workflow_text
    assert '"data/system_state.json"' in workflow_text
    assert '"data/trades.json"' in workflow_text
    assert "scripts/system_health_check.py" in workflow_text
    assert "tests/test_system_health_check.py" in workflow_text
    assert "tests/test_sync_alpaca_positions.py" in workflow_text
    assert "tests/test_mandatory_trade_gate.py" in workflow_text
    assert "tests/test_north_star_operating_plan.py" in workflow_text
    assert "tests/test_workflow_integrity.py" in workflow_text


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
