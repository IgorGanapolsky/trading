"""
Unit tests for Factuality Monitor.

Tests the FACTS Benchmark integration including:
- Factuality scoring and weighting
- Ground truth validation
- Hallucination detection and logging
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from src.verification.factuality_monitor import (
    FactualityMonitor,
    FACTS_BENCHMARK_SCORES,
    HallucinationType,
    VerificationSource,
    HallucinationIncident,
    FactualityMetrics,
)


class TestFACTSBenchmarkScores:
    """Test FACTS benchmark score definitions."""

    def test_all_scores_below_70_percent(self):
        """Verify the 70% factuality ceiling - no model exceeds it."""
        for model, score in FACTS_BENCHMARK_SCORES.items():
            if model != "default":
                assert score < 0.70, f"{model} exceeds 70% ceiling: {score}"

    def test_gemini_leads(self):
        """Verify Gemini 3 Pro leads per Dec 2025 benchmark."""
        gemini_score = FACTS_BENCHMARK_SCORES.get("google/gemini-3-pro-preview", 0)
        for model, score in FACTS_BENCHMARK_SCORES.items():
            if model not in ("default", "google/gemini-3-pro-preview"):
                assert gemini_score >= score, f"{model} ({score}) exceeds Gemini ({gemini_score})"

    def test_default_score_exists(self):
        """Ensure default score exists for unknown models."""
        assert "default" in FACTS_BENCHMARK_SCORES
        assert FACTS_BENCHMARK_SCORES["default"] == 0.60


class TestFactualityMonitor:
    """Test FactualityMonitor class."""

    @pytest.fixture
    def monitor(self):
        """Create a FactualityMonitor instance without dependencies."""
        return FactualityMonitor(rag_system=None, anomaly_detector=None)

    def test_get_facts_score_known_model(self, monitor):
        """Test getting FACTS score for known model."""
        score = monitor.get_facts_score("google/gemini-3-pro-preview")
        assert score == 0.688

    def test_get_facts_score_unknown_model(self, monitor):
        """Test getting FACTS score for unknown model returns default."""
        score = monitor.get_facts_score("unknown/model-xyz")
        assert score == 0.60

    def test_get_factuality_weight_no_history(self, monitor):
        """Test factuality weight equals FACTS score when no history."""
        weight = monitor.get_factuality_weight("google/gemini-3-pro-preview")
        assert weight == 0.688

    def test_weight_council_votes_single_vote(self, monitor):
        """Test weighting a single council vote."""
        votes = [
            {
                "model": "google/gemini-3-pro-preview",
                "vote": "BUY",
                "confidence": 0.8,
                "reasoning": "Strong momentum",
            }
        ]

        result = monitor.weight_council_votes(votes)

        assert result["consensus_vote"] == "BUY"
        # Confidence should be capped by factuality ceiling (0.688)
        assert result["consensus_confidence"] <= 0.688
        assert result["factuality_ceiling"] == 0.688

    def test_weight_council_votes_multiple_votes(self, monitor):
        """Test weighting multiple council votes with consensus."""
        votes = [
            {"model": "google/gemini-3-pro-preview", "vote": "BUY", "confidence": 0.8, "reasoning": ""},
            {"model": "anthropic/claude-sonnet-4", "vote": "BUY", "confidence": 0.75, "reasoning": ""},
            {"model": "openai/gpt-4o", "vote": "HOLD", "confidence": 0.6, "reasoning": ""},
        ]

        result = monitor.weight_council_votes(votes)

        # BUY should win with 2/3 votes
        assert result["consensus_vote"] == "BUY"
        assert "weighted_votes" in result
        assert len(result["weighted_votes"]) == 3

    def test_weight_council_votes_tie(self, monitor):
        """Test handling vote ties."""
        votes = [
            {"model": "google/gemini-3-pro-preview", "vote": "BUY", "confidence": 0.8, "reasoning": ""},
            {"model": "anthropic/claude-sonnet-4", "vote": "SELL", "confidence": 0.8, "reasoning": ""},
        ]

        result = monitor.weight_council_votes(votes)

        # Should still produce a result
        assert result["consensus_vote"] in ("BUY", "SELL", "HOLD")

    def test_factuality_ceiling_warning(self, monitor):
        """Test that high confidence triggers factuality ceiling warning."""
        votes = [
            {"model": "google/gemini-3-pro-preview", "vote": "BUY", "confidence": 0.95, "reasoning": ""},
        ]

        result = monitor.weight_council_votes(votes)

        # 95% confidence should trigger warning
        assert result.get("warning") is not None
        assert "70%" in result["warning"]


class TestGroundTruthValidation:
    """Test ground truth validation against technical indicators."""

    @pytest.fixture
    def monitor(self):
        return FactualityMonitor(rag_system=None, anomaly_detector=None)

    def test_validate_technicals_agreement(self, monitor):
        """Test validation when LLM agrees with technicals."""
        result = monitor.validate_against_technicals(
            llm_signal="BUY",
            symbol="SPY",
            macd_signal="BUY",
            rsi_signal="BUY",
            volume_signal="BUY",
        )

        assert result["validated"] is True
        assert result["agreement_score"] == 1.0
        assert result["is_contradiction"] is False

    def test_validate_technicals_contradiction(self, monitor):
        """Test validation when LLM contradicts technicals."""
        result = monitor.validate_against_technicals(
            llm_signal="BUY",
            symbol="SPY",
            macd_signal="SELL",
            rsi_signal="SELL",
            volume_signal="HOLD",
        )

        assert result["validated"] is False
        assert result["agreement_score"] < 0.5
        assert result["is_contradiction"] is True

    def test_validate_technicals_partial_agreement(self, monitor):
        """Test validation with partial agreement."""
        result = monitor.validate_against_technicals(
            llm_signal="BUY",
            symbol="SPY",
            macd_signal="BUY",
            rsi_signal="HOLD",
            volume_signal="SELL",
        )

        # 1/3 agreement = 0.33
        assert 0.3 <= result["agreement_score"] <= 0.4

    def test_validate_technicals_no_signals(self, monitor):
        """Test validation when no technical signals available."""
        result = monitor.validate_against_technicals(
            llm_signal="BUY",
            symbol="SPY",
        )

        assert result["validated"] is None
        assert result["agreement_score"] == 0.5
        assert "No technical signals" in result["message"]


class TestAPIValidation:
    """Test API ground truth validation."""

    @pytest.fixture
    def monitor(self):
        return FactualityMonitor(rag_system=None, anomaly_detector=None)

    def test_validate_api_no_discrepancy(self, monitor):
        """Test validation when LLM claims match API."""
        claimed = {"price": 100.0, "position_qty": 10}
        actual = {"price": 100.0, "position_qty": 10}

        result = monitor.validate_against_api(claimed, actual)

        assert result["validated"] is True
        assert result["hallucination_detected"] is False
        assert len(result["discrepancies"]) == 0

    def test_validate_api_price_discrepancy(self, monitor):
        """Test detection of price hallucination."""
        claimed = {"price": 100.0}
        actual = {"price": 95.0}  # 5% off

        result = monitor.validate_against_api(claimed, actual, tolerance=0.01)

        assert result["validated"] is False
        assert result["hallucination_detected"] is True
        assert len(result["discrepancies"]) == 1

    def test_validate_api_within_tolerance(self, monitor):
        """Test price within tolerance passes."""
        claimed = {"price": 100.5}
        actual = {"price": 100.0}  # 0.5% off

        result = monitor.validate_against_api(claimed, actual, tolerance=0.01)

        assert result["validated"] is True


class TestHallucinationLogging:
    """Test hallucination incident logging."""

    @pytest.fixture
    def monitor(self):
        monitor = FactualityMonitor(rag_system=None, anomaly_detector=None)
        # Clear state for isolated testing
        monitor.metrics = {}
        monitor.incidents = []
        return monitor

    def test_record_verification_true(self, monitor):
        """Test recording a verified claim."""
        monitor.record_verification(
            model="test/gemini-model",  # Use unique test model
            claim_verified=True,
            context={"symbol": "SPY"},
        )

        metrics = monitor.metrics.get("test/gemini-model")
        assert metrics is not None
        assert metrics.total_claims == 1
        assert metrics.verified_claims == 1
        assert metrics.hallucinations == 0

    def test_record_verification_false(self, monitor):
        """Test recording a hallucination."""
        monitor.record_verification(
            model="test/gpt-model",  # Use unique test model
            claim_verified=False,
            context={"issue": "price mismatch"},
        )

        metrics = monitor.metrics.get("test/gpt-model")
        assert metrics is not None
        assert metrics.total_claims == 1
        assert metrics.verified_claims == 0
        assert metrics.hallucinations == 1

    def test_accuracy_rate_calculation(self, monitor):
        """Test accuracy rate calculation."""
        # Add some verifications using unique model name
        for _ in range(8):
            monitor.record_verification("test/accuracy-model", True)
        for _ in range(2):
            monitor.record_verification("test/accuracy-model", False)

        metrics = monitor.metrics["test/accuracy-model"]
        assert metrics.accuracy_rate == 0.8  # 8/10


class TestFactualityReport:
    """Test factuality report generation."""

    @pytest.fixture
    def monitor(self):
        monitor = FactualityMonitor(rag_system=None, anomaly_detector=None)
        # Clear any existing metrics to ensure clean state
        monitor.metrics = {}
        monitor.incidents = []
        # Add some data
        monitor.record_verification("google/gemini-3-pro-preview", True)
        monitor.record_verification("google/gemini-3-pro-preview", True)
        monitor.record_verification("openai/gpt-4o", False)
        return monitor

    def test_report_structure(self, monitor):
        """Test factuality report has expected structure."""
        report = monitor.get_factuality_report()

        assert "timestamp" in report
        assert "facts_benchmark_scores" in report
        assert "model_metrics" in report
        assert "total_hallucinations" in report
        assert "overall_accuracy" in report
        assert "factuality_ceiling_warning" in report

    def test_report_metrics(self, monitor):
        """Test report contains correct metrics."""
        report = monitor.get_factuality_report()

        # Only count hallucinations from this test's data
        total_hallucinations = sum(
            m.get("hallucinations", 0) for m in report["model_metrics"].values()
        )
        total_claims = sum(
            m.get("total_claims", 0) for m in report["model_metrics"].values()
        )
        verified_claims = sum(
            m.get("verified_claims", 0) for m in report["model_metrics"].values()
        )

        assert total_hallucinations == 1
        assert total_claims == 3
        assert verified_claims == 2


class TestSeverityAssessment:
    """Test hallucination severity assessment."""

    @pytest.fixture
    def monitor(self):
        return FactualityMonitor(rag_system=None, anomaly_detector=None)

    def test_critical_severity(self, monitor):
        """Test critical severity for large price deviation."""
        severity = monitor._assess_severity(
            HallucinationType.PRICE_MISMATCH,
            claimed=100.0,
            actual=80.0,  # 25% off
        )
        assert severity == "critical"

    def test_high_severity(self, monitor):
        """Test high severity for moderate deviation."""
        severity = monitor._assess_severity(
            HallucinationType.PRICE_MISMATCH,
            claimed=100.0,
            actual=93.0,  # 7% off
        )
        assert severity == "high"

    def test_signal_contradiction_is_high(self, monitor):
        """Test signal contradiction is always high severity."""
        severity = monitor._assess_severity(
            HallucinationType.SIGNAL_CONTRADICTION,
            claimed="BUY",
            actual="SELL",
        )
        assert severity == "high"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
