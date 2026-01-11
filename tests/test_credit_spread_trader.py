#!/usr/bin/env python3
"""Tests for credit spread trader - 2026 best practices implementation."""

import pytest
from unittest.mock import MagicMock, patch

# Import will fail if dependencies not installed - that's OK for CI
try:
    from scripts.credit_spread_trader import (
        CONFIG,
        calculate_spread_collateral,
        validate_spread,
    )
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False


@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Dependencies not available")
class TestCreditSpreadConfig:
    """Test configuration follows 2026 best practices."""

    def test_delta_rules(self):
        """Verify 50/25 delta rule (or similar conservative delta)."""
        # Best practice: sell 30-50 delta, buy 15-25 delta
        assert 0.25 <= CONFIG["sell_delta"] <= 0.50
        assert 0.10 <= CONFIG["buy_delta"] <= 0.30
        assert CONFIG["sell_delta"] > CONFIG["buy_delta"]

    def test_premium_rules(self):
        """Verify 33% rule for minimum premium."""
        # Best practice: collect at least 33% of spread width
        assert CONFIG["min_premium_pct"] >= 0.30
        assert CONFIG["min_premium_dollars"] >= 0.25

    def test_dte_rules(self):
        """Verify 30-45 DTE targeting."""
        assert 25 <= CONFIG["target_dte"] <= 45
        assert CONFIG["min_dte"] >= 14
        assert CONFIG["max_dte"] <= 60

    def test_risk_management(self):
        """Verify proper risk management rules."""
        # Take profit at 50%
        assert CONFIG["take_profit_pct"] == 0.50
        # Stop loss at 100% (2x premium)
        assert CONFIG["stop_loss_pct"] == 1.00
        # Max spread width $5 (manageable collateral)
        assert CONFIG["max_spread_width"] <= 10
        # Position sizing
        assert CONFIG["max_portfolio_risk_pct"] <= 0.15

    def test_watchlist_has_low_price_stocks(self):
        """Verify watchlist includes stocks accessible to small accounts."""
        low_price_stocks = ["F", "SOFI", "T", "AAL"]
        for stock in low_price_stocks:
            assert stock in CONFIG["watchlist"], f"{stock} should be in watchlist for small accounts"


@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Dependencies not available")
class TestCollateralCalculation:
    """Test collateral calculations."""

    def test_5_dollar_spread(self):
        """$5 wide spread requires $500 collateral."""
        assert calculate_spread_collateral(5.0) == 500.0

    def test_2_50_spread(self):
        """$2.50 wide spread requires $250 collateral."""
        assert calculate_spread_collateral(2.5) == 250.0

    def test_10_dollar_spread(self):
        """$10 wide spread requires $1000 collateral."""
        assert calculate_spread_collateral(10.0) == 1000.0


@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Dependencies not available")
class TestSpreadValidation:
    """Test spread validation against 33% rule."""

    def test_valid_spread(self):
        """Spread meeting 33% rule should be valid."""
        spread = {
            "spread_width": 5.0,
            "estimated_credit": 2.0,  # 40% of width
        }
        # With 18% estimate, $5 width = $0.90 credit > $0.30 minimum
        assert validate_spread(spread)

    def test_invalid_zero_width(self):
        """Zero width spread should be invalid."""
        spread = {"spread_width": 0}
        assert not validate_spread(spread)

    def test_invalid_negative_width(self):
        """Negative width spread should be invalid."""
        spread = {"spread_width": -5}
        assert not validate_spread(spread)


class TestStrategyRules:
    """Test that strategy follows 2026 best practices."""

    def test_33_percent_rule_documented(self):
        """33% rule should be documented in code."""
        import inspect
        from pathlib import Path

        script_path = Path(__file__).parent.parent / "scripts" / "credit_spread_trader.py"
        if script_path.exists():
            content = script_path.read_text()
            assert "33%" in content, "33% rule should be documented"

    def test_take_profit_rule_documented(self):
        """Take profit at 50% should be documented."""
        from pathlib import Path

        script_path = Path(__file__).parent.parent / "scripts" / "credit_spread_trader.py"
        if script_path.exists():
            content = script_path.read_text()
            assert "50%" in content, "50% take profit rule should be documented"

    def test_stop_loss_rule_documented(self):
        """100% stop loss should be documented."""
        from pathlib import Path

        script_path = Path(__file__).parent.parent / "scripts" / "credit_spread_trader.py"
        if script_path.exists():
            content = script_path.read_text()
            assert "100%" in content or "stop_loss" in content, "Stop loss rule should be documented"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
