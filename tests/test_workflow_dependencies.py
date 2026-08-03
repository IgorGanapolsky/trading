import re
from pathlib import Path

WORKFLOWS = Path(".github/workflows")
ALLOWED_REQUIREMENTS = {"requirements-minimal.txt", "requirements-ci.txt"}


def test_workflow_requirement_files_exist() -> None:
    assert all(Path(item).is_file() for item in ALLOWED_REQUIREMENTS)


def test_workflows_use_only_canonical_requirement_files() -> None:
    pattern = re.compile(r"pip\s+install(?:\s+-q)?\s+-r\s+([^\s]+)")
    for workflow in WORKFLOWS.glob("*.yml"):
        for requirement in pattern.findall(workflow.read_text()):
            assert requirement in ALLOWED_REQUIREMENTS, (workflow, requirement)


def test_ci_installs_lint_and_test_tools() -> None:
    requirements = Path("requirements-ci.txt").read_text()
    assert ".[dev]" in requirements


def test_minimal_dependencies_exclude_heavy_optional_rag_stack() -> None:
    requirements = Path("requirements-minimal.txt").read_text().lower()
    assert all(
        package not in requirements
        for package in ("torch", "sentence-transformers", "lancedb", "chromadb")
    )


def test_workflow_python_entrypoints_exist() -> None:
    pattern = re.compile(r"(?:python3?|python)\s+([A-Za-z0-9_./-]+\.py)\b")
    missing: list[str] = []
    for workflow in WORKFLOWS.glob("*.yml"):
        for relative in pattern.findall(workflow.read_text(encoding="utf-8")):
            if relative.startswith(("scripts/", "src/")) and not Path(relative).is_file():
                missing.append(f"{workflow.name}: {relative}")
    assert missing == []


def test_workflow_run_triggers_name_existing_workflows() -> None:
    name_pattern = re.compile(r"^name:\s*['\"]?(.+?)['\"]?\s*$", re.MULTILINE)
    trigger_pattern = re.compile(r"^\s*workflows:\s*\[([^]]+)]", re.MULTILINE)
    names = {
        match.group(1)
        for workflow in WORKFLOWS.glob("*.yml")
        if (match := name_pattern.search(workflow.read_text(encoding="utf-8")))
    }
    missing: list[str] = []
    for workflow in WORKFLOWS.glob("*.yml"):
        text = workflow.read_text(encoding="utf-8")
        for raw_list in trigger_pattern.findall(text):
            for raw_name in raw_list.split(","):
                name = raw_name.strip().strip("'\"")
                if name not in names:
                    missing.append(f"{workflow.name}: {name}")
    assert missing == []
