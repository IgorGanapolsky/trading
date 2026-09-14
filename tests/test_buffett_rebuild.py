"""AGENT-616 Buffett Rule #1 rebuild — profile + risk budget."""

from __future__ import annotations

from src.core.trading_profiles import get_put_credit_profile
from src.risk.put_credit_regime import (
    REQUIRE_ABOVE_200DMA,
    evaluate_buffett_risk_budget,
)


def test_default_profile_is_buffett_v2():
    p = get_put_credit_profile()
    assert p.name == "spy-put-credit-buffett"
    assert p.target_dte == 60
    assert p.min_dte == 45
    assert p.max_dte == 70
    assert p.take_profit_pct == 0.50
    assert p.stop_loss_pct == 2.0
    assert p.exit_dte == 30
    assert p.max_daily_structures == 1
    assert p.max_concurrent_positions == 1
    assert p.max_contracts_per_trade == 1
    assert p.position_size_pct == 0.01


def test_legacy_profile_still_registered():
    legacy = get_put_credit_profile("spy-put-credit")
    assert legacy.name == "spy-put-credit"
    assert legacy.take_profit_pct == 0.25
    assert legacy.target_dte == 30


def test_200dma_required_by_default():
    assert REQUIRE_ABOVE_200DMA is True


def test_buffett_risk_budget_allows_one_lot_five_wide():
    # $5 wide, $0.67 credit → max loss ≈ $433 on $100k = 0.43% < 1%
    out = evaluate_buffett_risk_budget(
        equity=100_000.0, wing_width=5.0, credit=0.67, quantity=1
    )
    assert out["allowed"] is True
    assert out["max_loss"] < 500


def test_buffett_risk_budget_blocks_oversized():
    out = evaluate_buffett_risk_budget(
        equity=10_000.0, wing_width=5.0, credit=0.10, quantity=3
    )
    assert out["allowed"] is False
    assert any("exceeds" in b for b in out["blockers"])
