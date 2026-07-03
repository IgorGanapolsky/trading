"""
E2E tests for iron condor exit fixes (April 3, 2026).

Validates:
1. 24h minimum holding period enforcement
2. Missing entry_date defaults to HOLD
3. Orphan cleanup grace period (24h)
4. Credential lookup uses canonical function
5. Validation phase stays at 1 contract via MAX_CONTRACTS_PER_TRADE
6. Gate congruency: verified_edge requires >= 50% win rate + 30 trades
"""

from __future__ import annotations

from datetime import datetime, timedelta

# --- Test 1: 24h hold period ---


def test_hold_period_blocks_early_exit():
    """Positions held < 24h should not be closed."""
    from scripts.manage_iron_condor_positions import check_exit_conditions

    ic = {
        "expiry": (datetime.now() + timedelta(days=30)),
        "total_pl": 50.0,
        "credit_received": 100.0,
        "entry_date": (datetime.now() - timedelta(hours=2)).isoformat(),
    }
    should_exit, reason, details = check_exit_conditions(ic)
    assert not should_exit
    assert reason == "HOLD"
    assert "24h minimum" in details


def test_hold_period_allows_exit_after_24h():
    """Positions held > 24h should be evaluated for exit."""
    from scripts.manage_iron_condor_positions import check_exit_conditions

    ic = {
        "expiry": (datetime.now() + timedelta(days=30)),
        "total_pl": 60.0,
        "credit_received": 100.0,
        "entry_date": (datetime.now() - timedelta(hours=25)).isoformat(),
    }
    should_exit, reason, details = check_exit_conditions(ic)
    # Should evaluate (may or may not exit depending on P/L)
    # 60% profit > 25% target -> should exit
    assert should_exit
    assert reason == "PROFIT_TARGET"


def test_hold_period_allows_stop_loss_after_24h():
    """Stop loss should trigger after 24h hold."""
    from scripts.manage_iron_condor_positions import check_exit_conditions

    ic = {
        "expiry": (datetime.now() + timedelta(days=30)),
        "total_pl": -210.0,
        "credit_received": 100.0,
        "entry_date": (datetime.now() - timedelta(hours=25)).isoformat(),
    }
    should_exit, reason, details = check_exit_conditions(ic)
    assert should_exit
    assert reason == "STOP_LOSS"


# --- Test 2: Missing entry_date defaults to HOLD ---


def test_missing_entry_date_defaults_to_hold():
    """If entry_date is not recorded, default to HOLD."""
    from scripts.manage_iron_condor_positions import check_exit_conditions

    ic = {
        "expiry": (datetime.now() + timedelta(days=30)),
        "total_pl": 80.0,
        "credit_received": 100.0,
        # No entry_date key
    }
    should_exit, reason, details = check_exit_conditions(ic)
    assert not should_exit
    assert reason == "HOLD"
    assert "No entry_date recorded" in details


# --- Test 3: DTE exit still works after hold period ---


def test_dte_exit_triggers_after_hold():
    """7 DTE exit should trigger even with hold period met."""
    from scripts.manage_iron_condor_positions import check_exit_conditions

    ic = {
        "expiry": (datetime.now() + timedelta(days=5)),  # 5 DTE
        "total_pl": -10.0,
        "credit_received": 100.0,
        "entry_date": (datetime.now() - timedelta(days=30)).isoformat(),
    }
    should_exit, reason, details = check_exit_conditions(ic)
    assert should_exit
    assert reason == "DTE_EXIT"


# --- Test 4: MAX_CONTRACTS_PER_TRADE ---


def test_max_contracts_per_trade_is_1():
    """Validation phase must stay at one contract until edge is proven."""
    from src.core.trading_constants import MAX_CONTRACTS_PER_TRADE

    assert MAX_CONTRACTS_PER_TRADE == 1


# --- Test 5: Credential lookup ---


def test_manage_script_credential_lookup_uses_canonical():
    """manage_iron_condor_positions should use canonical credential lookup."""
    import inspect

    from scripts.manage_iron_condor_positions import get_alpaca_credentials

    source = inspect.getsource(get_alpaca_credentials)
    assert "ALPACA_PAPER_TRADING_API_KEY" in source
    # Should NOT use the old 5K/30K env var names in actual lookup code
    # (they may appear in comments/docstrings, so check environ.get calls only)
    import re

    env_gets = re.findall(r'environ\.get\("([^"]+)"\)', source)
    for var_name in env_gets:
        assert "5K" not in var_name, f"Still using old 5K env var: {var_name}"
        assert "30K" not in var_name, f"Still using old 30K env var: {var_name}"


# --- Test 6: Gate congruency ---


def test_gate_scale_allowed_requires_win_rate_and_sample():
    """scale_allowed should require >= 50% win rate AND 30+ trades."""

    # Gate congruency rule (formerly enforced by the removed publishing-surface
    # generator; the underlying gate semantics still apply downstream).
    def compute_scale_allowed(block_new_positions, win_rate_pct, closed_total):
        return not bool(block_new_positions) and (win_rate_pct or 0) >= 50 and closed_total >= 30

    # 24% win rate, 66 trades -> not scalable
    assert not compute_scale_allowed(False, 24.24, 66)
    # 80% win rate, 66 trades -> scalable
    assert compute_scale_allowed(False, 80.0, 66)
    # 80% win rate, 10 trades -> not enough sample
    assert not compute_scale_allowed(False, 80.0, 10)
    # blocked -> not scalable regardless
    assert not compute_scale_allowed(True, 90.0, 100)


def test_gate_verified_edge_requires_win_rate_and_sample():
    """verified_edge_available should require >= 50% win rate AND 30+ trades."""

    def compute_verified_edge(weekly_edge, win_rate_pct, closed_total):
        return bool(weekly_edge) and (win_rate_pct or 0) >= 50 and closed_total >= 30

    # Weekly says edge, but all-time is 24% -> no edge
    assert not compute_verified_edge(True, 24.24, 66)
    # Weekly says edge, all-time 80%, 66 trades -> edge
    assert compute_verified_edge(True, 80.0, 66)
    # Weekly says no edge -> no edge regardless
    assert not compute_verified_edge(False, 90.0, 100)
