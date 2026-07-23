"""
Tests for backtest_gate.py — validates parameter changes against trade history.

Covers:
- Metrics computation (win rate, P&L)
- Simulation with different hold periods
- Simulation with different profit targets
- Gate pass/fail logic
"""

from __future__ import annotations

from scripts.backtest_gate import check_gate, compute_metrics, simulate_with_params


def _make_trade(
    outcome: str, pnl: float, entry_credit: float = 200, hold_hours: float = 2.0
) -> dict:
    """Helper to create test trades."""
    from datetime import datetime, timedelta, timezone

    entry = datetime(2026, 3, 1, 14, 0, tzinfo=timezone.utc)
    exit_dt = entry + timedelta(hours=hold_hours)
    return {
        "id": f"test_{outcome}_{pnl}",
        "status": "closed",
        "outcome": outcome,
        "realized_pnl": pnl,
        "entry_credit": entry_credit,
        "credit_received": entry_credit,
        "entry_time": entry.isoformat(),
        "exit_time": exit_dt.isoformat(),
    }


# --- Metrics ---


def test_compute_metrics_basic():
    trades = [
        {"outcome": "win", "realized_pnl": 100},
        {"outcome": "win", "realized_pnl": 50},
        {"outcome": "loss", "realized_pnl": -80},
    ]
    m = compute_metrics(trades)
    assert m["total"] == 3
    assert m["wins"] == 2
    assert m["losses"] == 1
    assert round(m["win_rate"], 1) == 66.7
    assert m["total_pnl"] == 70


def test_compute_metrics_empty():
    m = compute_metrics([])
    assert m["total"] == 0
    assert m["win_rate"] == 0


def test_compute_metrics_all_losses():
    trades = [{"outcome": "loss", "realized_pnl": -50} for _ in range(5)]
    m = compute_metrics(trades)
    assert m["win_rate"] == 0
    assert m["total_pnl"] == -250


# --- Simulation ---


def test_simulation_short_hold_loss_recovers():
    """Trades held < min_hold_hours that lost small amounts should partially recover."""
    trades = [_make_trade("loss", -30, entry_credit=200, hold_hours=0.5)]
    result = simulate_with_params(trades, min_hold_hours=24)
    # Small loss (30 < 200 * 1.0 * 0.5 = 100) with short hold -> simulated recovery
    assert result["trades"][0]["simulated_outcome"] == "win"
    assert result["trades"][0]["simulated_pnl"] > 0


def test_simulation_long_hold_loss_unchanged():
    """Trades held > min_hold_hours that lost should not change."""
    trades = [_make_trade("loss", -150, entry_credit=200, hold_hours=48)]
    result = simulate_with_params(trades, min_hold_hours=24)
    assert result["trades"][0]["simulated_outcome"] == "loss"
    assert result["trades"][0]["simulated_pnl"] == -150


def test_simulation_win_unchanged():
    """Winning trades should keep their outcome."""
    trades = [_make_trade("win", 100, entry_credit=200, hold_hours=48)]
    result = simulate_with_params(trades, min_hold_hours=24)
    assert result["trades"][0]["simulated_outcome"] == "win"


def test_simulation_different_profit_target():
    """Lower profit target should cap winning trades."""
    trades = [_make_trade("win", 150, entry_credit=200, hold_hours=48)]
    result = simulate_with_params(trades, profit_target_pct=0.25)
    # 150/200 = 75% > 25% target -> capped at 200 * 0.25 = 50
    assert result["trades"][0]["simulated_pnl"] == 50.0


# --- Gate ---


def test_gate_passes_on_improvement():
    current = {"win_rate": 24.0, "total_pnl": -3402}
    proposed = {"win_rate": 35.0, "total_pnl": -2000}
    gate = check_gate(current, proposed)
    assert gate["passed"] is True
    assert gate["improvement_pnl"] == 1402


def test_gate_blocks_win_rate_regression():
    current = {"win_rate": 30.0, "total_pnl": -1000}
    proposed = {"win_rate": 25.0, "total_pnl": -500}
    gate = check_gate(current, proposed)
    assert gate["passed"] is False
    assert any("win rate" in r.lower() for r in gate["reasons"])


def test_gate_blocks_pnl_regression():
    current = {"win_rate": 30.0, "total_pnl": -1000}
    proposed = {"win_rate": 35.0, "total_pnl": -1500}
    gate = check_gate(current, proposed)
    assert gate["passed"] is False
    assert any("p&l" in r.lower() for r in gate["reasons"])


def test_gate_passes_equal_metrics():
    current = {"win_rate": 50.0, "total_pnl": 0}
    proposed = {"win_rate": 50.0, "total_pnl": 0}
    gate = check_gate(current, proposed)
    assert gate["passed"] is True
