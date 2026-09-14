"""Prevention: scrap freeze (AGENT-615) must keep trading as a paper lab."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_active_scope import REMOVED_IC_WORKFLOWS, audit

ROOT = Path(__file__).resolve().parents[1]


def test_repo_passes_active_scope_audit() -> None:
    report = audit(ROOT)
    assert report["ok"] is True, report["findings"]


def test_scope_doc_states_cash_rule() -> None:
    text = (ROOT / "docs/TRADING_ACTIVE_SCOPE.md").read_text(encoding="utf-8")
    assert "paper validation lab" in text.lower() or "paper validation" in text.lower()
    assert "not" in text.lower() and "revenue" in text.lower()
    assert "spy_put_credit" in text
    assert "live_blocked" in text


def test_audit_flags_missing_scope_and_theater(tmp_path: Path) -> None:
    (tmp_path / "data/runtime").mkdir(parents=True)
    (tmp_path / "data/runtime/strategy_kill_switch.json").write_text(
        json.dumps(
            {
                "active_family": "spy_put_credit",
                "paper_only": True,
                "live_blocked": True,
                "killed_families": ["ic_simple", "iron_condor"],
            }
        ),
        encoding="utf-8",
    )
    # No scope doc → error
    report = audit(tmp_path)
    assert any(f["kind"] == "missing-scope-doc" for f in report["findings"])

    # Add scope doc but revive IC workflow + theater filename via git? skip git by
    # creating file and monkeypatching ls-files through real git init.
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/TRADING_ACTIVE_SCOPE.md").write_text("# scope\n", encoding="utf-8")
    bad_wf = tmp_path / REMOVED_IC_WORKFLOWS[0]
    bad_wf.parent.mkdir(parents=True, exist_ok=True)
    bad_wf.write_text("name: bad\n", encoding="utf-8")

    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    theater = tmp_path / "scripts" / "ralph_gsd_24_7_engine.py"
    theater.parent.mkdir(parents=True, exist_ok=True)
    theater.write_text("# theater\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)

    report2 = audit(tmp_path)
    kinds = {f["kind"] for f in report2["findings"]}
    assert "revived-ic-workflow" in kinds
    assert "forbidden-theater-path" in kinds
    assert report2["ok"] is False


def test_audit_rejects_live_unblocked(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/TRADING_ACTIVE_SCOPE.md").write_text("# scope\n", encoding="utf-8")
    (tmp_path / "data/runtime").mkdir(parents=True)
    (tmp_path / "data/runtime/strategy_kill_switch.json").write_text(
        json.dumps(
            {
                "active_family": "spy_put_credit",
                "paper_only": False,
                "live_blocked": False,
                "killed_families": ["ic_simple", "iron_condor"],
            }
        ),
        encoding="utf-8",
    )
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    report = audit(tmp_path)
    kinds = {f["kind"] for f in report["findings"]}
    assert "paper-only-required" in kinds
    assert "live-blocked-required" in kinds
