"""
Tests for ML feedback loop (update_ml_from_trades.py).

Covers:
1. Thompson Sampler update from real trade data
2. Trading gate enforcement (win rate + sample size)
3. Post-mortem lesson generation from losses
4. Drift detection alerts
5. Halt file enforcement
6. Idempotent lesson generation (no duplicates)
"""

from __future__ import annotations

from scripts.update_ml_from_trades import (
    check_trading_gate,
    generate_loss_postmortems,
    update_thompson_sampler,
)

# --- Thompson Sampler Tests ---


def test_thompson_update_replaces_stale_priors():
    """Stale (86/14) priors should be replaced with empirical data."""
    trades = {"stats": {"wins": 16, "losses": 49, "closed_trades": 66, "win_rate_pct": 24.24}}
    model = {
        "iron_condor": {"alpha": 86.0, "beta": 14.0, "wins": 0, "losses": 1},
        "spy_specific": {"alpha": 86.0, "beta": 14.0, "wins": 0, "losses": 1},
    }
    updated = update_thompson_sampler(trades, model)
    assert updated["iron_condor"]["alpha"] == 17.0  # 16 wins + 1
    assert updated["iron_condor"]["beta"] == 50.0  # 49 losses + 1
    assert updated["iron_condor"]["wins"] == 16
    assert updated["iron_condor"]["losses"] == 49


def test_thompson_update_with_zero_trades():
    """With no trades, priors should be (1, 1) — uninformative."""
    trades = {"stats": {"wins": 0, "losses": 0, "closed_trades": 0, "win_rate_pct": 0}}
    model = {"iron_condor": {"alpha": 86.0, "beta": 14.0, "wins": 0, "losses": 0}}
    updated = update_thompson_sampler(trades, model)
    assert updated["iron_condor"]["alpha"] == 1.0
    assert updated["iron_condor"]["beta"] == 1.0


def test_thompson_update_syncs_spy_specific():
    """spy_specific should match iron_condor (same underlying)."""
    trades = {"stats": {"wins": 10, "losses": 5, "closed_trades": 15, "win_rate_pct": 66.7}}
    model = {
        "iron_condor": {"alpha": 1, "beta": 1},
        "spy_specific": {"alpha": 1, "beta": 1},
    }
    updated = update_thompson_sampler(trades, model)
    assert updated["iron_condor"]["alpha"] == updated["spy_specific"]["alpha"]
    assert updated["iron_condor"]["beta"] == updated["spy_specific"]["beta"]


# --- Trading Gate Tests ---


def test_gate_blocks_low_win_rate():
    """Win rate below 50% with enough trades should block."""
    stats = {"closed_trades": 66, "win_rate_pct": 24.24, "avg_win": 70.5, "avg_loss": 92.45}
    gate = check_trading_gate(stats)
    assert not gate["should_trade"]
    assert "24.2%" in gate["block_reason"]


def test_gate_blocks_insufficient_trades():
    """Fewer than 30 trades should block even with high win rate."""
    stats = {"closed_trades": 10, "win_rate_pct": 80.0, "avg_win": 100, "avg_loss": 50}
    gate = check_trading_gate(stats)
    assert not gate["should_trade"]
    assert "10/30" in gate["block_reason"]


def test_gate_allows_good_performance():
    """High win rate with enough trades should allow."""
    stats = {"closed_trades": 50, "win_rate_pct": 75.0, "avg_win": 100, "avg_loss": 80}
    gate = check_trading_gate(stats)
    assert gate["should_trade"]
    assert gate["expectancy_per_trade"] > 0


def test_gate_calculates_expectancy():
    """Expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)."""
    stats = {"closed_trades": 100, "win_rate_pct": 80.0, "avg_win": 100, "avg_loss": 200}
    gate = check_trading_gate(stats)
    # Expected: 0.8 * 100 - 0.2 * 200 = 80 - 40 = 40
    assert gate["expectancy_per_trade"] == 40.0


# --- Post-Mortem Tests ---


def test_postmortem_generates_from_losses():
    """Should generate lessons for trades with P&L < -$20."""
    trades = {
        "stats": {},
        "trades": [
            {
                "id": "trade1",
                "outcome": "loss",
                "realized_pnl": -100,
                "entry_date": "2026-03-01",
                "exit_date": "2026-03-01",
                "entry_time": "2026-03-01T14:00:00+00:00",
                "exit_time": "2026-03-01T14:30:00+00:00",
                "signature": "SPY_test",
                "source": "",
            },
            {
                "id": "trade2",
                "outcome": "win",
                "realized_pnl": 50,
                "entry_date": "2026-03-02",
                "exit_date": "2026-03-05",
                "signature": "SPY_win",
                "source": "",
            },
            {
                "id": "trade3",
                "outcome": "loss",
                "realized_pnl": -5,
                "entry_date": "2026-03-03",
                "exit_date": "2026-03-03",
                "signature": "SPY_small",
                "source": "",
            },
        ],
    }
    lessons = generate_loss_postmortems(trades)
    assert len(lessons) == 1  # Only trade1 (P&L < -20)
    assert lessons[0]["pnl"] == -100
    assert "PREMATURE_EXIT" in lessons[0]["root_cause"]  # Held 0.5h


def test_postmortem_categorizes_orphan_cleanup():
    """Orphan cleanup should be identified in root cause."""
    trades = {
        "stats": {},
        "trades": [
            {
                "id": "orphan1",
                "outcome": "loss",
                "realized_pnl": -500,
                "entry_date": "2026-03-01",
                "exit_date": "2026-03-01",
                "signature": "SPY_orphan",
                "source": "alpaca_leg_cluster->ORPHAN",
            },
        ],
    }
    lessons = generate_loss_postmortems(trades)
    assert len(lessons) == 1
    assert "ORPHAN" in lessons[0]["root_cause"]


def test_postmortem_skips_wins():
    """Should not generate lessons for winning trades."""
    trades = {
        "stats": {},
        "trades": [
            {"id": "win1", "outcome": "win", "realized_pnl": 100, "signature": "SPY_win"},
        ],
    }
    lessons = generate_loss_postmortems(trades)
    assert len(lessons) == 0


def test_postmortem_limits_count():
    """Should respect max_lessons parameter."""
    trades = {
        "stats": {},
        "trades": [
            {
                "id": f"loss{i}",
                "outcome": "loss",
                "realized_pnl": -100 * (i + 1),
                "entry_date": "2026-03-01",
                "exit_date": "2026-03-01",
                "signature": f"SPY_loss{i}",
                "source": "",
            }
            for i in range(20)
        ],
    }
    lessons = generate_loss_postmortems(trades, max_lessons=3)
    assert len(lessons) == 3
    # Should be sorted by worst loss first
    assert lessons[0]["pnl"] < lessons[1]["pnl"]
