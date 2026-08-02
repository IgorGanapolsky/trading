"""Prevention: killed IC entry workflows must remain no-ops.

Boundary: new iron-condor / ic_simple entries are forbidden.
Guardian exit path may exist separately; these files must refuse entry.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

KILLED_ENTRY_WORKFLOWS = (
    ".github/workflows/force-iron-condor.yml",
    ".github/workflows/iron-condor-autonomous.yml",
    ".github/workflows/iron-condor-scan.yml",
    ".github/workflows/execute-credit-spread.yml",
)

REQUIRED_KILL_MARKERS = (
    "STRATEGY_KILLED",
    "spy_put_credit",
)


def test_killed_ic_entry_workflows_are_refuse_noops() -> None:
    for rel in KILLED_ENTRY_WORKFLOWS:
        path = ROOT / rel
        assert path.is_file(), f"missing killed workflow file: {rel}"
        text = path.read_text(encoding="utf-8")
        assert "DISABLED" in text or "KILLED" in text, f"{rel} must be marked disabled/killed"
        for marker in REQUIRED_KILL_MARKERS:
            assert marker in text, f"{rel} missing marker {marker!r}"
        # Must not still execute trader entry scripts
        assert "iron_condor_trader.py --force" not in text or "Refuse" in text or "exit 1" in text
        assert "OrderClass" not in text, f"{rel} still contains live order submission code"


def test_guardian_workflow_still_present() -> None:
    """Guardian owns residual exit path; do not delete the file (boundary-policy)."""
    path = ROOT / ".github/workflows/iron-condor-guardian.yml"
    assert path.is_file(), "iron-condor-guardian.yml must remain in repo"


def test_trading_rules_document_active_put_credit() -> None:
    text = (ROOT / ".claude/rules/trading.md").read_text(encoding="utf-8")
    assert "spy_put_credit" in text
    assert "KILLED" in text
    # Must not present iron condor as the sole active North Star strategy
    assert "Active Strategy" in text or "Active strategy" in text or "post IC kill" in text
