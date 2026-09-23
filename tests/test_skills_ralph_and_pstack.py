"""Tests for Ralph Loop and pstack skills & execution harness."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.ralph_loop_runner import (
    StruggleDetector,
    append_decision_log,
    execute_ralph_cycle,
    main,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_SKILLS = [
    "ralph-loop",
    "pstack-how",
    "pstack-why",
    "pstack-architect",
    "pstack-arena",
    "pstack-interrogate",
    "verify-trading",
]


@pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
def test_skill_structure_and_frontmatter(skill_name: str) -> None:
    skill_dir = REPO_ROOT / "skills" / skill_name
    skill_file = skill_dir / "SKILL.md"

    assert skill_dir.is_dir(), f"Skill directory missing: {skill_dir}"
    assert skill_file.is_file(), f"SKILL.md missing: {skill_file}"

    content = skill_file.read_text(encoding="utf-8")
    assert content.startswith("---"), f"SKILL.md must start with YAML frontmatter: {skill_file}"

    parts = content.split("---", 2)
    assert len(parts) >= 3, f"SKILL.md missing frontmatter closing delimiter: {skill_file}"

    frontmatter_text = parts[1]
    parsed = yaml.safe_load(frontmatter_text)

    assert isinstance(parsed, dict), "Frontmatter must parse into a dictionary"
    assert parsed.get("name") == skill_name, f"Skill name in frontmatter must match '{skill_name}'"
    description = parsed.get("description")
    assert description and isinstance(description, str), "Skill must have non-empty description"
    assert len(description.strip()) > 20, "Skill description must be descriptive (>20 chars)"

    body = parts[2]
    assert "# " in body, "Skill body must have a top-level Markdown header"


def test_struggle_detector() -> None:
    detector = StruggleDetector(max_consecutive_errors=3)

    # Distinct errors: no struggle
    struggling, _ = detector.record_and_check("AssertionError: test 1 failed")
    assert not struggling
    struggling, _ = detector.record_and_check("KeyError: 'active_family'")
    assert not struggling

    # Repeated errors: triggers at 3
    struggling, _ = detector.record_and_check("ZeroDivisionError: width is 0")
    assert not struggling
    struggling, _ = detector.record_and_check("ZeroDivisionError: width is 0")
    assert not struggling
    struggling, reason = detector.record_and_check("ZeroDivisionError: width is 0")
    assert struggling
    assert "Identical failure detected 3 times" in reason


def test_decision_log_tsv(tmp_path: Path) -> None:
    log_file = tmp_path / "decision_log.tsv"

    append_decision_log(
        iteration=1,
        phase="MUTATE",
        hypothesis="Fix zero division",
        action="Added width > 0 guard",
        evidence="Tests passing",
        result="KEEP",
        log_path=log_file,
    )

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # Header + 1 row
    assert lines[0] == "timestamp\titeration\tphase\thypothesis\taction\tevidence\tresult"
    assert "Fix zero division" in lines[1]
    assert "KEEP" in lines[1]


def test_ralph_runner_success(tmp_path: Path) -> None:
    # A command that passes immediately satisfies the baseline
    success = execute_ralph_cycle(
        verify_cmd="python3 -c 'exit(0)'",
        max_iterations=3,
        cwd=tmp_path,
    )
    assert success is True


def test_ralph_runner_struggle_detection(tmp_path: Path) -> None:
    # A command that fails repeatedly with identical output triggers struggle detector
    success = execute_ralph_cycle(
        verify_cmd="python3 -c 'import sys; sys.stderr.write(\"repeat error\\n\"); exit(1)'",
        max_iterations=5,
        cwd=tmp_path,
    )
    assert success is False


def test_ralph_runner_auto_revert(tmp_path: Path) -> None:
    # Verify auto-revert path executes without error
    success = execute_ralph_cycle(
        verify_cmd="python3 -c 'import time; print(time.time()); exit(1)'",
        max_iterations=2,
        auto_revert=True,
        cwd=tmp_path,
    )
    assert success is False


def test_ralph_runner_main_check_only() -> None:
    code = main(["--verify-cmd", "python3 -c 'exit(0)'", "--check-only"])
    assert code == 0

    code_fail = main(["--verify-cmd", "python3 -c 'exit(2)'", "--check-only"])
    assert code_fail == 2


def test_ralph_runner_main_cli_success() -> None:
    code = main(["--verify-cmd", "python3 -c 'exit(0)'", "--max-iterations", "1"])
    assert code == 0


def test_ralph_runner_iteration_success(tmp_path: Path) -> None:
    flag = tmp_path / "flag"
    # Fails first time (creating flag), passes second time
    cmd = f"python3 -c 'import sys, pathlib; p = pathlib.Path(\"{flag}\"); sys.exit(0 if p.exists() else (p.touch() or 1))'"
    success = execute_ralph_cycle(
        verify_cmd=cmd,
        max_iterations=3,
        cwd=tmp_path,
    )
    assert success is True
