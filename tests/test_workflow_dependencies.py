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
    assert all(package not in requirements for package in ("torch", "sentence-transformers", "lancedb", "chromadb"))

