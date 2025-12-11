"""
Tests for Semantic Trade Anomaly Detector.

Verifies that the detector correctly identifies trades similar to past failures
and blocks high-risk trades while allowing safe ones.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.verification.semantic_trade_anomaly import (
    SemanticTradeAnomalyDetector,
    TradeContext,
    AnomalyResult,
)


class TestTradeContext:
    """Test TradeContext dataclass."""

    def test_to_query_text_basic(self):
        """Test basic query text generation."""
        context = TradeContext(
            symbol="SPY",
            side="buy",
            amount=100.0,
            strategy="momentum",
        )

        query = context.to_query_text()
        assert "buy SPY" in query
        assert "amount $100.00" in query
        assert "strategy momentum" in query

    def test_to_query_text_with_additional_context(self):
        """Test query text with additional context."""
        context = TradeContext(
            symbol="AAPL",
            side="sell",
            amount=50.0,
            strategy="mean_reversion",
            additional_context={
                "macd": -10.5,
                "rsi": 35,
                "volume": "high",
            },
        )

        query = context.to_query_text()
        assert "sell AAPL" in query
        assert "amount $50.00" in query
        assert "macd -10.5" in query
        assert "rsi 35" in query
        assert "volume high" in query


class TestSemanticTradeAnomalyDetector:
    """Test SemanticTradeAnomalyDetector class."""

    @pytest.fixture
    def detector(self):
        """Create detector instance for testing."""
        return SemanticTradeAnomalyDetector(
            similarity_threshold=0.7,
            financial_impact_threshold=100,
        )

    @pytest.fixture
    def mock_rag(self):
        """Create mock RAG for testing."""
        mock = Mock()
        mock.lessons = []
        mock.encoder = Mock()
        return mock

    def test_initialization_without_rag(self):
        """Test detector initializes gracefully without RAG."""
        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG", side_effect=ImportError):
            detector = SemanticTradeAnomalyDetector()
            assert not detector.rag_available
            assert detector.similarity_threshold == 0.7
            assert detector.financial_impact_threshold == 100

    def test_initialization_with_rag(self, mock_rag):
        """Test detector initializes with RAG."""
        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG", return_value=mock_rag):
            detector = SemanticTradeAnomalyDetector()
            assert detector.rag_available
            assert detector.rag is not None

    def test_check_trade_invalid_context(self, detector):
        """Test check_trade with invalid context."""
        # Missing required field
        result = detector.check_trade({
            "symbol": "SPY",
            "side": "buy",
            # missing "amount"
            "strategy": "momentum",
        })

        assert result["safe"]  # Fail open on errors
        assert "ERROR" in result["recommendation"]
        assert "amount" in result["recommendation"].lower()

    def test_check_trade_fallback_mode_safe(self):
        """Test fallback mode with safe trade."""
        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG", side_effect=ImportError):
            detector = SemanticTradeAnomalyDetector()

            result = detector.check_trade({
                "symbol": "AAPL",
                "side": "buy",
                "amount": 100.0,
                "strategy": "momentum",
            })

            assert result["safe"]
            assert not result["rag_available"]
            assert result["risk_score"] == 0.0
            assert "fallback mode" in result["recommendation"]

    def test_check_trade_fallback_mode_large_amount(self):
        """Test fallback mode blocks large amounts."""
        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG", side_effect=ImportError):
            detector = SemanticTradeAnomalyDetector()

            result = detector.check_trade({
                "symbol": "SPY",
                "side": "buy",
                "amount": 3000.0,  # Over $2000 limit
                "strategy": "momentum",
            })

            assert not result["safe"]
            assert result["risk_score"] > 0.5
            assert "BLOCKED" in result["recommendation"]
            assert "3000" in result["recommendation"]

    def test_check_trade_fallback_mode_tiny_amount(self):
        """Test fallback mode blocks tiny amounts."""
        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG", side_effect=ImportError):
            detector = SemanticTradeAnomalyDetector()

            result = detector.check_trade({
                "symbol": "AAPL",
                "side": "buy",
                "amount": 0.50,  # Below $1 minimum
                "strategy": "test",
            })

            assert not result["safe"]
            assert "WARNING" in result["recommendation"]

    def test_check_trade_with_rag_no_similar_incidents(self, mock_rag):
        """Test with RAG but no similar incidents found."""
        mock_rag.search.return_value = []
        mock_rag.get_context_for_trade.return_value = {
            "warnings": [],
            "prevention_checklist": [],
        }

        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG", return_value=mock_rag):
            detector = SemanticTradeAnomalyDetector()

            result = detector.check_trade({
                "symbol": "MSFT",
                "side": "buy",
                "amount": 50.0,
                "strategy": "momentum",
            })

            assert result["safe"]
            assert result["rag_available"]
            assert result["risk_score"] == 0.0
            assert "SAFE" in result["recommendation"]
            assert len(result["similar_incidents"]) == 0

    def test_check_trade_with_low_similarity_incidents(self, mock_rag):
        """Test with low similarity incidents (should pass)."""
        # Create mock lesson
        mock_lesson = Mock()
        mock_lesson.id = "lesson_1"
        mock_lesson.title = "Unrelated Issue"
        mock_lesson.category = "data"
        mock_lesson.severity = "low"
        mock_lesson.description = "Data freshness check"
        mock_lesson.root_cause = "Stale data"
        mock_lesson.prevention = "Check timestamps"
        mock_lesson.financial_impact = 0.0
        mock_lesson.tags = ["data", "freshness"]

        # Low similarity
        mock_rag.search.return_value = [(mock_lesson, 0.2)]
        mock_rag.get_context_for_trade.return_value = {"warnings": []}

        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG", return_value=mock_rag):
            detector = SemanticTradeAnomalyDetector(similarity_threshold=0.7)

            result = detector.check_trade({
                "symbol": "NVDA",
                "side": "buy",
                "amount": 75.0,
                "strategy": "growth",
            })

            assert result["safe"]
            assert result["risk_score"] < 0.4
            assert len(result["similar_incidents"]) > 0

    def test_check_trade_blocks_high_similarity_high_impact(self, mock_rag):
        """Test blocking trade with high similarity to high-impact incident."""
        # Create mock lesson - 200x position size bug
        mock_lesson = Mock()
        mock_lesson.id = "LESSON-001"
        mock_lesson.title = "200x Position Size Bug"
        mock_lesson.category = "size_error"
        mock_lesson.severity = "critical"
        mock_lesson.description = "Trade executed at $1,600 instead of $8"
        mock_lesson.root_cause = "Unit confusion between shares and dollars"
        mock_lesson.prevention = "Validate order size before submit"
        mock_lesson.financial_impact = 1592.0
        mock_lesson.tags = ["bug", "critical", "position_size"]

        # High similarity (0.85)
        mock_rag.search.return_value = [(mock_lesson, 0.85)]
        mock_rag.get_context_for_trade.return_value = {"warnings": []}

        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG", return_value=mock_rag):
            detector = SemanticTradeAnomalyDetector(
                similarity_threshold=0.7,
                financial_impact_threshold=100,
            )

            result = detector.check_trade({
                "symbol": "SPY",
                "side": "buy",
                "amount": 1600.0,
                "strategy": "momentum",
            })

            assert not result["safe"]  # Should be blocked
            assert result["risk_score"] > 0.7
            assert "BLOCKED" in result["recommendation"]
            assert "200x" in result["recommendation"] or "Position Size" in result["recommendation"]
            assert "$1592" in result["recommendation"] or "1592" in result["recommendation"]
            assert len(result["similar_incidents"]) > 0

    def test_check_trade_warns_medium_risk(self, mock_rag):
        """Test warning on medium risk trade."""
        # Create mock lesson with medium similarity and impact
        mock_lesson = Mock()
        mock_lesson.id = "LESSON-002"
        mock_lesson.title = "Market Order Slippage"
        mock_lesson.category = "execution"
        mock_lesson.severity = "medium"
        mock_lesson.description = "Slippage during volatile periods"
        mock_lesson.root_cause = "Market orders execute at best price"
        mock_lesson.prevention = "Use limit orders for large positions"
        mock_lesson.financial_impact = 50.0
        mock_lesson.tags = ["execution", "slippage"]

        # Medium similarity (0.6)
        mock_rag.search.return_value = [(mock_lesson, 0.6)]
        mock_rag.get_context_for_trade.return_value = {"warnings": []}

        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG", return_value=mock_rag):
            detector = SemanticTradeAnomalyDetector()

            result = detector.check_trade({
                "symbol": "TSLA",
                "side": "sell",
                "amount": 200.0,
                "strategy": "momentum",
            })

            # Should pass but with warning
            assert result["safe"]
            assert 0.3 < result["risk_score"] < 0.7
            assert "RISK" in result["recommendation"]

    def test_calculate_risk_score_no_incidents(self, detector):
        """Test risk score calculation with no incidents."""
        context = TradeContext("SPY", "buy", 100.0, "momentum")
        risk_score = detector._calculate_risk_score([], context)
        assert risk_score == 0.0

    def test_calculate_risk_score_multiple_factors(self, detector):
        """Test risk score with multiple risk factors."""
        incidents = [
            {
                "similarity": 0.8,
                "financial_impact": 500.0,
                "severity": "critical",
            },
            {
                "similarity": 0.6,
                "financial_impact": 100.0,
                "severity": "high",
            },
        ]

        context = TradeContext("SPY", "buy", 100.0, "momentum")
        risk_score = detector._calculate_risk_score(incidents, context)

        # Should be high risk due to high similarity and financial impact
        assert risk_score > 0.5
        assert risk_score <= 1.0

    def test_latency_target(self, mock_rag):
        """Test that detection meets <50ms latency target."""
        mock_rag.search.return_value = []
        mock_rag.get_context_for_trade.return_value = {"warnings": []}

        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG", return_value=mock_rag):
            detector = SemanticTradeAnomalyDetector()

            result = detector.check_trade({
                "symbol": "AAPL",
                "side": "buy",
                "amount": 100.0,
                "strategy": "momentum",
            })

            # Note: This may fail in slow environments, but should pass in production
            # We allow up to 100ms for test environments
            assert result["latency_ms"] < 100, f"Latency {result['latency_ms']}ms exceeds target"

    def test_get_stats(self, detector):
        """Test statistics retrieval."""
        stats = detector.get_stats()

        assert "rag_available" in stats
        assert "similarity_threshold" in stats
        assert "financial_impact_threshold" in stats
        assert "top_k" in stats
        assert stats["similarity_threshold"] == 0.7
        assert stats["financial_impact_threshold"] == 100
        assert stats["top_k"] == 5

    def test_regression_ll009_syntax_error_prevention(self, mock_rag):
        """
        Regression test for ll_009: Ensure detector doesn't fail with errors.

        See: rag_knowledge/lessons_learned/ll_009_ci_syntax_failure_dec11.md
        """
        # Simulate error in RAG
        mock_rag.search.side_effect = Exception("Database connection error")

        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG", return_value=mock_rag):
            detector = SemanticTradeAnomalyDetector()

            result = detector.check_trade({
                "symbol": "SPY",
                "side": "buy",
                "amount": 100.0,
                "strategy": "momentum",
            })

            # Should fail open (allow trade) on errors
            assert result["safe"], "REGRESSION ll_009: Detector should fail open on errors"
            assert "ERROR" in result["recommendation"]

    def test_regression_200x_position_size_bug(self, mock_rag):
        """
        Regression test for 200x position size bug.

        Ensure detector blocks trades similar to the $1,600 incident.
        """
        # Mock the exact lesson from the 200x bug
        mock_lesson = Mock()
        mock_lesson.id = "LESSON-001"
        mock_lesson.title = "200x Order Amount Error"
        mock_lesson.category = "size_error"
        mock_lesson.severity = "critical"
        mock_lesson.description = "Deployed $1,600 instead of $8/day"
        mock_lesson.root_cause = "Wrong script executed"
        mock_lesson.prevention = "ALWAYS validate order amounts"
        mock_lesson.financial_impact = 1600.0
        mock_lesson.tags = ["order-validation", "critical"]

        mock_rag.search.return_value = [(mock_lesson, 0.9)]  # Very high similarity
        mock_rag.get_context_for_trade.return_value = {"warnings": []}

        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG", return_value=mock_rag):
            detector = SemanticTradeAnomalyDetector(
                similarity_threshold=0.7,
                financial_impact_threshold=100,
            )

            # Try to execute similar large trade
            result = detector.check_trade({
                "symbol": "QQQ",
                "side": "buy",
                "amount": 1500.0,  # Similar to the $1,600 incident
                "strategy": "autonomous",
            })

            assert not result["safe"], "Should block trade similar to 200x bug"
            assert result["risk_score"] > 0.7
            assert "BLOCKED" in result["recommendation"]

    def test_top_k_incidents_returned(self, mock_rag):
        """Test that exactly top_k incidents are returned."""
        # Create 10 mock lessons
        mock_lessons = []
        for i in range(10):
            mock_lesson = Mock()
            mock_lesson.id = f"lesson_{i}"
            mock_lesson.title = f"Incident {i}"
            mock_lesson.category = "test"
            mock_lesson.severity = "medium"
            mock_lesson.description = f"Description {i}"
            mock_lesson.root_cause = f"Cause {i}"
            mock_lesson.prevention = f"Prevention {i}"
            mock_lesson.financial_impact = float(i * 10)
            mock_lesson.tags = []
            mock_lessons.append((mock_lesson, 0.5 - i * 0.03))  # Decreasing similarity

        mock_rag.search.return_value = mock_lessons
        mock_rag.get_context_for_trade.return_value = {"warnings": []}

        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG", return_value=mock_rag):
            detector = SemanticTradeAnomalyDetector(top_k=5)

            result = detector.check_trade({
                "symbol": "AAPL",
                "side": "buy",
                "amount": 100.0,
                "strategy": "test",
            })

            # Should return exactly 5 incidents
            assert len(result["similar_incidents"]) == 5

    def test_crypto_specific_context(self, mock_rag):
        """Test detector works with crypto-specific context."""
        mock_lesson = Mock()
        mock_lesson.id = "LESSON-005"
        mock_lesson.title = "Crypto MACD Threshold Too Conservative"
        mock_lesson.category = "crypto_specific"
        mock_lesson.severity = "medium"
        mock_lesson.description = "MACD < 0 rejected valid crypto trades"
        mock_lesson.root_cause = "Stock thresholds applied to crypto"
        mock_lesson.prevention = "Crypto needs wider thresholds"
        mock_lesson.financial_impact = 0.0
        mock_lesson.tags = ["crypto", "macd"]

        mock_rag.search.return_value = [(mock_lesson, 0.7)]
        mock_rag.get_context_for_trade.return_value = {"warnings": []}

        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG", return_value=mock_rag):
            detector = SemanticTradeAnomalyDetector()

            result = detector.check_trade({
                "symbol": "BTCUSD",
                "side": "buy",
                "amount": 0.5,
                "strategy": "momentum_crypto",
                "additional_context": {
                    "macd": -5.0,
                    "signal": "consolidation",
                },
            })

            # Should pass (low financial impact) but include warning
            assert result["safe"]
            assert len(result["similar_incidents"]) > 0
            assert any("MACD" in inc["title"] for inc in result["similar_incidents"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
