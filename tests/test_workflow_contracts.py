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
    assert "AGENT-604" in text
    assert "LL-593" in text


STATE_WRITERS = (
    "put-credit-validation.yml",
    "sync-alpaca-status.yml",
    "pre-market-sync.yml",
    "arxiv-paper-ingestion.yml",
)


def test_state_writers_land_via_pr_not_protected_main() -> None:
    queue = "format('state-writer-{0}-{1}', github.repository, github.ref_name || 'main')"
    helper = Path("scripts/land_github_actions_pr.sh")
    assert helper.is_file()
    helper_text = helper.read_text()
    assert "set -euo pipefail" in helper_text
    assert "chore/auto-" in helper_text
    assert "git push origin main" not in helper_text
    assert "git push origin HEAD:main" not in helper_text
    assert "HEAD:refs/heads/main" not in helper_text
    for name in STATE_WRITERS:
        text = _read(name)
        assert "scripts/land_github_actions_pr.sh" in text, name
        assert "git push origin main" not in text, name
        assert "git push origin HEAD:main" not in text, name
        assert "HEAD:refs/heads/main" not in text, name
        assert "pull-requests: write" in text, name
        assert "set -euo pipefail" in text, name
        if name != "arxiv-paper-ingestion.yml":
            assert queue in text or "state-writer-{0}-{1}" in text, name
            assert "cancel-in-progress: false" in text, name


def test_run_all_tests_core_timeout_outlives_gha_124() -> None:
    runner = Path("scripts/ci/run_all_tests.sh").read_text()
    ci = _read("ci.yml")
    assert 'CORE_TIMEOUT_MINUTES="${CORE_TIMEOUT_MINUTES:-36}"' in runner
    assert "timeout-minutes: 55" in ci


def test_no_workflow_pushes_protected_main() -> None:
    for path in WORKFLOWS.glob("*.yml"):
        text = path.read_text()
        assert "git push origin main" not in text, path.name
        assert "git push origin HEAD:main" not in text, path.name
        assert "HEAD:refs/heads/main" not in text, path.name


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
