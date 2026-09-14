"""Unit tests for open-gsd FORMAT steal in ralph_gsd_tick (STATE/CONTEXT/verify)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TICK_PATH = ROOT / "scripts" / "ralph_gsd_tick.py"


def _load_tick():
    spec = importlib.util.spec_from_file_location("ralph_gsd_tick", TICK_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load tick")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_phase_loop_maps_cash_residual():
    mod = _load_tick()
    pick = {"residual": "cash_fee_yes", "act": "expand drafts"}
    phase = mod._phase_loop(pick)
    assert phase["loop"] == ["discuss", "plan", "execute", "verify", "ship"]
    assert phase["phase_name"] == "miramar-fee-yes"
    assert phase["next_action"] == "verify-phase"
    assert "open-gsd" in phase["source"]


def test_verify_cash_gaps_without_sheet(tmp_path, monkeypatch):
    mod = _load_tick()
    monkeypatch.setattr(mod, "CALL_SHEET", tmp_path / "missing.md")
    monkeypatch.setattr(mod, "DRAFTS_DIR", tmp_path / "drafts")
    (tmp_path / "drafts").mkdir()
    pick = {"residual": "cash_fee_yes"}
    v = mod.verify_evidence(pick, live_checkout=False)
    assert v["status"] == "gaps_found"
    assert v["ok"] is False


def test_verify_cash_passes_with_sheet_and_draft(tmp_path, monkeypatch):
    mod = _load_tick()
    sheet = tmp_path / "CALL_SHEET_VERIFIED.md"
    sheet.write_text("# dial\n")
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    (drafts / "prepaid_x_2026-09-14.json").write_text("{}")
    monkeypatch.setattr(mod, "CALL_SHEET", sheet)
    monkeypatch.setattr(mod, "DRAFTS_DIR", drafts)
    pick = {"residual": "cash_fee_yes"}
    v = mod.verify_evidence(pick, live_checkout=False)
    assert v["status"] == "passed"
    assert v["ok"] is True


def test_write_state_and_context(tmp_path, monkeypatch):
    mod = _load_tick()
    planning = tmp_path / ".planning"
    monkeypatch.setattr(mod, "PLANNING", planning)
    monkeypatch.setattr(mod, "STATE_MD", planning / "STATE.md")
    monkeypatch.setattr(mod, "CONTEXT_MD", planning / "CONTEXT.md")
    pick = {
        "residual": "cash_fee_yes",
        "act": "Expand CALL_SHEET",
    }
    phase = mod._phase_loop(pick)
    verification = {"status": "gaps_found", "ok": False, "checks": []}
    state = mod.write_state(pick, phase, verification, overall="F")
    ctx = mod.write_context(pick, phase)
    assert state.exists()
    text = state.read_text()
    assert "gsd_state_version" in text
    assert "miramar-fee-yes" in text
    assert "Discuss → Plan → Execute → Verify → Ship" in text
    assert ctx.exists()
    assert "Hard decisions" in ctx.read_text()


def test_verify_ci_fails_while_detail_present():
    mod = _load_tick()
    pick = {
        "residual": "fix_required_ci",
        "detail": [{"pr": 1, "check": "Run All Tests"}],
    }
    v = mod.verify_evidence(pick)
    assert v["ok"] is False
    assert v["status"] == "gaps_found"


def test_pick_empty_scorecard_is_maintain_not_cash():
    """CI runners often lack fleet-a-plus scorecard — must not invent cash residual."""
    mod = _load_tick()
    pick = mod._pick({}, [])
    assert pick["residual"] == "maintain"


def test_pick_explicit_cash_fail_is_cash():
    mod = _load_tick()
    pick = mod._pick({"cash_fee_yes": {"ok": False, "letter": "F"}, "overall": {"letter": "F"}}, [])
    assert pick["residual"] == "cash_fee_yes"


def test_verify_cash_skips_when_lane_absent(tmp_path, monkeypatch):
    mod = _load_tick()
    missing_lane = tmp_path / "no-such-lane" / "outreach" / "CALL_SHEET_VERIFIED.md"
    monkeypatch.setattr(mod, "CALL_SHEET", missing_lane)
    monkeypatch.setattr(mod, "DRAFTS_DIR", missing_lane.parent / "drafts")
    v = mod.verify_evidence({"residual": "cash_fee_yes"})
    assert v["ok"] is True
    assert v["status"] == "passed"
    assert any(c.get("skipped") for c in v["checks"])
