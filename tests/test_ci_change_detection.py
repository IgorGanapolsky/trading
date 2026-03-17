"""Tests for CI change classification."""

from __future__ import annotations

from src.utils.change_detection import classify_changed_paths


def test_docs_only_changes_skip_heavy_jobs() -> None:
    result = classify_changed_paths(
        [
            "docs/_reports/2026-03-17-dashboard-snapshot.md",
            "docs/llms.txt",
            "AGENTS.md",
        ]
    )

    assert result.docs_only is True
    assert result.run_lint_docs is True
    assert result.run_full_tests is False
    assert result.run_workflow_checks is False
    assert result.run_type_check is False


def test_workflow_only_changes_run_workflow_checks_without_full_test_suite() -> None:
    result = classify_changed_paths(
        [
            ".github/workflows/ci.yml",
            "tests/test_workflow_integrity.py",
            "scripts/agent_handoff_gate.py",
        ]
    )

    assert result.docs_only is False
    assert result.run_workflow_checks is True
    assert result.run_agent_handoff is True
    assert result.run_full_tests is False
    assert result.run_type_check is False


def test_trading_risk_change_runs_runtime_and_safety_jobs() -> None:
    result = classify_changed_paths(
        [
            "src/risk/trade_gateway.py",
            "tests/test_trade_gateway.py",
        ]
    )

    assert result.run_lint_python is True
    assert result.run_full_tests is True
    assert result.run_smoke is True
    assert result.run_integration is True
    assert result.run_core_test_suite is True
    assert result.run_safety_jobs is True
    assert result.run_type_check is True
    assert result.run_safe_wrapper_scan is True


def test_skill_change_triggers_skill_validation() -> None:
    result = classify_changed_paths(
        [
            ".codex/skills/autonomous-ops/SKILL.md",
        ]
    )

    assert result.run_skill_validation is True
    assert result.run_lint_docs is True
    assert result.docs_only is True
