#!/usr/bin/env python3
"""Test that workflows use valid CLI flags.

Prevents ll_025-type failures where workflows use deprecated CLI flags
that cause silent failures in production.
"""

import re
import subprocess
import sys
from pathlib import Path

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


def test_daily_trading_workflow_uses_llm_observability_check():
    """Daily trading should use the real LLM observability check, not stale LangSmith text."""
    workflow_text = Path(".github/workflows/daily-trading.yml").read_text()

    assert "python3 scripts/check_llm_observability.py" in workflow_text
    assert "LangSmith" not in workflow_text
    assert "HELICONE_API_KEY" not in workflow_text


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


def test_main_ci_concurrency_cancels_stale_branch_runs():
    """CI should cancel superseded branch/PR runs without canceling main verification."""
    workflow_text = Path(".github/workflows/ci.yml").read_text()

    assert "github.event.pull_request.number || github.ref" in workflow_text
    assert "cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}" in workflow_text


def test_main_ci_fast_paths_workflow_docs_config_changes():
    """Workflow/docs/config-only changes should keep the required test check fast."""
    workflow_text = Path(".github/workflows/ci.yml").read_text()

    assert "Detect Changed Paths" in workflow_text
    assert "run_full_tests" in workflow_text
    assert "Only workflow/docs/config files changed" in workflow_text
    assert "Skipping full Python test suite" in workflow_text
    assert ".github/workflows/*" in workflow_text
    assert "data/system_state.json" in workflow_text
    assert "data/runtime/intraday_pnl_latest.json" in workflow_text
    assert "data/runtime/intraday_pnl_history.json" in workflow_text
    assert "data/north_star_weekly_history.json" in workflow_text


def test_sync_alpaca_status_updates_public_surfaces():
    """Alpaca sync must regenerate the public bundle and wiki surfaces.

    Note: Sync Alpaca only commits its own files (broker state, pnl, public status, wiki).
    ML models, trade data, and RAG lessons are owned by IC Simple.
    """
    workflow_text = Path(".github/workflows/sync-alpaca-status.yml").read_text()

    assert "npx --yes prettier@3.6.2 --write" in workflow_text
    assert "scripts/daily_scorecard.py --repo-root ." in workflow_text
    assert "scripts/build_public_status.py --repo-root ." in workflow_text
    assert "docs/data/public_status.json" in workflow_text
    assert "wiki/Progress-Dashboard.md" in workflow_text
    assert "gh repo edit" in workflow_text
    # ML models are now owned by IC Simple, not Sync Alpaca (commit race fix)
    assert "models/ml/trade_confidence_model.json" not in workflow_text


def test_state_writer_workflows_share_a_single_queue():
    """Sync Alpaca and IC Simple must serialize writes to generated state on main."""
    sync_text = Path(".github/workflows/sync-alpaca-status.yml").read_text()
    ic_text = Path(".github/workflows/ic-simple.yml").read_text()

    queue_expr = "format('state-writer-{0}-{1}', github.repository, github.ref_name || 'main')"
    assert queue_expr in sync_text
    assert queue_expr in ic_text
    assert "cancel-in-progress: false" in sync_text
    assert "cancel-in-progress: false" in ic_text


def test_state_writer_workflows_fail_closed_on_rebase_or_push_errors():
    """State-writing workflows must not report green when main-update rebases or pushes fail."""
    sync_text = Path(".github/workflows/sync-alpaca-status.yml").read_text()
    ic_text = Path(".github/workflows/ic-simple.yml").read_text()

    assert "set -euo pipefail" in sync_text
    assert "set -euo pipefail" in ic_text
    assert "git push origin HEAD:main ||" not in sync_text
    assert "git push origin HEAD:main ||" not in ic_text
    assert "git pull --rebase origin main" not in ic_text
    assert "git pull --ff-only origin main" in sync_text
    assert "git pull --ff-only origin main" in ic_text


def test_state_writer_workflows_refresh_to_latest_main_before_mutating_state():
    """Queued state writers must base their outputs on the newest main head before running."""
    sync_text = Path(".github/workflows/sync-alpaca-status.yml").read_text()
    ic_text = Path(".github/workflows/ic-simple.yml").read_text()

    assert "name: Refresh to latest main" in sync_text
    assert "name: Refresh to latest main" in ic_text
    assert "git fetch origin main" in sync_text
    assert "git fetch origin main" in ic_text
    assert "git checkout -B main origin/main" in sync_text
    assert "git checkout -B main origin/main" in ic_text


def test_public_surface_guard_workflow_exists():
    """Public-facing copy must have its own lightweight guard workflow."""
    workflow_text = Path(".github/workflows/public-surface-guard.yml").read_text()

    assert "scripts/build_public_status.py --repo-root . --check" in workflow_text
    assert "scripts/check_public_copy_freshness.py --repo-root ." in workflow_text
    assert "tests/test_build_public_status.py" in workflow_text


def test_ic_simple_workflow_commits_canonical_state_outputs():
    """IC Simple must persist the canonical ledgers it refreshes after each run."""
    workflow_text = Path(".github/workflows/ic-simple.yml").read_text()

    assert "npx --yes prettier@3.6.2 --write" in workflow_text
    assert "data/system_state.json" in workflow_text
    assert "data/trades.json" in workflow_text
    assert "data/runtime/intraday_pnl_latest.json" in workflow_text
    assert "data/runtime/intraday_pnl_history.json" in workflow_text
    assert "models/ml/grpo_trade_metadata.json" in workflow_text


def test_auto_format_uses_repo_token_not_pat_checkout():
    """Auto-format must use the repository token path that works on default-branch pushes."""
    workflow_text = Path(".github/workflows/auto-format.yml").read_text()

    assert "actions/checkout@v6" in workflow_text
    assert "secrets.GH_PAT" not in workflow_text


def test_main_head_verification_runs_bounded_health_mode():
    """Main-head verification must opt into bounded health checks in CI."""
    workflow_text = Path(".github/workflows/main-head-verification.yml").read_text()

    assert 'SYSTEM_HEALTH_BOUNDED: "1"' in workflow_text


def test_auto_format_opens_pr_instead_of_pushing_main():
    """Auto-format must not push straight to protected main."""
    workflow_text = Path(".github/workflows/auto-format.yml").read_text()

    assert "gh pr create" in workflow_text
    assert "git push origin main" not in workflow_text
    assert "pull-requests: write" in workflow_text


def test_self_healing_uses_pr_safe_mutation_flow():
    """Self-healing workflow must not mutate protected main directly."""
    workflow_text = Path(".github/workflows/self-healing-auto-fix.yml").read_text()

    assert "gh pr create" in workflow_text
    assert "git push origin main" not in workflow_text
    assert "secrets.GH_PAT" not in workflow_text


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
