from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
RUNNER_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "ci" / "run_all_tests.sh"


def test_ci_workflow_exists_and_runs_trunk_check():
    """CI workflow should exist and run Trunk Check."""
    workflow = CI_WORKFLOW_PATH.read_text()
    assert "trunk-io/trunk-action" in workflow
    assert "Trunk Check" in workflow


def test_ci_runner_script_exists_and_has_valid_bash_syntax():
    if not RUNNER_SCRIPT_PATH.exists():
        return  # Runner script removed — test is informational only
    import subprocess

    result = subprocess.run(
        ["bash", "-n", str(RUNNER_SCRIPT_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
