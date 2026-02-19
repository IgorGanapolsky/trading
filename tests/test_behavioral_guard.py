"""Tests for BehavioralGuard — FOMO, cooling, blacklist checks."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.safety.behavioral_guard import (
    BehavioralGuard,
    _STATE_FILE,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_state(tmp_path, monkeypatch):
    """Redirect state file to tmp_path so tests don't pollute data/."""
    fake = tmp_path / "behavioral_guard_state.json"
    monkeypatch.setattr("src.safety.behavioral_guard._STATE_FILE", fake)
    yield


# ── Blacklist ─────────────────────────────────────────────────────────


def test_blacklist_rejects_sofi():
    bg = BehavioralGuard()
    result = bg.evaluate(symbol="SOFI")
    assert not result.passed
    assert any("BLACKLISTED" in r for r in result.rejections)


def test_blacklist_allows_spy():
    bg = BehavioralGuard()
    result = bg.evaluate(symbol="SPY")
    assert "blacklist" in result.checks_run
    assert not any("BLACKLISTED" in r for r in result.rejections)


def test_blacklist_rejects_occ_symbol():
    """OCC symbol for SOFI should still be caught."""
    bg = BehavioralGuard()
    result = bg.evaluate(symbol="SOFI260115P00024000")
    assert not result.passed
    assert any("BLACKLISTED" in r for r in result.rejections)


# ── FOMO ──────────────────────────────────────────────────────────────


def test_fomo_rejects_large_move():
    bg = BehavioralGuard(fomo_threshold=0.02)
    result = bg.evaluate(symbol="SPY", spy_open=500.0, spy_current=512.0)
    assert not result.passed
    assert any("FOMO" in r for r in result.rejections)


def test_fomo_allows_small_move():
    bg = BehavioralGuard(fomo_threshold=0.02)
    result = bg.evaluate(symbol="SPY", spy_open=500.0, spy_current=504.0)
    assert not any("FOMO" in r for r in result.rejections)


def test_fomo_fails_open_no_data():
    """No market data = allow trade (fail open)."""
    bg = BehavioralGuard()
    result = bg.evaluate(symbol="SPY", spy_open=None, spy_current=None)
    assert not any("FOMO" in r for r in result.rejections)


def test_fomo_detects_negative_move():
    """A big drop is also FOMO-triggering."""
    bg = BehavioralGuard(fomo_threshold=0.02)
    result = bg.evaluate(symbol="SPY", spy_open=500.0, spy_current=488.0)
    assert any("FOMO" in r for r in result.rejections)


# ── Stop-loss cooling ────────────────────────────────────────────────


def test_cooling_blocks_recent_exit():
    BehavioralGuard.record_stop_loss_exit(expiry="2026-03-21", symbol="SPY")
    bg = BehavioralGuard(cooling_hours=24)
    result = bg.evaluate(symbol="SPY", expiry="2026-03-21")
    assert not result.passed
    assert any("COOLING" in r for r in result.rejections)


def test_cooling_allows_old_exit():
    """Exit >24h ago should not block."""
    # Manually write an old entry
    old_ts = (datetime.now(tz=timezone.utc) - timedelta(hours=25)).isoformat()
    state = {"stop_loss_exits": [{"expiry": "2026-03-21", "symbol": "SPY", "timestamp": old_ts}]}
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state))

    bg = BehavioralGuard(cooling_hours=24)
    result = bg.evaluate(symbol="SPY", expiry="2026-03-21")
    assert not any("COOLING" in r for r in result.rejections)


def test_cooling_allows_different_expiry():
    BehavioralGuard.record_stop_loss_exit(expiry="2026-03-21", symbol="SPY")
    bg = BehavioralGuard(cooling_hours=24)
    result = bg.evaluate(symbol="SPY", expiry="2026-03-28")
    assert not any("COOLING" in r for r in result.rejections)


def test_cooling_normalizes_yymmdd():
    """YYMMDD and YYYY-MM-DD for the same date should match."""
    BehavioralGuard.record_stop_loss_exit(expiry="260321", symbol="SPY")
    bg = BehavioralGuard(cooling_hours=24)
    result = bg.evaluate(symbol="SPY", expiry="2026-03-21")
    assert any("COOLING" in r for r in result.rejections)


# ── Integration ──────────────────────────────────────────────────────


def test_all_checks_run():
    bg = BehavioralGuard()
    result = bg.evaluate(symbol="SPY", spy_open=500.0, spy_current=501.0, expiry="2026-04-18")
    assert set(result.checks_run) == {"blacklist", "fomo", "stop_loss_cooling"}
    assert result.passed


def test_multiple_rejections():
    """Blacklisted symbol + FOMO = 2 rejections."""
    bg = BehavioralGuard(fomo_threshold=0.02)
    result = bg.evaluate(symbol="SOFI", spy_open=500.0, spy_current=515.0)
    assert not result.passed
    assert len(result.rejections) == 2
