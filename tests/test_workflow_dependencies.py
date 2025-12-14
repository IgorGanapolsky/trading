#!/usr/bin/env python3
"""
Test Workflow Dependencies - Prevent requirements.txt disasters

This test catches issues like:
- Dashboard workflow trying to install GPU packages on GitHub Actions
- Workflows using wrong requirements file
- Missing dependencies in minimal requirements files

Prevention for: LL-020 (Dashboard failed due to GPU packages in requirements.txt)
"""

import re
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent
WORKFLOWS_DIR = PROJECT_ROOT / ".github" / "workflows"

# Packages that should NEVER be in requirements files used by GitHub Actions
# (unless the workflow explicitly needs GPU support)
GPU_PACKAGES = [
    "nvidia-",
    "torch",
    "triton",
    "cuda",
]

# Lightweight workflows that should use minimal requirements
LIGHTWEIGHT_WORKFLOWS = [
    "dashboard-auto-update.yml",
    "check-health.yml",
    "update-wiki.yml",
]


def get_workflow_requirements(workflow_path: Path) -> list[str]:
    """Extract requirements files referenced by a workflow."""
    with open(workflow_path) as f:
        content = yaml.safe_load(f)

    requirements = []
    yaml_str = yaml.dump(content)

    # Find pip install -r commands
    matches = re.findall(r"pip install.*?-r\s+(\S+)", yaml_str)
    requirements.extend(matches)

    return requirements


def test_workflow_files_exist():
    """Ensure workflow directory exists and has YAML files."""
    assert WORKFLOWS_DIR.exists(), f"Workflows directory not found: {WORKFLOWS_DIR}"
    workflows = list(WORKFLOWS_DIR.glob("*.yml"))
    assert len(workflows) > 0, "No workflow YAML files found"


def test_lightweight_workflows_use_minimal_requirements():
    """
    Lightweight workflows should NOT use full requirements.txt

    This prevents the dashboard failure where GPU packages couldn't install.
    """
    for workflow_name in LIGHTWEIGHT_WORKFLOWS:
        workflow_path = WORKFLOWS_DIR / workflow_name
        if not workflow_path.exists():
            continue

        requirements = get_workflow_requirements(workflow_path)

        for req in requirements:
            # Should NOT use the main requirements.txt
            assert req != "requirements.txt", (
                f"Workflow {workflow_name} uses full requirements.txt! "
                f"This will fail on GitHub Actions due to GPU packages. "
                f"Use requirements-dashboard.txt or requirements-minimal.txt instead. "
                f"(Lesson: LL-020)"
            )


def test_minimal_requirements_has_no_gpu_packages():
    """Ensure minimal requirements files don't have GPU packages."""
    minimal_files = [
        "requirements-dashboard.txt",
        "requirements-minimal.txt",
        "requirements-ci.txt",
    ]

    for req_file in minimal_files:
        req_path = PROJECT_ROOT / req_file
        if not req_path.exists():
            continue

        with open(req_path) as f:
            content = f.read().lower()

        for gpu_pkg in GPU_PACKAGES:
            assert gpu_pkg.lower() not in content, (
                f"{req_file} contains GPU package '{gpu_pkg}'. "
                f"GPU packages fail on GitHub Actions runners. "
                f"Remove them for CI-compatible requirements."
            )


def test_dashboard_workflow_uses_correct_requirements():
    """Specific test for dashboard workflow requirements."""
    dashboard_workflow = WORKFLOWS_DIR / "dashboard-auto-update.yml"

    if not dashboard_workflow.exists():
        pytest.skip("Dashboard workflow not found")

    with open(dashboard_workflow) as f:
        content = f.read()

    # Should use requirements-dashboard.txt
    assert "requirements-dashboard.txt" in content, (
        "Dashboard workflow should use requirements-dashboard.txt, not requirements.txt. "
        "The full requirements.txt has GPU packages that fail on GitHub Actions."
    )

    # Should NOT use full requirements.txt
    # Use regex to find 'pip install -r requirements.txt' (not requirements-*.txt)
    full_req_pattern = r"pip install.*-r\s+requirements\.txt(?!\-)"
    matches = re.findall(full_req_pattern, content)
    assert len(matches) == 0, (
        f"Dashboard workflow uses full requirements.txt: {matches}. "
        f"This will fail due to GPU packages."
    )


def test_requirements_dashboard_has_essential_packages():
    """Ensure dashboard requirements has necessary packages."""
    req_path = PROJECT_ROOT / "requirements-dashboard.txt"

    if not req_path.exists():
        pytest.fail(
            "requirements-dashboard.txt not found! Create it with: alpaca-py, python-dotenv, numpy"
        )

    with open(req_path) as f:
        content = f.read().lower()

    essential = ["alpaca-py", "python-dotenv", "numpy"]
    missing = [pkg for pkg in essential if pkg not in content]

    assert len(missing) == 0, (
        f"requirements-dashboard.txt missing essential packages: {missing}. "
        f"Dashboard needs these for fetching account data and calculations."
    )


def test_all_workflows_have_valid_yaml():
    """Ensure all workflow files have valid YAML syntax."""
    for workflow_path in WORKFLOWS_DIR.glob("*.yml"):
        with open(workflow_path) as f:
            try:
                yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {workflow_path.name}: {e}")


def test_workflow_python_versions():
    """Check that workflows use compatible Python versions."""
    for workflow_path in WORKFLOWS_DIR.glob("*.yml"):
        with open(workflow_path) as f:
            content = yaml.safe_load(f)

        yaml_str = yaml.dump(content)

        # Check for Python version specification
        python_versions = re.findall(r"python-version:\s*['\"]?(\d+\.\d+)", yaml_str)

        for version in python_versions:
            major, minor = map(int, version.split("."))
            assert major == 3 and minor >= 9, (
                f"{workflow_path.name} uses Python {version}. Minimum supported is 3.9."
            )
            assert major == 3 and minor < 14, (
                f"{workflow_path.name} uses Python {version}. "
                f"Python 3.14+ has limited wheel availability."
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
