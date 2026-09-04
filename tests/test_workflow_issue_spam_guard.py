"""Paper ops crons must not file GitHub Issues.

AGENT-569: verify-trade-execution treated a flat paper book / dry-run as
"Trade Execution Failed" and opened a new issue every weekday. North Star
and weekly digest used Issues as living dashboards, so closing them just
made the next cron recreate the card.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

SPAM_WORKFLOWS = (
    "verify-trade-execution.yml",
    "north-star-blocker-watch.yml",
    "weekly-health-digest.yml",
    "self-healing-monitor.yml",
)


def test_paper_ops_crons_do_not_create_github_issues() -> None:
    for name in SPAM_WORKFLOWS:
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "github.rest.issues.create(" not in text, name
        assert "issues.createComment(" not in text, name
        assert "issues: write" not in text, name
