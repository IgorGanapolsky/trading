"""Tests for scripts/autonomous_repo_autopilot.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from scripts.autonomous_repo_autopilot import (
    are_checks_passing,
    extract_slug,
    run_cycle,
)


def test_extract_slug():
    assert extract_slug("chore/auto-alpaca-sync-36724449717-1") == "alpaca-sync"
    assert extract_slug("chore/auto-premarket-sync-12345678-1") == "premarket-sync"
    assert extract_slug("chore/auto-put-credit-sync-99999-2") == "put-credit-sync"
    assert extract_slug("chore/auto-arxiv-ingest-36678863158-1") == "arxiv-ingest"
    assert extract_slug("feat/agent-31-autonomous-autopilot") == "unknown"


def test_are_checks_passing():
    # Empty checks
    assert not are_checks_passing([])

    # All success
    checks_success = [
        {"name": "CodeQL", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "CI", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "SonarCloud", "status": "COMPLETED", "conclusion": "SUCCESS"},
    ]
    assert are_checks_passing(checks_success)

    # Success with skipped / neutral
    checks_mixed = [
        {"name": "CodeQL", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "Optional", "status": "COMPLETED", "conclusion": "SKIPPED"},
        {"name": "Report", "status": "COMPLETED", "conclusion": "NEUTRAL"},
    ]
    assert are_checks_passing(checks_mixed)

    # In progress
    checks_in_progress = [
        {"name": "CodeQL", "status": "IN_PROGRESS", "conclusion": None},
    ]
    assert not are_checks_passing(checks_in_progress)

    # Failure
    checks_failed = [
        {"name": "CodeQL", "status": "COMPLETED", "conclusion": "FAILURE"},
    ]
    assert not are_checks_passing(checks_failed)


@patch("scripts.autonomous_repo_autopilot.list_open_prs")
@patch("scripts.autonomous_repo_autopilot.close_superseded_pr")
@patch("scripts.autonomous_repo_autopilot.approve_pr")
@patch("scripts.autonomous_repo_autopilot.merge_pr")
def test_run_cycle_pruning_and_merge(
    mock_merge: MagicMock,
    mock_approve: MagicMock,
    mock_close: MagicMock,
    mock_list_prs: MagicMock,
):
    mock_close.return_value = True
    mock_approve.return_value = True
    mock_merge.return_value = True

    # 3 premarket sync PRs (newest + 2 older)
    mock_list_prs.return_value = [
        {
            "number": 5136,
            "title": "chore: pre-market data sync [auto]",
            "headRefName": "chore/auto-premarket-sync-36730468804-1",
            "author": {"login": "app/github-actions"},
            "isCrossRepository": False,
            "createdAt": "2026-09-30T10:00:00Z",
            "reviewDecision": "REVIEW_REQUIRED",
            "statusCheckRollup": [
                {"name": "CI", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
        },
        {
            "number": 5099,
            "title": "chore: pre-market data sync [auto]",
            "headRefName": "chore/auto-premarket-sync-36583757416-1",
            "author": {"login": "app/github-actions"},
            "isCrossRepository": False,
            "createdAt": "2026-09-29T10:00:00Z",
            "reviewDecision": "REVIEW_REQUIRED",
            "statusCheckRollup": [],
        },
        {
            "number": 5066,
            "title": "chore: pre-market data sync [auto]",
            "headRefName": "chore/auto-premarket-sync-36437319896-1",
            "author": {"login": "app/github-actions"},
            "isCrossRepository": False,
            "createdAt": "2026-09-28T10:00:00Z",
            "reviewDecision": "REVIEW_REQUIRED",
            "statusCheckRollup": [],
        },
    ]

    summary = run_cycle()
    assert summary["open_prs_scanned"] == 3
    assert summary["auto_slugs"] == ["premarket-sync"]
    assert summary["superseded_closed"] == 2
    assert summary["auto_merged"] == 1

    # Verify older PRs closed
    mock_close.assert_any_call(5099, "premarket-sync", 5136)
    mock_close.assert_any_call(5066, "premarket-sync", 5136)
    # Verify newest PR approved and merged
    mock_approve.assert_called_once_with(5136)
    mock_merge.assert_called_once_with(5136)


@patch("scripts.autonomous_repo_autopilot.list_open_prs")
def test_run_cycle_rejects_unauthorized_author_or_fork(mock_list_prs: MagicMock):
    # Fork PR from external contributor trying to mimic auto sync
    mock_list_prs.return_value = [
        {
            "number": 9999,
            "title": "chore: pre-market data sync [auto]",
            "headRefName": "chore/auto-premarket-sync-99999-1",
            "author": {"login": "malicious-contributor"},
            "isCrossRepository": True,
            "createdAt": "2026-09-30T12:00:00Z",
            "statusCheckRollup": [],
        },
    ]
    summary = run_cycle()
    assert summary["open_prs_scanned"] == 1
    assert summary["auto_slugs"] == []
    assert summary["superseded_closed"] == 0
    assert summary["auto_merged"] == 0
