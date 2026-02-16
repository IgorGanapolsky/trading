#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

FAILED_TEST_RE = re.compile(r"^FAILED\s+([^\s]+)")
ERROR_TEST_RE = re.compile(r"^ERROR\s+([^\s]+)")
PYTEST_ERR_FILE_RE = re.compile(r"^E\s+File \"([^\"]+)\"")
RUFF_FILE_RE = re.compile(r"^([A-Za-z0-9_./-]+\.py):\d+:\d+:")
RUFF_ARROW_FILE_RE = re.compile(r"^\s*-->\s+([A-Za-z0-9_./-]+\.py):\d+:\d+")
TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b", re.IGNORECASE)
CHECKBOX_RE = re.compile(r"^- \[( |x)\] (.+)$")


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_failed_tests(text: str) -> list[str]:
    failed: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        m = FAILED_TEST_RE.match(stripped)
        if m:
            failed.append(m.group(1))
            continue
        m = ERROR_TEST_RE.match(stripped)
        if m:
            failed.append(m.group(1))
    return failed


def parse_problem_files(pytest_text: str, ruff_text: str) -> Counter[str]:
    files: Counter[str] = Counter()

    for line in pytest_text.splitlines():
        m = PYTEST_ERR_FILE_RE.match(line.strip())
        if m:
            files[m.group(1)] += 1

    for line in ruff_text.splitlines():
        stripped = line.strip()
        m = RUFF_FILE_RE.match(stripped)
        if m:
            files[m.group(1)] += 1
            continue
        m = RUFF_ARROW_FILE_RE.match(stripped)
        if m:
            files[m.group(1)] += 1

    return files


def parse_existing_checkboxes(out_path: Path) -> dict[str, bool]:
    statuses: dict[str, bool] = {}
    if not out_path.exists():
        return statuses
    for line in out_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = CHECKBOX_RE.match(line.strip())
        if not m:
            continue
        checked = m.group(1) == "x"
        task = m.group(2).strip()
        statuses[task] = checked
    return statuses


def scan_todos(repo_root: Path, max_items: int) -> list[str]:
    items: list[str] = []
    allowed_roots = {
        repo_root / "src",
        repo_root / "scripts",
        repo_root / "tests",
        repo_root / "docs",
        repo_root / ".github",
        repo_root / "config",
    }
    for path in repo_root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if path.suffix.lower() not in {".py", ".md", ".yml", ".yaml", ".sh", ".js", ".ts"}:
            continue
        if ".git" in path.parts:
            continue
        if str(path).startswith(str(repo_root / "artifacts")):
            continue
        if str(path).startswith(str(repo_root / ".claude")):
            continue
        if str(path).startswith(str(repo_root / "rag_knowledge")):
            continue
        if not any(str(path).startswith(str(root)) for root in allowed_roots):
            continue

        text = read_text(path)
        for i, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            if TODO_RE.search(stripped) and (
                stripped.startswith("#")
                or stripped.startswith("//")
                or stripped.startswith("-")
                or "TODO:" in stripped
                or "FIXME:" in stripped
            ):
                rel_path = path.relative_to(repo_root)
                items.append(f"{rel_path}:{i} {line.strip()}")
                if len(items) >= max_items:
                    return items
    return items


def write_markdown(
    out_path: Path,
    *,
    failed_tests: list[str],
    problem_files: Counter[str],
    todo_items: list[str],
    lint_ok: bool,
    test_ok: bool,
) -> None:
    existing_status = parse_existing_checkboxes(out_path)

    layer1_tasks: list[str] = []
    if not lint_ok:
        layer1_tasks.append("Fix lint/type/static issues blocking green checks.")
    for t in failed_tests[:50]:
        layer1_tasks.append(f"Fix failing test: `{t}`")

    prev_open = {task for task, checked in existing_status.items() if not checked}
    current_set = set(layer1_tasks)
    completed_now = sorted(prev_open - current_set)

    lines: list[str] = []
    lines.append("# Layered Task Backlog")
    lines.append("")
    lines.append("## Gate Status")
    lines.append(f"- Lint: {'PASS' if lint_ok else 'FAIL'}")
    lines.append(f"- Tests: {'PASS' if test_ok else 'FAIL'}")
    lines.append("")

    lines.append("## Layer 1: Red Build/Test Failures")
    if not layer1_tasks:
        lines.append("- [x] None")
    else:
        for task in layer1_tasks:
            lines.append(f"- [ ] {task}")
    lines.append("")

    lines.append("## Completed Since Last Iteration")
    if not completed_now:
        lines.append("- [x] None")
    else:
        for task in completed_now:
            lines.append(f"- [x] {task}")
    lines.append("")

    lines.append("## Layer 2: High-Impact Files")
    if not problem_files:
        lines.append("- None")
    else:
        for f, count in problem_files.most_common(25):
            lines.append(f"- `{f}` ({count} signal(s))")
    lines.append("")

    lines.append("## Layer 3: Deferred Cleanup")
    if not todo_items:
        lines.append("- None")
    else:
        for item in todo_items:
            lines.append(f"- {item}")
    lines.append("")

    lines.append("## Next Loop Protocol")
    lines.append("1. Pick one unchecked Layer 1 item and implement a minimal fix.")
    lines.append("2. Re-run lint/tests.")
    lines.append("3. Regenerate this file; resolved Layer 1 items auto-move to checked.")
    lines.append("4. Repeat until Layer 1 is fully checked.")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate layered TDD backlog from lint/test output."
    )
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--ruff-log", required=True, help="Path to ruff output log")
    parser.add_argument("--pytest-log", required=True, help="Path to pytest output log")
    parser.add_argument("--out", required=True, help="Output markdown file")
    parser.add_argument("--max-todos", type=int, default=40, help="Max TODO-like lines to include")
    parser.add_argument("--lint-exit", type=int, default=0, help="Lint command exit code")
    parser.add_argument("--test-exit", type=int, default=0, help="Pytest command exit code")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    ruff_text = read_text(Path(args.ruff_log))
    pytest_text = read_text(Path(args.pytest_log))

    lint_ok = args.lint_exit == 0
    test_ok = args.test_exit == 0

    failed_tests = parse_failed_tests(pytest_text)
    problem_files = parse_problem_files(pytest_text, ruff_text)
    todo_items = scan_todos(repo_root, max_items=args.max_todos)

    write_markdown(
        Path(args.out),
        failed_tests=failed_tests,
        problem_files=problem_files,
        todo_items=todo_items,
        lint_ok=lint_ok,
        test_ok=test_ok,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
