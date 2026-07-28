"""Unit tests verifying the 5-point roadmap requirements to achieve $1,000/mo after-tax profit."""

from __future__ import annotations

from src.core.trading_profiles import (
    IRON_CONDOR_PROFILE_REGISTRY,
    PUT_CREDIT_PROFILE_REGISTRY,
    get_iron_condor_profile,
    get_put_credit_profile,
)
from src.risk.put_credit_regime import evaluate_regime_gate
from src.risk.trade_gateway import TradeGateway


def test_xsp_section_1256_profiles_registered():
    """Verify XSP is registered in strategy profiles for Section 1256 tax treatment."""
    assert "xsp-core" in IRON_CONDOR_PROFILE_REGISTRY
    assert "xsp-put-credit" in PUT_CREDIT_PROFILE_REGISTRY

    ic_xsp = get_iron_condor_profile("xsp-core")
    assert ic_xsp.underlying == "XSP"

    pc_xsp = get_put_credit_profile("xsp-put-credit")
    assert pc_xsp.underlying == "XSP"


def test_trade_gateway_allows_xsp_and_spy():
    """Verify TradeGateway allows XSP and SPY index/ETF tickers."""
    gateway = TradeGateway()
    allowed_tickers = gateway.ALLOWED_TICKERS
    assert "XSP" in allowed_tickers
    assert "SPY" in allowed_tickers


def test_regime_gate_enforces_iv_rank_and_vix_limits():
    """Verify evaluate_regime_gate enforces IV rank >= 30 and VIX <= 30."""
    # Good snapshot
    good_snapshot = {
        "vix": 18.5,
        "iv_rank_proxy": 35.0,
        "spy_above_200dma": True,
    }
    result_good = evaluate_regime_gate(good_snapshot, min_iv_rank=30.0, max_vix=30.0)
    assert result_good["allowed"] is True
    assert len(result_good["blockers"]) == 0

    # Low IV Rank snapshot (< 30)
    low_iv_snapshot = {
        "vix": 18.5,
        "iv_rank_proxy": 20.0,
        "spy_above_200dma": True,
    }
    result_low_iv = evaluate_regime_gate(low_iv_snapshot, min_iv_rank=30.0, max_vix=30.0)
    assert result_low_iv["allowed"] is False
    assert any("IV rank proxy" in b for b in result_low_iv["blockers"])

    # High VIX snapshot (> 30)
    high_vix_snapshot = {
        "vix": 35.0,
        "iv_rank_proxy": 40.0,
        "spy_above_200dma": True,
    }
    result_high_vix = evaluate_regime_gate(high_vix_snapshot, min_iv_rank=30.0, max_vix=30.0)
    assert result_high_vix["allowed"] is False
    assert any("VIX" in b for b in result_high_vix["blockers"])


def test_after_tax_profit_math_requirements():
    """Verify mathematical model for $1,000/mo net post-tax profit."""
    net_monthly_target = 1000.0
    net_annual_target = net_monthly_target * 12

    # Case A: Standard Short-Term Capital Gains Tax (30%)
    tax_rate_spy = 0.30
    pre_tax_annual_spy = net_annual_target / (1 - tax_rate_spy)
    pre_tax_monthly_spy = pre_tax_annual_spy / 12
    assert abs(pre_tax_monthly_spy - 1428.57) < 0.1
    assert abs(pre_tax_annual_spy - 17142.86) < 0.1

    # Case B: Section 1256 Blended Tax Rate (20%)
    tax_rate_xsp = 0.20
    pre_tax_annual_xsp = net_annual_target / (1 - tax_rate_xsp)
    pre_tax_monthly_xsp = pre_tax_annual_xsp / 12
    assert abs(pre_tax_monthly_xsp - 1250.00) < 0.1
    assert abs(pre_tax_annual_xsp - 15000.00) < 0.1

    # Required capital at 20% net ROC on XSP
    target_roc = 0.20
    required_capital_xsp = pre_tax_annual_xsp / target_roc
    assert required_capital_xsp == 75000.00
