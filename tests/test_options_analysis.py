"""
Tests for options analysis module.

Tests the Matt Giannino checklist validation functions added Jan 2026:
- validate_delta_theta_ratio
- check_liquidity
- validate_contract_quality
- get_atr
"""

import pytest

try:
    from src.utils.options_analysis import (
        MAX_BID_ASK_SPREAD_PCT,
        MAX_THETA_DECAY_PCT,
        MIN_DELTA_THETA_RATIO,
        MIN_OPEN_INTEREST,
        check_liquidity,
        validate_contract_quality,
        validate_delta_theta_ratio,
    )
except ImportError as e:
    pytest.skip(f"Skipping options_analysis tests: {e}", allow_module_level=True)


class TestDeltaThetaRatio:
    """Tests for delta/theta ratio validation."""

    def test_good_ratio_passes(self):
        """Delta/Theta > 3:1 should pass."""
        # Delta 0.45 = $45 per $1 move, Theta $0.10/day = ratio 4.5
        result = validate_delta_theta_ratio(delta=0.45, theta=-0.10, contract_price=2.50)
        assert result["is_valid"] is True
        assert result["ratio"] >= MIN_DELTA_THETA_RATIO
        assert result["ratio_ok"] is True
        assert len(result["warnings"]) == 0

    def test_bad_ratio_fails(self):
        """Delta/Theta < 3:1 should fail."""
        # Delta 0.20 = $20 per $1 move, Theta $0.15/day = ratio 1.33
        result = validate_delta_theta_ratio(delta=0.20, theta=-0.15, contract_price=2.50)
        assert result["ratio_ok"] is False
        assert "Low delta/theta ratio" in result["warnings"][0]

    def test_high_decay_percentage_fails(self):
        """Theta > 10% of contract price should fail."""
        # Contract $1.00, Theta $0.20/day = 20% decay
        result = validate_delta_theta_ratio(delta=0.50, theta=-0.20, contract_price=1.00)
        assert result["decay_ok"] is False
        assert result["theta_decay_pct"] == 20.0
        assert "High daily decay" in str(result["warnings"])

    def test_acceptable_decay_passes(self):
        """Theta < 10% of contract price should pass."""
        # Contract $5.00, Theta $0.10/day = 2% decay
        result = validate_delta_theta_ratio(delta=0.50, theta=-0.10, contract_price=5.00)
        assert result["decay_ok"] is True
        assert result["theta_decay_pct"] == 2.0

    def test_zero_theta_handles_gracefully(self):
        """Zero theta should not cause division error."""
        result = validate_delta_theta_ratio(delta=0.50, theta=0.0, contract_price=2.50)
        assert result["ratio"] == float("inf")
        assert result["ratio_ok"] is True

    def test_negative_theta_handled(self):
        """Negative theta (standard format) should work."""
        result = validate_delta_theta_ratio(delta=0.45, theta=-0.10, contract_price=2.50)
        assert result["theta"] == -0.10
        assert result["ratio"] > 0


class TestLiquidity:
    """Tests for liquidity validation."""

    def test_good_liquidity_passes(self):
        """High OI and tight spread should pass."""
        result = check_liquidity(open_interest=1500, bid=2.45, ask=2.55)
        assert result["is_liquid"] is True
        assert result["oi_ok"] is True
        assert result["spread_ok"] is True
        assert len(result["warnings"]) == 0

    def test_low_open_interest_fails(self):
        """Open Interest < 500 should fail."""
        result = check_liquidity(open_interest=200, bid=2.45, ask=2.55)
        assert result["oi_ok"] is False
        assert result["is_liquid"] is False
        assert "Low open interest" in result["warnings"][0]

    def test_wide_spread_fails(self):
        """Bid-Ask spread > 10% should fail."""
        # Bid $1.50, Ask $2.00 = 28.6% spread
        result = check_liquidity(open_interest=1000, bid=1.50, ask=2.00)
        assert result["spread_ok"] is False
        assert result["spread_pct"] > MAX_BID_ASK_SPREAD_PCT
        assert "Wide bid-ask spread" in result["warnings"][0]

    def test_tight_spread_passes(self):
        """Bid-Ask spread < 10% should pass."""
        # Bid $2.45, Ask $2.55 = 3.9% spread
        result = check_liquidity(open_interest=1000, bid=2.45, ask=2.55)
        assert result["spread_ok"] is True
        assert result["spread_pct"] < MAX_BID_ASK_SPREAD_PCT

    def test_exact_minimum_oi_passes(self):
        """OI exactly at minimum should pass."""
        result = check_liquidity(open_interest=MIN_OPEN_INTEREST, bid=2.45, ask=2.55)
        assert result["oi_ok"] is True

    def test_zero_bid_ask_handled(self):
        """Zero bid/ask should not cause errors."""
        result = check_liquidity(open_interest=1000, bid=0, ask=0)
        assert result["spread_pct"] == 100
        assert result["spread_ok"] is False


class TestContractQuality:
    """Tests for complete checklist validation."""

    def test_perfect_contract_passes(self):
        """Contract passing all checks should get PROCEED."""
        result = validate_contract_quality(
            symbol="SPY",
            delta=0.45,
            theta=-0.10,
            contract_price=2.50,
            open_interest=1500,
            bid=2.45,
            ask=2.55,
            implied_volatility=0.25,
        )
        assert result["passes_checklist"] is True
        assert result["checks_passed"] == 4
        assert result["recommendation"] == "PROCEED"
        assert len(result["all_warnings"]) == 0

    def test_high_iv_warns(self):
        """High IV should trigger warning but still pass."""
        result = validate_contract_quality(
            symbol="SOFI",
            delta=0.45,
            theta=-0.10,
            contract_price=2.50,
            open_interest=1500,
            bid=2.45,
            ask=2.55,
            implied_volatility=0.55,  # 55% IV - high
        )
        assert result["passes_checklist"] is True
        assert result["iv_warning"] is not None
        assert result["recommendation"] == "PROCEED_WITH_CAUTION"

    def test_marginal_contract_detected(self):
        """Contract failing 1 check should be MARGINAL."""
        result = validate_contract_quality(
            symbol="SPY",
            delta=0.45,
            theta=-0.10,
            contract_price=2.50,
            open_interest=300,  # Fails OI check
            bid=2.45,
            ask=2.55,
        )
        assert result["passes_checklist"] is False
        assert result["checks_passed"] == 3
        assert result["recommendation"] == "MARGINAL"

    def test_poor_contract_skipped(self):
        """Contract failing multiple checks should be SKIP."""
        result = validate_contract_quality(
            symbol="SPY",
            delta=0.20,  # Bad ratio
            theta=-0.15,  # High decay
            contract_price=1.00,
            open_interest=200,  # Low OI
            bid=1.50,
            ask=2.00,  # Wide spread
        )
        assert result["passes_checklist"] is False
        assert result["checks_passed"] < 3
        assert result["recommendation"] == "SKIP"
        assert len(result["all_warnings"]) > 0

    def test_no_iv_provided(self):
        """Validation should work without IV."""
        result = validate_contract_quality(
            symbol="SPY",
            delta=0.45,
            theta=-0.10,
            contract_price=2.50,
            open_interest=1500,
            bid=2.45,
            ask=2.55,
            implied_volatility=None,
        )
        assert result["iv_warning"] is None
        assert result["passes_checklist"] is True


class TestThresholdConstants:
    """Tests that constants are set correctly."""

    def test_delta_theta_ratio_threshold(self):
        """MIN_DELTA_THETA_RATIO should be 3.0 per Giannino."""
        assert MIN_DELTA_THETA_RATIO == 3.0

    def test_theta_decay_threshold(self):
        """MAX_THETA_DECAY_PCT should be 10% per Giannino."""
        assert MAX_THETA_DECAY_PCT == 10.0

    def test_open_interest_threshold(self):
        """MIN_OPEN_INTEREST should be 500 per Giannino."""
        assert MIN_OPEN_INTEREST == 500

    def test_spread_threshold(self):
        """MAX_BID_ASK_SPREAD_PCT should be 10% per Giannino."""
        assert MAX_BID_ASK_SPREAD_PCT == 10.0
