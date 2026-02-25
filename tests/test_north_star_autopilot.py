from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.safety.north_star_autopilot import (
    build_autopilot_snapshot,
    compute_cadence_optimizer,
    compute_hard_gate_monitor,
    compute_regime_aware_sizing,
    write_gate_overrides,
)


def _base_state() -> dict:
    return {
        "meta": {"last_updated": "2026-02-20T14:00:00Z"},
        "north_star": {"monthly_after_tax_target": 6000.0},
        "north_star_weekly_gate": {
            "updated_at": "2026-02-20T14:00:00Z",
            "mode": "validation",
            "sample_size": 2,
            "expectancy_per_trade": -20.0,
            "recommended_max_position_pct": 0.02,
            "block_new_positions": False,
            "liquidity_min_volume_ratio": 0.2,
            "scale_multiplier_from_usd_macro": 0.95,
            "cadence_kpi": {
                "passed": False,
                "qualified_setups_observed": 0,
                "min_qualified_setups_per_week": 3,
            },
            "no_trade_diagnostic": {
                "blocked_categories": ["liquidity"],
                "gate_block_counts": {"liquidity": 4, "dte": 1},
                "gate_status": {
                    "liquidity": {"status": "blocked", "threshold_min_volume_ratio": 0.2},
                    "ai_credit_stress": {"status": "watch", "severity_score": 40.0},
                    "usd_macro": {"status": "watch", "position_size_multiplier": 0.95},
                    "ai_cycle": {
                        "status": "watch",
                        "position_size_multiplier": 0.95,
                        "capex_deceleration_shock": False,
                    },
                    "regime": {"status": "pass"},
                },
            },
        },
    }


def test_cadence_optimizer_loosen_when_liquidity_dominates() -> None:
    result = compute_cadence_optimizer(_base_state())
    assert result["decision"] == "loosen_liquidity_floor"
    assert result["apply_override"] is True
    assert result["target_min_liquidity_volume_ratio"] == 0.18


def test_regime_aware_sizing_reduces_cap_with_macro_watch() -> None:
    result = compute_regime_aware_sizing(_base_state())
    assert result["base_max_position_pct"] == 0.02
    assert result["recommended_max_position_pct"] < 0.02
    assert result["block_new_positions"] is False


def test_hard_gate_monitor_critical_on_stale_and_target_mismatch() -> None:
    state = _base_state()
    state["meta"]["last_updated"] = "2026-02-18T00:00:00Z"
    state["north_star"]["monthly_after_tax_target"] = 5000.0
    now_utc = datetime(2026, 2, 20, 15, 0, tzinfo=timezone.utc)
    monitor = compute_hard_gate_monitor(state, now_utc=now_utc, halt_exists=False)
    assert monitor["status"] == "critical"
    assert monitor["critical_count"] >= 1
    assert monitor["block_new_positions"] is True


def test_regime_aware_sizing_applies_ai_cycle_shock_multiplier() -> None:
    state = _base_state()
    state["north_star_weekly_gate"]["no_trade_diagnostic"]["gate_status"]["ai_cycle"] = {
        "status": "blocked",
        "position_size_multiplier": 0.85,
        "capex_deceleration_shock": True,
    }
    result = compute_regime_aware_sizing(state)
    assert result["recommended_max_position_pct"] < 0.015
    multipliers = result["applied_multipliers"]
    names = {row.get("name") for row in multipliers}
    assert "ai_cycle_multiplier" in names
    assert "ai_cycle_capex_shock" in names


def test_build_snapshot_and_write_overrides(tmp_path: Path) -> None:
    state = _base_state()
    blocker_report = {
        "blocked": True,
        "blockers": [{"id": "cadence_failed"}],
        "warnings": [],
        "root_causes": ["cadence miss"],
    }
    now_utc = datetime(2026, 2, 20, 15, 0, tzinfo=timezone.utc)
    snapshot = build_autopilot_snapshot(
        state=state,
        blocker_report=blocker_report,
        now_utc=now_utc,
        halt_exists=False,
    )
    assert snapshot["execution_actions"]
    first = write_gate_overrides(data_dir=tmp_path, snapshot=snapshot, now_utc=now_utc)
    second = write_gate_overrides(data_dir=tmp_path, snapshot=snapshot, now_utc=now_utc)
    assert first["changed"] is True
    assert second["changed"] is False
    assert (tmp_path / "runtime" / "north_star_gate_overrides.json").exists()
