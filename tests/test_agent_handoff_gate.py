"""Tests for scripts.agent_handoff_gate."""

from __future__ import annotations

from pathlib import Path

from scripts.agent_handoff_gate import (
    GateReport,
    GateStepResult,
    parse_changed_paths,
    render_markdown_report,
    select_targeted_tests,
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
