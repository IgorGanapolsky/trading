import re
from pathlib import Path

import yaml

WORKFLOWS = Path(".github/workflows")


def _text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_every_workflow_yaml_parses() -> None:
    for path in WORKFLOWS.glob("*.yml"):
        assert isinstance(yaml.safe_load(path.read_text(encoding="utf-8")), dict), path


def test_ci_jobs_have_timeouts() -> None:
    workflow = yaml.safe_load(_text("ci.yml"))
    assert [name for name, job in workflow["jobs"].items() if "timeout-minutes" not in job] == []


def test_actions_are_sha_pinned() -> None:
    action = re.compile(r"^\s*uses:\s*([^\s#]+)", re.MULTILINE)
    sha = re.compile(r"^[^@]+@[0-9a-f]{40}$")
    offenders = []
    for path in WORKFLOWS.glob("*.yml"):
        for use in action.findall(path.read_text()):
            if not use.startswith(("./", "docker://")) and not sha.match(use):
                offenders.append(f"{path.name}: {use}")
    assert offenders == []


def test_put_credit_entry_depends_on_clean_residual_inventory() -> None:
    text = _text("put-credit-validation.yml")
    assert "steps.residual_ic.outcome == 'success'" in text
    assert text.index("scripts/residual_ic_manager.py") < text.index("--execute-paper")


def test_event_router_handles_non_success_ci_conclusions() -> None:
    text = _text("event-router.yml")
    assert all(f"workflow_run.conclusion == '{item}'" in text for item in ("failure", "cancelled", "timed_out"))


def test_ci_stale_run_watchdog_can_cancel_stuck_runs() -> None:
    text = _text("ci-stale-run-watchdog.yml")
    assert all(item in text for item in ("listWorkflowRunsForRepo", "cancelWorkflowRun", '"queued", "in_progress"'))
