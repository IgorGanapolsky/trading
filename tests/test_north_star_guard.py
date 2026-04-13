"""Tests for North Star guard dynamic risk constraints."""

from src.safety.north_star_guard import get_guard_context


def test_guard_validation_mode_with_low_sample(tmp_path):
    state = tmp_path / "system_state.json"
    state.write_text(
        """
{
  "paper_account": {"equity": 100000, "win_rate": 50, "win_rate_sample_size": 10},
  "paper_trading": {"current_day": 20, "target_duration_days": 90}
}
""".strip(),
        encoding="utf-8",
    )

    guard = get_guard_context(state)
    assert guard["enabled"] is True
    assert guard["mode"] == "validation"
    assert guard["block_new_positions"] is False
    assert guard["max_position_pct"] == 0.05
    assert guard["target_date"] is None
    assert guard["north_star_target_mode"] == "asap_monthly_income"
    assert guard["north_star_monthly_after_tax_target"] == 6000.0


def test_guard_capital_preservation_blocks_new_positions(tmp_path):
    state = tmp_path / "system_state.json"
    state.write_text(
        """
{
  "paper_account": {"equity": 101000, "win_rate": 37.5, "win_rate_sample_size": 32},
  "paper_trading": {"current_day": 40, "target_duration_days": 90}
}
""".strip(),
        encoding="utf-8",
    )

    guard = get_guard_context(state)
    assert guard["mode"] == "capital_preservation"
    assert guard["block_new_positions"] is True
    assert guard["max_position_pct"] <= 0.01


def test_guard_ignores_unconfirmed_env_override(tmp_path, monkeypatch):
    """A stray scheduled env var must not disable North Star blocking."""
    state = tmp_path / "system_state.json"
    state.write_text(
        """
{
  "paper_account": {"equity": 101000, "win_rate": 37.5, "win_rate_sample_size": 32},
  "paper_trading": {"current_day": 40, "target_duration_days": 90}
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("NORTH_STAR_GUARD_OVERRIDE", "true")
    monkeypatch.delenv("NORTH_STAR_GUARD_OVERRIDE_CONFIRM", raising=False)

    guard = get_guard_context(state)

    assert guard["mode"] == "capital_preservation"
    assert guard["block_new_positions"] is True
    assert any("ignored" in reason for reason in guard["reasons"])


def test_guard_accepts_explicit_manual_override(tmp_path, monkeypatch):
    """Manual override now requires a second explicit confirmation env var."""
    state = tmp_path / "system_state.json"
    state.write_text(
        """
{
  "paper_account": {"equity": 101000, "win_rate": 37.5, "win_rate_sample_size": 32},
  "paper_trading": {"current_day": 40, "target_duration_days": 90}
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("NORTH_STAR_GUARD_OVERRIDE", "true")
    monkeypatch.setenv("NORTH_STAR_GUARD_OVERRIDE_CONFIRM", "manual-risk-accepted")

    guard = get_guard_context(state)

    assert guard["mode"] == "override"
    assert guard["block_new_positions"] is False
    assert guard["max_position_pct"] == 0.05


def test_guard_scale_ready_when_validation_passes(tmp_path):
    state = tmp_path / "system_state.json"
    state.write_text(
        """
{
  "paper_account": {"equity": 450000, "win_rate": 82.0, "win_rate_sample_size": 45},
  "paper_trading": {"current_day": 95, "target_duration_days": 90}
}
""".strip(),
        encoding="utf-8",
    )

    guard = get_guard_context(state)
    assert guard["mode"] == "scale_ready"
    assert guard["block_new_positions"] is False
    assert guard["max_position_pct"] == 0.05


def test_guard_applies_weekly_gate_position_cap(tmp_path):
    state = tmp_path / "system_state.json"
    state.write_text(
        """
{
  "paper_account": {"equity": 200000, "win_rate": 85.0, "win_rate_sample_size": 60},
  "paper_trading": {"current_day": 120, "target_duration_days": 90},
  "north_star_weekly_gate": {
    "mode": "cautious",
    "recommended_max_position_pct": 0.0125,
    "block_new_positions": false
  }
}
""".strip(),
        encoding="utf-8",
    )

    guard = get_guard_context(state)
    assert guard["block_new_positions"] is False
    assert guard["max_position_pct"] <= 0.0125
    assert guard["weekly_gate_mode"] == "cautious"


def test_guard_applies_autopilot_regime_sizing_cap(tmp_path):
    state = tmp_path / "system_state.json"
    state.write_text(
        """
{
  "paper_account": {"equity": 200000, "win_rate": 85.0, "win_rate_sample_size": 60},
  "paper_trading": {"current_day": 120, "target_duration_days": 90},
  "north_star_weekly_gate": {
    "mode": "cautious",
    "recommended_max_position_pct": 0.02,
    "block_new_positions": false
  },
  "north_star_autopilot": {
    "regime_aware_sizing": {
      "recommended_max_position_pct": 0.0115
    }
  }
}
""".strip(),
        encoding="utf-8",
    )

    guard = get_guard_context(state)
    assert guard["block_new_positions"] is False
    assert guard["max_position_pct"] <= 0.0115


def test_guard_allows_validation_reset_entries_while_live_risk_stays_blocked(tmp_path):
    state = tmp_path / "system_state.json"
    state.write_text(
        """
{
  "paper_account": {"equity": 93838.3, "win_rate": 24.24, "win_rate_sample_size": 66},
  "paper_trading": {"current_day": 91, "target_duration_days": 90},
  "north_star_weekly_gate": {
    "mode": "validation_reset",
    "recommended_max_position_pct": 0.01,
    "block_new_positions": false,
    "block_live_new_positions": true,
    "allow_validation_entries": true,
    "validation_reset_reason": "Legacy lifetime ledger remains negative."
  }
}
""".strip(),
        encoding="utf-8",
    )

    guard = get_guard_context(state)
    assert guard["mode"] == "validation_reset"
    assert guard["block_new_positions"] is False
    assert guard["allow_validation_entries"] is True
    assert guard["block_live_new_positions"] is True
    assert guard["max_position_pct"] <= 0.01
