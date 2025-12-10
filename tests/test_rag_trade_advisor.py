"""
Test RAG Trade Advisor Integration

Validates that RAG knowledge is properly integrated into trading decisions.
"""

import pytest
from src.trading.rag_trade_advisor import RAGTradeAdvisor


class TestRAGTradeAdvisor:
    """Test suite for RAG Trade Advisor."""

    @pytest.fixture
    def advisor(self):
        """Create RAG advisor instance."""
        return RAGTradeAdvisor()

    def test_advisor_initialization(self, advisor):
        """Test that advisor initializes with knowledge chunks."""
        assert advisor is not None
        assert advisor.retriever is not None
        assert len(advisor.mcmillan_chunks) > 0
        assert len(advisor.tastytrade_chunks) > 0

    def test_validate_strategy_high_iv_reject_long_call(self, advisor):
        """Test that long calls are rejected in high IV (critical!)."""
        is_valid, result = advisor.validate_strategy_vs_iv("long_call", iv_rank=85)

        assert not is_valid, "Long calls should be REJECTED in high IV"
        assert result["rejection_reason"] is not None
        assert "forbidden" in result["rejection_reason"].lower()
        assert result["regime"] == "very_high"

    def test_validate_strategy_high_iv_approve_credit_spread(self, advisor):
        """Test that credit spreads are approved in high IV."""
        is_valid, result = advisor.validate_strategy_vs_iv("credit_spread", iv_rank=65)

        assert is_valid, "Credit spreads should be APPROVED in high IV"
        assert result["rejection_reason"] is None
        assert result["regime"] in ["high", "very_high"]

    def test_validate_strategy_low_iv_reject_iron_condor(self, advisor):
        """Test that iron condors are rejected in low IV."""
        is_valid, result = advisor.validate_strategy_vs_iv("iron_condor", iv_rank=15)

        assert not is_valid, "Iron condors should be REJECTED in low IV"
        assert result["rejection_reason"] is not None
        assert "forbidden" in result["rejection_reason"].lower()
        assert result["regime"] == "very_low"

    def test_validate_strategy_low_iv_approve_long_put(self, advisor):
        """Test that long puts are approved in low IV."""
        is_valid, result = advisor.validate_strategy_vs_iv("long_put", iv_rank=18)

        assert is_valid, "Long puts should be APPROVED in low IV"
        assert result["rejection_reason"] is None
        assert result["regime"] in ["very_low", "low"]

    def test_get_trade_advice_high_iv_iron_condor(self, advisor):
        """Test full trade advice for iron condor in high IV."""
        advice = advisor.get_trade_advice(
            ticker="SPY",
            strategy="iron_condor",
            iv_rank=68,
            sentiment="neutral",
            dte=35,
            stock_price=450.0,
            current_iv=0.18,
        )

        assert advice["approved"], "Iron condor should be APPROVED in high IV"
        assert advice["confidence"] > 0.5
        assert advice["rejection_reason"] is None
        assert advice["iv_regime"]["regime"] in ["high", "very_high"]
        assert "iron_condor" in advice["iv_regime"]["allowed_strategies"]

    def test_get_trade_advice_high_iv_long_call_rejected(self, advisor):
        """Test full trade advice for long call in high IV (should reject)."""
        advice = advisor.get_trade_advice(
            ticker="SPY",
            strategy="long_call",
            iv_rank=75,
            sentiment="bullish",
            dte=30,
            stock_price=450.0,
            current_iv=0.22,
        )

        assert not advice["approved"], "Long call should be REJECTED in high IV"
        assert advice["rejection_reason"] is not None
        assert "forbidden" in advice["rejection_reason"].lower()
        assert advice["iv_regime"]["regime"] in ["high", "very_high"]

    def test_get_trade_advice_optimal_dte(self, advisor):
        """Test that optimal DTE (30-45) increases confidence."""
        advice_optimal = advisor.get_trade_advice(
            ticker="SPY",
            strategy="iron_condor",
            iv_rank=60,
            sentiment="neutral",
            dte=35,
        )

        advice_suboptimal = advisor.get_trade_advice(
            ticker="SPY",
            strategy="iron_condor",
            iv_rank=60,
            sentiment="neutral",
            dte=15,
        )

        assert advice_optimal["confidence"] > advice_suboptimal["confidence"]
        assert len(advice_suboptimal["warnings"]) > 0

    def test_get_mcmillan_rule_covered_call(self, advisor):
        """Test retrieval of McMillan's covered call rules."""
        rule = advisor.get_mcmillan_rule("covered_call")

        assert rule != "", "Should find McMillan rule for covered call"
        assert "covered" in rule.lower() or "call" in rule.lower()

    def test_get_mcmillan_rule_stop_loss(self, advisor):
        """Test retrieval of McMillan's stop-loss rules."""
        rule = advisor.get_mcmillan_rule("stop_loss")

        assert rule != "", "Should find McMillan rule for stop loss"
        assert "stop" in rule.lower() or "loss" in rule.lower()

    def test_get_tastytrade_rule_iron_condor(self, advisor):
        """Test retrieval of TastyTrade iron condor rules."""
        rule = advisor.get_tastytrade_rule("iron_condor", dte=35, iv_rank=60)

        assert rule != "", "Should find TastyTrade rule for iron condor"
        assert "condor" in rule.lower() or "tastytrade" in rule.lower()

    def test_get_trade_attribution(self, advisor):
        """Test trade attribution metadata generation."""
        advice = advisor.get_trade_advice(
            ticker="SPY",
            strategy="iron_condor",
            iv_rank=65,
            sentiment="neutral",
            dte=30,
        )

        attribution = advisor.get_trade_attribution(advice)

        assert attribution["ticker"] == "SPY"
        assert attribution["strategy"] == "iron_condor"
        assert attribution["approved"] == advice["approved"]
        assert "iv_regime" in attribution
        assert "mcmillan_used" in attribution
        assert "tastytrade_used" in attribution


class TestRAGIntegrationScenarios:
    """Test real-world trading scenarios."""

    @pytest.fixture
    def advisor(self):
        """Create RAG advisor instance."""
        return RAGTradeAdvisor()

    def test_scenario_earnings_high_iv_sell_premium(self, advisor):
        """Scenario: Earnings coming up, IV spiked to 80%."""
        advice = advisor.get_trade_advice(
            ticker="AAPL",
            strategy="strangle_short",
            iv_rank=80,
            sentiment="neutral",
            dte=7,
            stock_price=180.0,
            current_iv=0.35,
        )

        # Short strangle should be approved in very high IV
        assert advice["approved"] or "dte" in advice.get("rejection_reason", "").lower()
        assert advice["iv_regime"]["regime"] == "very_high"

    def test_scenario_market_crash_low_iv_buy_puts(self, advisor):
        """Scenario: After crash, IV collapsed to 15%."""
        advice = advisor.get_trade_advice(
            ticker="SPY",
            strategy="long_put",
            iv_rank=15,
            sentiment="bearish",
            dte=45,
            stock_price=400.0,
            current_iv=0.12,
        )

        # Long puts should be approved in very low IV
        assert advice["approved"], "Long puts should be approved in low IV"
        assert advice["iv_regime"]["regime"] == "very_low"

    def test_scenario_sideways_market_neutral_iv(self, advisor):
        """Scenario: Market range-bound, IV at 50%."""
        advice = advisor.get_trade_advice(
            ticker="SPY",
            strategy="iron_condor",
            iv_rank=50,
            sentiment="neutral",
            dte=35,
            stock_price=450.0,
            current_iv=0.15,
        )

        # Iron condor should be approved in neutral IV
        assert advice["approved"], "Iron condor should work in neutral IV"
        assert advice["iv_regime"]["regime"] in ["neutral", "high"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
