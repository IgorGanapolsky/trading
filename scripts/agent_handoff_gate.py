#!/usr/bin/env python3
"""Agent handoff gate for autonomous multi-agent branches.

This gate enforces three baseline controls before handoff/merge:
1) AGENTS contract is present and structurally complete.
2) Lint/format pass on changed Python files (or fallback paths).
3) Smart, targeted tests pass based on changed files.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_AGENTS_SECTIONS = (
    "# AGENTS",
    "## Core Directive",
    "## Interaction Style",
    "## Secrets / Keys",
)

DEFAULT_QUICK_TESTS = (
    "tests/test_workflow_integrity.py",
    "tests/test_workflow_dependencies.py",
    "tests/test_workflow_contracts.py",
)

DEFAULT_LINT_FALLBACK = ("src", "scripts", "tests")
MAX_OUTPUT_CHARS = 2500


@dataclass
class GateStepResult:
    name: str
    passed: bool
    details: list[str] = field(default_factory=list)
    command: str = ""
    return_code: int = 0
    duration_seconds: float = 0.0


@dataclass
class GateReport:
    mode: str
    base_ref: str
    changed_paths: list[str]
    selected_tests: list[str]
    steps: list[GateStepResult]
    generated_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    @property
    def passed(self) -> bool:
        return all(step.passed for step in self.steps)


def parse_changed_paths(raw_text: str) -> list[str]:
    """Parse git diff --name-only output into normalized paths."""
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


def _trim_output(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return f"{text[:MAX_OUTPUT_CHARS]} ...[trimmed]"


def _run_git_diff(repo_root: Path, base_ref: str, head_ref: str) -> tuple[int, str, str]:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            f"{base_ref}...{head_ref}",
        ],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def get_changed_paths(repo_root: Path, base_ref: str, head_ref: str = "HEAD") -> list[str]:
    """Get changed file paths against a base ref, with a shallow-clone fallback."""
    code, stdout, _stderr = _run_git_diff(repo_root=repo_root, base_ref=base_ref, head_ref=head_ref)
    if code == 0:
        return parse_changed_paths(stdout)

    fallback_base = f"{head_ref}~1"
    code, stdout, _stderr = _run_git_diff(
        repo_root=repo_root,
        base_ref=fallback_base,
        head_ref=head_ref,
    )
    if code == 0:
        return parse_changed_paths(stdout)

    return []


def _find_covering_agents_file(repo_root: Path, rel_path: str) -> Path | None:
    candidate = (repo_root / rel_path).resolve()
    if candidate.is_file():
        current = candidate.parent
    else:
        current = candidate

    repo_root_resolved = repo_root.resolve()
    while True:
        agents_path = current / "AGENTS.md"
        if agents_path.exists():
            return agents_path
        if current == repo_root_resolved:
            break
        if repo_root_resolved not in current.parents and current != repo_root_resolved:
            break
        current = current.parent
    return None


def validate_agents_contract(repo_root: Path, changed_paths: list[str]) -> GateStepResult:
    """Validate AGENTS structure and changed-file coverage."""
    details: list[str] = []
    passed = True

    root_agents = repo_root / "AGENTS.md"
    if not root_agents.exists():
        return GateStepResult(
            name="AGENTS contract",
            passed=False,
            details=["Missing root AGENTS.md"],
        )

    text = root_agents.read_text(encoding="utf-8", errors="replace")
    missing_sections = [section for section in REQUIRED_AGENTS_SECTIONS if section not in text]
    if missing_sections:
        passed = False
        details.append(f"Missing required sections: {', '.join(missing_sections)}")

    uncovered: list[str] = []
    for rel in changed_paths:
        agents_path = _find_covering_agents_file(repo_root=repo_root, rel_path=rel)
        if agents_path is None:
            uncovered.append(rel)
    if uncovered:
        passed = False
        details.append(f"No covering AGENTS.md for: {', '.join(uncovered)}")

    if not details:
        details.append("AGENTS contract and coverage checks passed")

    return GateStepResult(name="AGENTS contract", passed=passed, details=details)


def _iter_test_files(repo_root: Path) -> list[Path]:
    tests_dir = repo_root / "tests"
    if not tests_dir.exists():
        return []
    return sorted(tests_dir.rglob("test_*.py"))


def _to_rel_posix(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def select_targeted_tests(
    repo_root: Path, changed_paths: list[str], max_tests: int = 20
) -> list[str]:
    """Select test targets based on changed file stems and direct test edits."""
    all_tests = _iter_test_files(repo_root)
    if not all_tests:
        return []

    by_name: dict[str, list[str]] = {}
    for test_path in all_tests:
        rel = _to_rel_posix(test_path, repo_root)
        by_name.setdefault(test_path.name, []).append(rel)

    selected: list[str] = []
    seen: set[str] = set()

    def add(path_str: str) -> None:
        if path_str in seen:
            return
        seen.add(path_str)
        selected.append(path_str)

    for rel in changed_paths:
        changed = Path(rel)
        if changed.name.startswith("test_") and changed.suffix == ".py":
            candidate = changed.as_posix()
            if (repo_root / candidate).exists():
                add(candidate)

        if changed.suffix != ".py":
            continue

        stem = changed.stem
        for candidate in by_name.get(f"test_{stem}.py", []):
            add(candidate)

        if changed.parts and changed.parts[0] in {"src", "scripts"}:
            for test_rel in [f"tests/test_{stem}.py", f"tests/unit/test_{stem}.py"]:
                if (repo_root / test_rel).exists():
                    add(test_rel)

        if len(selected) >= max_tests:
            break

    return selected[:max_tests]


def render_markdown_report(report: GateReport) -> str:
    """Render a human-readable gate report."""
    status = "PASS" if report.passed else "FAIL"
    lines: list[str] = [
        "# Agent Handoff Gate Report",
        "",
        f"- Status: **{status}**",
        f"- Mode: `{report.mode}`",
        f"- Base Ref: `{report.base_ref}`",
        f"- Generated (UTC): `{report.generated_at_utc}`",
        "",
        "## Steps",
        "",
    ]

    for step in report.steps:
        icon = "✅" if step.passed else "❌"
        lines.append(f"- {icon} {step.name}")
        if step.command:
            lines.append(f"  - command: `{step.command}`")
        if step.return_code:
            lines.append(f"  - return code: `{step.return_code}`")
        for detail in step.details:
            lines.append(f"  - {detail}")

    lines.extend(["", "## Changed Files", ""])
    if report.changed_paths:
        lines.extend([f"- `{path}`" for path in report.changed_paths])
    else:
        lines.append("- none detected")

    lines.extend(["", "## Selected Tests", ""])
    if report.selected_tests:
        lines.extend([f"- `{path}`" for path in report.selected_tests])
    else:
        lines.append("- none selected")
    lines.append("")
    return "\n".join(lines)


def _run_command_step(
    name: str, command: list[str], repo_root: Path, dry_run: bool
) -> GateStepResult:
    command_display = " ".join(command)
    if dry_run:
        return GateStepResult(
            name=name,
            passed=True,
            details=["dry-run: command not executed"],
            command=command_display,
            return_code=0,
            duration_seconds=0.0,
        )

    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed = time.perf_counter() - started

    details: list[str] = []
    stdout_trimmed = _trim_output(result.stdout)
    stderr_trimmed = _trim_output(result.stderr)
    if stdout_trimmed:
        details.append(f"stdout: {stdout_trimmed}")
    if stderr_trimmed:
        details.append(f"stderr: {stderr_trimmed}")
    if not details:
        details.append("no command output")

    return GateStepResult(
        name=name,
        passed=result.returncode == 0,
        details=details,
        command=command_display,
        return_code=result.returncode,
        duration_seconds=elapsed,
    )


def _select_lint_targets(repo_root: Path, changed_paths: list[str], max_targets: int) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()

    for rel in changed_paths:
        if not rel.endswith(".py"):
            continue
        if not (repo_root / rel).exists():
            continue
        if rel in seen:
            continue
        seen.add(rel)
        targets.append(rel)
        if len(targets) >= max_targets:
            break

    if targets:
        return targets

    fallback = [path for path in DEFAULT_LINT_FALLBACK if (repo_root / path).exists()]
    return fallback


def _write_reports(report: GateReport, report_md_path: Path, report_json_path: Path) -> None:
    report_md_path.parent.mkdir(parents=True, exist_ok=True)
    report_json_path.parent.mkdir(parents=True, exist_ok=True)

    report_md_path.write_text(render_markdown_report(report), encoding="utf-8")
    report_json_path.write_text(
        json.dumps(
            {
                **asdict(report),
                "passed": report.passed,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def run_gate(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changed_paths = get_changed_paths(
        repo_root=repo_root,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
    )

    selected_tests = select_targeted_tests(
        repo_root=repo_root,
        changed_paths=changed_paths,
        max_tests=args.max_tests,
    )
    if args.mode == "quick" and not selected_tests:
        selected_tests = [test for test in DEFAULT_QUICK_TESTS if (repo_root / test).exists()]

    steps: list[GateStepResult] = [
        validate_agents_contract(repo_root=repo_root, changed_paths=changed_paths),
    ]

    lint_targets = _select_lint_targets(
        repo_root=repo_root,
        changed_paths=changed_paths,
        max_targets=args.max_lint_targets,
    )
    steps.append(
        _run_command_step(
            name="lint",
            command=["ruff", "check", *lint_targets],
            repo_root=repo_root,
            dry_run=args.dry_run,
        )
    )
    steps.append(
        _run_command_step(
            name="format",
            command=["ruff", "format", "--check", *lint_targets],
            repo_root=repo_root,
            dry_run=args.dry_run,
        )
    )

    test_command = ["python3", "-m", "pytest", "-q"]
    if args.mode == "full":
        test_command.extend(["tests"])
    elif selected_tests:
        test_command.extend(selected_tests)
    else:
        test_command.extend(["tests"])

    steps.append(
        _run_command_step(
            name="tests",
            command=test_command,
            repo_root=repo_root,
            dry_run=args.dry_run,
        )
    )

    report = GateReport(
        mode=args.mode,
        base_ref=args.base_ref,
        changed_paths=changed_paths,
        selected_tests=selected_tests,
        steps=steps,
    )

    report_md_path = Path(args.report_md).resolve()
    report_json_path = Path(args.report_json).resolve()
    _write_reports(report, report_md_path=report_md_path, report_json_path=report_json_path)

    print(f"Agent handoff gate status: {'PASS' if report.passed else 'FAIL'}")
    print(f"Markdown report: {report_md_path}")
    print(f"JSON report: {report_json_path}")
    return 0 if report.passed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run autonomous multi-agent handoff gate.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path.",
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Git base ref for changed-file detection.",
    )
    parser.add_argument(
        "--head-ref",
        default="HEAD",
        help="Git head ref for changed-file detection.",
    )
    parser.add_argument(
        "--mode",
        choices=("quick", "full"),
        default="quick",
        help="quick=targeted tests, full=full test suite.",
    )
    parser.add_argument(
        "--max-tests",
        type=int,
        default=20,
        help="Maximum number of targeted tests.",
    )
    parser.add_argument(
        "--max-lint-targets",
        type=int,
        default=80,
        help="Maximum number of changed Python files to lint directly.",
    )
    parser.add_argument(
        "--report-md",
        default="artifacts/devloop/agent_handoff_gate.md",
        help="Markdown report output path.",
    )
    parser.add_argument(
        "--report-json",
        default="artifacts/devloop/agent_handoff_gate.json",
        help="JSON report output path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan commands and generate reports without executing lint/tests.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run_gate(args)


if __name__ == "__main__":
    raise SystemExit(main())
