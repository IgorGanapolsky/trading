"""Tests for scripts.agent_handoff_gate."""

from __future__ import annotations

import json
from pathlib import Path

from src.safety.trading_policy_drift import canonical_policy_values
from scripts.agent_handoff_gate import (
    GateReport,
    GateStepResult,
    parse_changed_paths,
    render_markdown_report,
    select_targeted_tests,
    validate_delegation_contract_step,
    validate_trading_policy_drift,
    validate_agents_contract,
)


def test_parse_changed_paths_ignores_empty_lines() -> None:
    raw = "\n".join(
        [
            "src/orchestrator/main.py",
            "",
            "tests/test_orchestrator_gates.py",
            "  ",
        ]
    )
    parsed = parse_changed_paths(raw)
    assert parsed == ["src/orchestrator/main.py", "tests/test_orchestrator_gates.py"]


def test_validate_agents_contract_fails_when_required_section_missing(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "\n".join(
            [
                "# AGENTS",
                "## Core Directive",
                "## Interaction Style",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    changed = ["src/example.py"]

    result = validate_agents_contract(repo_root=tmp_path, changed_paths=changed)

    assert result.passed is False
    assert any("Secrets / Keys" in detail for detail in result.details)


def test_select_targeted_tests_matches_by_stem(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_example.py").write_text("def test_ok():\n    assert True\n")
    (tmp_path / "tests" / "test_unrelated.py").write_text("def test_noop():\n    assert True\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "example.py").write_text("VALUE = 1\n")

    selected = select_targeted_tests(
        repo_root=tmp_path,
        changed_paths=["src/example.py"],
        max_tests=10,
    )

    assert selected == ["tests/test_example.py"]


def test_render_markdown_report_includes_failed_steps() -> None:
    report = GateReport(
        mode="quick",
        base_ref="origin/main",
        changed_paths=["scripts/agent_handoff_gate.py"],
        selected_tests=["tests/test_agent_handoff_gate.py"],
        steps=[
            GateStepResult(name="AGENTS contract", passed=True, details=["ok"]),
            GateStepResult(name="lint", passed=False, details=["ruff failed"]),
        ],
    )

    markdown = render_markdown_report(report)

    assert "# Agent Handoff Gate Report" in markdown
    assert "❌ lint" in markdown
    assert "scripts/agent_handoff_gate.py" in markdown


def test_validate_delegation_contract_step_fails_on_missing_fields() -> None:
    result = validate_delegation_contract_step(
        contract={"assignee": "codex"},
        changed_paths=["src/orchestrator/main.py"],
    )
    assert result.passed is False
    assert any("missing required field" in detail for detail in result.details)


def _write_policy_docs(repo_root: Path, max_positions: int | None = None) -> None:
    (repo_root / ".claude" / "rules").mkdir(parents=True)
    canonical = canonical_policy_values()
    resolved_max_positions = (
        int(canonical["MAX_POSITIONS"]) if max_positions is None else max_positions
    )
    content = "\n".join(
        [
            (f"IRON_CONDOR_STOP_LOSS_MULTIPLIER = {canonical['IRON_CONDOR_STOP_LOSS_MULTIPLIER']}"),
            f"NORTH_STAR_MONTHLY_AFTER_TAX = {canonical['NORTH_STAR_MONTHLY_AFTER_TAX']}",
            f"MAX_POSITIONS = {resolved_max_positions}",
        ]
    )
    for rel in (
        ".claude/CLAUDE.md",
        ".claude/rules/risk-management.md",
        ".claude/rules/trading.md",
    ):
        (repo_root / rel).write_text(content, encoding="utf-8")


def test_validate_trading_policy_drift_passes_and_writes_metrics(tmp_path: Path) -> None:
    _write_policy_docs(tmp_path)
    metrics_path = tmp_path / "artifacts" / "policy_metrics.json"

    result = validate_trading_policy_drift(
        repo_root=tmp_path,
        policy_doc_paths=[
            ".claude/CLAUDE.md",
            ".claude/rules/risk-management.md",
            ".claude/rules/trading.md",
        ],
        policy_ab_json_path=metrics_path,
    )

    assert result.passed is True
    assert metrics_path.exists()
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert payload["drift_detected"] is False
    assert payload["checks_failed"] == 0


def test_validate_trading_policy_drift_fails_on_mismatch(tmp_path: Path) -> None:
    _write_policy_docs(tmp_path, max_positions=5)
    metrics_path = tmp_path / "artifacts" / "policy_metrics.json"

    result = validate_trading_policy_drift(
        repo_root=tmp_path,
        policy_doc_paths=[
            ".claude/CLAUDE.md",
            ".claude/rules/risk-management.md",
            ".claude/rules/trading.md",
        ],
        policy_ab_json_path=metrics_path,
    )

    assert result.passed is False
    assert any("MAX_POSITIONS" in detail for detail in result.details)
