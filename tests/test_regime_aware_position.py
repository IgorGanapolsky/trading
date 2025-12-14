"""Tests for Regime-Aware Position Sizing Anomaly Detector.

Test cases cover:
1. All regime classifications (CALM, NORMAL, VOLATILE, EXTREME)
2. Position size violations and safe positions
3. Risk score calculation
4. Multiple position checking
5. Edge cases (zero portfolio, extreme ATR values)

Author: Trading System CTO
Created: 2025-12-11
"""

import pytest
from src.verification.regime_aware_position_anomaly import (
    RegimeAwarePositionChecker,
    create_regime_checker,
)


class TestRegimeClassification:
    """Test market regime classification based on ATR."""

    def test_calm_regime_classification(self):
        """Test CALM regime: ATR < 1%."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        assert checker.classify_regime(0.5) == "CALM"
        assert checker.classify_regime(0.8) == "CALM"
        assert checker.classify_regime(0.99) == "CALM"

    def test_normal_regime_classification(self):
        """Test NORMAL regime: ATR 1-2%."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        assert checker.classify_regime(1.0) == "NORMAL"
        assert checker.classify_regime(1.5) == "NORMAL"
        assert checker.classify_regime(1.99) == "NORMAL"

    def test_volatile_regime_classification(self):
        """Test VOLATILE regime: ATR 2-5%."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        assert checker.classify_regime(2.0) == "VOLATILE"
        assert checker.classify_regime(3.5) == "VOLATILE"
        assert checker.classify_regime(4.99) == "VOLATILE"

    def test_extreme_regime_classification(self):
        """Test EXTREME regime: ATR > 5%."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        assert checker.classify_regime(5.0) == "EXTREME"
        assert checker.classify_regime(8.0) == "EXTREME"
        assert checker.classify_regime(15.0) == "EXTREME"
        assert checker.classify_regime(100.0) == "EXTREME"


class TestPositionLimits:
    """Test position size limits for each regime."""

    def test_calm_regime_max_position(self):
        """Test CALM regime: 8% max position."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)
        assert checker.get_max_position_pct("CALM") == 0.08

    def test_normal_regime_max_position(self):
        """Test NORMAL regime: 5% max position."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)
        assert checker.get_max_position_pct("NORMAL") == 0.05

    def test_volatile_regime_max_position(self):
        """Test VOLATILE regime: 3% max position."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)
        assert checker.get_max_position_pct("VOLATILE") == 0.03

    def test_extreme_regime_max_position(self):
        """Test EXTREME regime: 1% max position."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)
        assert checker.get_max_position_pct("EXTREME") == 0.01

    def test_unknown_regime_fallback(self):
        """Test unknown regime defaults to 1% (safest)."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)
        assert checker.get_max_position_pct("UNKNOWN") == 0.01


class TestPositionChecking:
    """Test position size violation detection."""

    def test_safe_position_calm_regime(self):
        """Test safe position in CALM regime."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="SPY",
            amount=500,  # 5% of portfolio
            atr_pct=0.8,  # CALM regime (< 1%)
        )

        assert result.safe is True
        assert result.regime == "CALM"
        assert result.max_allowed == 0.08
        assert result.actual_pct == 0.05
        assert result.risk_score < 30
        assert result.violation_severity == "none"
        assert "✅ SAFE" in result.recommendation

    def test_safe_position_normal_regime(self):
        """Test safe position in NORMAL regime."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="QQQ",
            amount=400,  # 4% of portfolio
            atr_pct=1.5,  # NORMAL regime (1-2%)
        )

        assert result.safe is True
        assert result.regime == "NORMAL"
        assert result.max_allowed == 0.05
        assert result.actual_pct == 0.04
        assert result.risk_score < 30
        assert "✅ SAFE" in result.recommendation

    def test_violation_volatile_regime(self):
        """Test position violation in VOLATILE regime."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="TSLA",
            amount=1000,  # 10% of portfolio
            atr_pct=3.5,  # VOLATILE regime (2-5%)
        )

        assert result.safe is False
        assert result.regime == "VOLATILE"
        assert result.max_allowed == 0.03
        assert result.actual_pct == 0.10
        assert result.risk_score >= 50
        assert result.violation_severity in ["major", "critical"]
        assert "VIOLATION" in result.recommendation

    def test_violation_extreme_regime(self):
        """Test position violation in EXTREME regime."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="GME",
            amount=500,  # 5% of portfolio
            atr_pct=8.0,  # EXTREME regime (> 5%)
        )

        assert result.safe is False
        assert result.regime == "EXTREME"
        assert result.max_allowed == 0.01
        assert result.actual_pct == 0.05
        assert result.risk_score >= 50
        assert "VIOLATION" in result.recommendation

    def test_max_position_at_limit_calm(self):
        """Test position exactly at limit in CALM regime."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="SPY",
            amount=800,  # Exactly 8% (CALM limit)
            atr_pct=0.5,  # CALM regime
        )

        assert result.safe is True
        assert result.actual_pct == 0.08
        assert result.max_allowed == 0.08
        assert result.risk_score <= 30

    def test_position_just_over_limit(self):
        """Test position just over limit triggers violation."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="QQQ",
            amount=501,  # 5.01% in NORMAL regime (5% limit)
            atr_pct=1.5,  # NORMAL regime
        )

        assert result.safe is False
        assert result.actual_pct > result.max_allowed


class TestRiskScoring:
    """Test risk score calculation."""

    def test_risk_score_safe_small_position(self):
        """Test low risk score for small safe positions."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="SPY",
            amount=200,  # 2% (well under 5% NORMAL limit)
            atr_pct=1.5,  # NORMAL regime
        )

        assert result.safe is True
        assert 0 <= result.risk_score <= 30

    def test_risk_score_safe_at_limit(self):
        """Test moderate risk score at position limit."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="SPY",
            amount=500,  # Exactly 5% (NORMAL limit)
            atr_pct=1.5,  # NORMAL regime
        )

        assert result.safe is True
        assert result.risk_score <= 30

    def test_risk_score_minor_violation(self):
        """Test moderate risk score for minor violations."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="QQQ",
            amount=600,  # 6% (20% over 5% limit)
            atr_pct=1.5,  # NORMAL regime
        )

        assert result.safe is False
        assert 50 <= result.risk_score < 75
        assert result.violation_severity in ["minor", "major"]

    def test_risk_score_major_violation(self):
        """Test high risk score for major violations."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="TSLA",
            amount=1500,  # 15% (400% over 3% VOLATILE limit)
            atr_pct=3.5,  # VOLATILE regime
        )

        assert result.safe is False
        assert result.risk_score >= 75
        assert result.violation_severity == "critical"

    def test_risk_score_extreme_violation(self):
        """Test maximum risk score for extreme violations."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="GME",
            amount=5000,  # 50% (4900% over 1% EXTREME limit!)
            atr_pct=10.0,  # EXTREME regime
        )

        assert result.safe is False
        assert result.risk_score == 100.0  # Capped at 100
        assert result.violation_severity == "critical"


class TestMultiplePositions:
    """Test checking multiple positions."""

    def test_all_safe_positions(self):
        """Test all positions within limits."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        positions = [
            {"symbol": "SPY", "amount": 500, "atr_pct": 0.8},  # CALM, safe
            {"symbol": "QQQ", "amount": 400, "atr_pct": 1.5},  # NORMAL, safe
            {"symbol": "BND", "amount": 200, "atr_pct": 3.0},  # VOLATILE, safe
        ]

        summary = checker.check_multiple_positions(positions)

        assert summary["total_positions"] == 3
        assert summary["safe_count"] == 3
        assert summary["violation_count"] == 0
        assert summary["passed"] is True
        assert summary["total_risk_score"] < 30

    def test_mixed_positions(self):
        """Test mix of safe and violating positions."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        positions = [
            {"symbol": "SPY", "amount": 500, "atr_pct": 0.8},  # CALM, safe
            {"symbol": "TSLA", "amount": 1000, "atr_pct": 4.0},  # VOLATILE, VIOLATION
            {"symbol": "GME", "amount": 1500, "atr_pct": 8.0},  # EXTREME, VIOLATION
        ]

        summary = checker.check_multiple_positions(positions)

        assert summary["total_positions"] == 3
        assert summary["safe_count"] == 1
        assert summary["violation_count"] == 2
        assert summary["passed"] is False
        assert len(summary["violations"]) == 2

    def test_all_violations(self):
        """Test all positions violating limits."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        positions = [
            {"symbol": "TSLA", "amount": 1000, "atr_pct": 4.0},  # VOLATILE, VIOLATION
            {"symbol": "GME", "amount": 1500, "atr_pct": 8.0},  # EXTREME, VIOLATION
        ]

        summary = checker.check_multiple_positions(positions)

        assert summary["total_positions"] == 2
        assert summary["safe_count"] == 0
        assert summary["violation_count"] == 2
        assert summary["passed"] is False
        assert summary["total_risk_score"] > 50


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_portfolio_value(self):
        """Test handling of zero portfolio value."""
        checker = RegimeAwarePositionChecker(portfolio_value=0)

        result = checker.check_position(
            symbol="SPY",
            amount=500,
            atr_pct=1.5,
        )

        # Should handle gracefully (actual_pct will be 0)
        assert result.actual_pct == 0.0

    def test_negative_atr(self):
        """Test handling of negative ATR (should take absolute value)."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="SPY",
            amount=500,
            atr_pct=-1.0,  # Invalid but should handle
        )

        # Negative ATR is converted to absolute value (|-1.0| = 1.0)
        # 1.0% ATR falls into NORMAL regime (1-2% range)
        # (In practice, ATR can't be negative, but code handles it defensively)
        assert result.regime == "NORMAL"

    def test_very_large_atr(self):
        """Test handling of extremely large ATR."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="MEME",
            amount=50,  # Tiny position
            atr_pct=50.0,  # 50% ATR (crisis level)
        )

        assert result.regime == "EXTREME"
        assert result.max_allowed == 0.01

    def test_zero_amount_position(self):
        """Test zero position size."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="SPY",
            amount=0,
            atr_pct=1.5,
        )

        assert result.safe is True
        assert result.actual_pct == 0.0
        assert result.risk_score == 0.0

    def test_rag_disabled(self):
        """Test with RAG queries disabled."""
        checker = RegimeAwarePositionChecker(
            portfolio_value=10000,
            enable_rag_query=False,
        )

        result = checker.check_position(
            symbol="TSLA",
            amount=1000,  # Violation
            atr_pct=4.0,
        )

        # Should still work, just no RAG query
        assert result.safe is False


class TestResultSerialization:
    """Test result dictionary conversion."""

    def test_to_dict_conversion(self):
        """Test converting result to dictionary."""
        checker = RegimeAwarePositionChecker(portfolio_value=10000)

        result = checker.check_position(
            symbol="SPY",
            amount=500,
            atr_pct=1.5,
        )

        result_dict = checker.to_dict(result)

        assert isinstance(result_dict, dict)
        assert "safe" in result_dict
        assert "risk_score" in result_dict
        assert "regime" in result_dict
        assert "max_allowed_pct" in result_dict
        assert "actual_pct" in result_dict
        assert "recommendation" in result_dict
        assert "atr_pct" in result_dict
        assert "violation_severity" in result_dict

        # Check formatting
        assert isinstance(result_dict["risk_score"], float)
        assert result_dict["max_allowed_pct"] == 5.0  # 5% as percentage
        assert result_dict["actual_pct"] == 5.0  # 5% as percentage


class TestFactoryFunction:
    """Test factory function."""

    def test_create_regime_checker_defaults(self):
        """Test creating checker with defaults."""
        checker = create_regime_checker()

        assert checker.portfolio_value == 10000.0
        assert checker.enable_rag_query is True

    def test_create_regime_checker_custom_portfolio(self):
        """Test creating checker with custom portfolio."""
        checker = create_regime_checker(portfolio_value=50000)

        assert checker.portfolio_value == 50000.0


class TestLatencyRequirement:
    """Test that checks complete within 100ms latency requirement."""

    def test_single_check_latency(self):
        """Test single position check completes quickly."""
        import time

        checker = RegimeAwarePositionChecker(
            portfolio_value=10000,
            enable_rag_query=False,  # Disable RAG for pure check latency
        )

        start = time.time()
        result = checker.check_position(
            symbol="SPY",
            amount=500,
            atr_pct=1.5,
        )
        elapsed_ms = (time.time() - start) * 1000

        # Should complete in < 100ms
        assert elapsed_ms < 100
        assert result is not None

    def test_multiple_check_latency(self):
        """Test multiple position checks complete quickly."""
        import time

        checker = RegimeAwarePositionChecker(
            portfolio_value=10000,
            enable_rag_query=False,
        )

        positions = [{"symbol": f"SYM{i}", "amount": 500, "atr_pct": 1.5} for i in range(10)]

        start = time.time()
        summary = checker.check_multiple_positions(positions)
        elapsed_ms = (time.time() - start) * 1000

        # Should complete in < 100ms for 10 positions
        assert elapsed_ms < 100
        assert summary["total_positions"] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
