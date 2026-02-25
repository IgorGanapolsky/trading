import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
RUNNER_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "ci" / "run_all_tests.sh"


def test_ci_workflow_uses_watchdog_runner_script():
    workflow = CI_WORKFLOW_PATH.read_text()
    assert "bash scripts/ci/run_all_tests.sh" in workflow
    assert "Upload test diagnostics" in workflow


def test_ci_workflow_collects_handoff_ab_metrics():
    workflow = CI_WORKFLOW_PATH.read_text()
    assert "scripts/collect_agent_handoff_ab_metrics.py collect" in workflow
    assert "artifacts/devloop/agent_handoff_ab_metrics_latest.json" in workflow
    assert "artifacts/devloop/agent_handoff_ab_metrics_history.jsonl" in workflow


def test_ci_runner_script_exists_and_has_valid_bash_syntax():
    assert RUNNER_SCRIPT_PATH.exists()
    result = subprocess.run(
        ["bash", "-n", str(RUNNER_SCRIPT_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_ci_runner_script_has_timeout_and_coverage_controls():
    content = RUNNER_SCRIPT_PATH.read_text()
    assert "resolve_timeout_cmd" in content
    assert "COV_FAIL_UNDER" in content
    assert "--timeout=" in content
