from pathlib import Path

WORKFLOWS = Path(".github/workflows")
PUT_CREDIT = WORKFLOWS / "put-credit-validation.yml"


def _read(name: str) -> str:
    return (WORKFLOWS / name).read_text()


def test_put_credit_workflow_uses_current_entry_and_residual_exit_paths() -> None:
    text = PUT_CREDIT.read_text()
    assert "scripts/spy_put_credit.py" in text and "scripts/residual_ic_manager.py" in text
    assert "scripts/ic_simple.py" not in text and "scripts/iron_condor_trader.py" not in text


def test_put_credit_workflow_is_paper_only_and_fail_closed() -> None:
    text = PUT_CREDIT.read_text()
    assert "--execute-paper" in text and "--live" not in text
    assert "github.event_name == 'workflow_dispatch' && 'true' || 'false'" in text
    assert "steps.residual_ic.outcome == 'success'" in text
    assert "steps.residual_ic.outcome == 'failure'" in text


def test_state_writers_serialize_and_fail_on_push_errors() -> None:
    queue = "format('state-writer-{0}-{1}', github.repository, github.ref_name || 'main')"
    for name in ("put-credit-validation.yml", "sync-alpaca-status.yml", "pre-market-sync.yml"):
        text = _read(name)
        assert queue in text or "state-writer-{0}-{1}" in text
        assert "cancel-in-progress: false" in text and "set -euo pipefail" in text
        assert (
            "git pull --ff-only origin main" in text and "git push origin HEAD:main ||" not in text
        )


def test_ci_cancels_superseded_branch_runs_only() -> None:
    text = _read("ci.yml")
    assert "github.event.pull_request.number || github.ref" in text
    assert "cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}" in text


def test_removed_mutating_automation_stays_removed() -> None:
    removed = {
        "auto-format.yml",
        "browser-automation-pilot.yml",
        "claude-agent-utility.yml",
        "daily-trading.yml",
        "deploy-rag-webhook.yml.disabled",
        "event-router.yml",
        "iron-condor-guardian.yml",
        "notify-alert.yml",
        "notify-failure.yml",
        "pre-market-scan.yml",
        "self-healing-auto-fix.yml",
        "webhook-health-check.yml",
        "webhook-integration-test.yml",
    }
    assert all(not (WORKFLOWS / name).exists() for name in removed)
