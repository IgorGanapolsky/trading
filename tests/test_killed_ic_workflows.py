"""Prevention: killed IC entry workflows must remain deleted."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REMOVED_IC_WORKFLOWS = (
    ".github/workflows/force-iron-condor.yml",
    ".github/workflows/iron-condor-autonomous.yml",
    ".github/workflows/iron-condor-scan.yml",
    ".github/workflows/execute-credit-spread.yml",
    ".github/workflows/iron-condor-guardian.yml",
)


def test_killed_ic_workflows_are_absent() -> None:
    assert [rel for rel in REMOVED_IC_WORKFLOWS if (ROOT / rel).exists()] == []


def test_trading_rules_document_active_put_credit() -> None:
    text = (ROOT / ".claude/rules/trading.md").read_text(encoding="utf-8")
    assert "spy_put_credit" in text
    assert "killed" in text.lower()
    # Must not present iron condor as the sole active North Star strategy
    assert "Active Strategy" in text or "Active strategy" in text or "post IC kill" in text
